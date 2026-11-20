"""Evidence-First Research Agent — ODSC x Nebius Hackathon.

question -> plan queries (Nebius Token Factory, MiniMaxAI/MiniMax-M3)
         -> Tavily live search (advanced, 5 results/query)
         -> credibility scoring + select & dedupe
         -> Tavily extract for the top sources when snippets are thin
         -> (one refinement round if < MIN_SOURCES)
         -> synthesis with [n] citations (Token Factory)
         -> second LLM verification pass (claim vs. source)
         -> code-level citation check + confidence score
         -> answer + sources + trace  (or honest INSUFFICIENT EVIDENCE, exit 2)

Usage:
    python src/agent.py "Your research question" [--json] [--trace-file docs/trace.json]
    python src/agent.py "Your research question" --html reports/answer.html --md reports/answer.md

Keys live only in .env / environment variables — never in code, traces or output.
No answer is ever hard-coded; every claim must come from live Tavily results.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional; plain env vars also work
    pass

# ---------------------------------------------------------------- tunables
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
DEFAULT_MODEL = "MiniMaxAI/MiniMax-M3"

MAX_QUERIES = 4          # sub-queries per round
RESULTS_PER_QUERY = 5    # Tavily max_results (matches the Nebius cookbook)
MAX_SOURCES = 8          # evidence passed to the model (caps tokens/cost)
MAX_PER_DOMAIN = 2       # avoid one site dominating the answer
MIN_SOURCES = 3          # below this: one refinement round, then refuse
MIN_SCORE = 0.2          # drop weak Tavily matches
SNIPPET_CHARS = 1200     # chars of snippet kept per source
EXTRACT_TOP_N = 3        # top sources enriched with Tavily extract
EXTRACT_MIN_CHARS = 600  # only extract when the snippet is thinner than this
EXTRACT_CHARS = 4000     # chars of extracted page content kept per source

# Credibility tiers. Scores are heuristics about the *publisher*, not a
# guarantee about a single page — the verification pass still checks claims.
TRUSTED_TLDS = (".edu", ".gov", ".ac.uk", ".edu.au", ".gov.uk", ".gov.au", ".int")
TRUSTED_DOMAINS = {
    "nature.com", "science.org", "sciencedirect.com", "arxiv.org",
    "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov", "who.int", "nih.gov",
    "nasa.gov", "wikipedia.org", "britannica.com", "reuters.com",
    "apnews.com", "bbc.com", "bbc.co.uk", "nytimes.com", "theguardian.com",
    "ft.com", "wsj.com", "bloomberg.com", "economist.com", "docs.python.org",
    "developer.mozilla.org", "github.com", "stackoverflow.com",
    "oecd.org", "worldbank.org", "un.org", "europa.eu",
}
OFFICIAL_DOC_HINTS = ("docs.", "developer.", "support.", "help.", "learn.")
SPAM_TLDS = (".xyz", ".click", ".top", ".loan", ".buzz", ".sbs", ".online")
SPAM_HINTS = (
    "best-", "top10", "top-10", "review", "cheap-", "free-download",
    "casino", "crypto-giveaway", "earn-money", "miracle",
)

TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|ref$|ref_)", re.I)


# ---------------------------------------------------------------- data
@dataclass
class Source:
    id: int
    title: str
    url: str
    content: str
    score: float  # Tavily relevance score (0-1)
    query: str = ""
    credibility: float = 0.5   # 0-1 publisher-credibility heuristic
    credibility_tier: str = "standard"
    credibility_note: str = ""
    extracted: bool = False

    @property
    def combined_score(self) -> float:
        """Ranking used for selection: relevance and credibility together."""
        return 0.6 * self.score + 0.4 * self.credibility


@dataclass
class Trace:
    steps: list = field(default_factory=list)

    def add(self, step: str, **data):
        self.steps.append({"t": round(time.time(), 2), "step": step, **data})
        # Trace goes to stderr only, and never contains keys or raw secrets.
        safe = ", ".join(f"{k}={v}" for k, v in data.items())
        print(f"[trace] {step}: {safe}", file=sys.stderr)


# ---------------------------------------------------------------- clients
def get_llm():
    from openai import OpenAI

    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise SystemExit("NEBIUS_API_KEY is not set (see .env.example).")
    return OpenAI(
        base_url=os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
        api_key=key,
    )


def get_search():
    from tavily import TavilyClient

    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise SystemExit("TAVILY_API_KEY is not set (see .env.example).")
    return TavilyClient(api_key=key)


def chat(llm, system: str, user: str, temperature: float = 0.2,
         max_tokens: int = 2500) -> str:
    model = os.environ.get("NEBIUS_MODEL", DEFAULT_MODEL)
    resp = llm.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    text = resp.choices[0].message.content or ""
    # MiniMax-M3 may return reasoning text; strip <think> blocks.
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()


# ---------------------------------------------------------------- credibility
def credibility_score(url: str, title: str = "") -> tuple[float, str, str]:
    """Score a source's publisher credibility (0-1) with a human-readable note.

    Prefers .edu/.gov, official docs and established news/reference sites;
    down-ranks content farms and SEO-spam patterns. This is a *ranking*
    heuristic only — it never invents or removes facts, and the verification
    pass still checks every cited claim against its source text.
    """
    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return 0.3, "standard", "unparseable URL"
    host_no_port = host.split(":")[0]

    # Spam / content-farm signals first (they override a generic .com).
    if any(host_no_port.endswith(tld) for tld in SPAM_TLDS):
        return 0.15, "low", f"low-trust TLD ({host_no_port.rsplit('.', 1)[-1]})"
    hay = (host_no_port + " " + title.lower())
    if any(h in hay for h in SPAM_HINTS):
        return 0.2, "low", "SEO-spam pattern in domain/title"
    if host_no_port.count("-") >= 3:
        return 0.25, "low", "hyphen-stuffed domain (typical content farm)"

    if any(host_no_port.endswith(tld) for tld in TRUSTED_TLDS):
        return 0.95, "high", f"trusted TLD ({host_no_port.rsplit('.', 1)[-1]})"
    if host_no_port in TRUSTED_DOMAINS or any(
        host_no_port.endswith("." + d) for d in TRUSTED_DOMAINS
    ):
        return 0.9, "high", "established publisher / official reference"
    if any(host_no_port.startswith(h) for h in OFFICIAL_DOC_HINTS):
        return 0.85, "high", "official documentation"
    if host_no_port.endswith((".org", ".net")):
        return 0.65, "standard", "non-profit / network domain"
    return 0.5, "standard", "standard web source"


# ---------------------------------------------------------------- planning
PLAN_SYSTEM = (
    "You plan web research. Break the user's question into at most {n} short, distinct web search "
    "queries that together cover it (include a query that could surface contradicting evidence if the "
    "claim is contested). Return ONLY a JSON array of strings."
)


def parse_json_list(text: str) -> list[str]:
    m = re.search(r"\[.*\]", text, flags=re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [q.strip() for q in data if isinstance(q, str) and q.strip()]


def plan_queries(llm, question: str, trace: Trace) -> list[str]:
    try:
        queries = parse_json_list(
            chat(llm, PLAN_SYSTEM.format(n=MAX_QUERIES), question)
        )[:MAX_QUERIES]
    except Exception as e:  # planning failure must not kill the run
        trace.add("plan_failed", error=type(e).__name__)
        queries = []
    if not queries:
        queries = [question]  # safe fallback
    trace.add("plan", queries=queries)
    return queries


# ---------------------------------------------------------------- search
def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    q = "&".join(x for x in p.query.split("&") if x and not TRACKING_PARAMS.match(x))
    host = p.netloc.lower().removeprefix("www.")
    return urlunparse((p.scheme.lower(), host, p.path.rstrip("/"), "", q, ""))


def run_searches(search, queries: list[str], trace: Trace) -> list[dict]:
    raw = []
    for q in queries:
        try:
            res = search.search(query=q, search_depth="advanced",
                                max_results=RESULTS_PER_QUERY)
            hits = res.get("results", []) if isinstance(res, dict) else []
            trace.add("tavily", query=q, results=len(hits))
            for h in hits:
                h["_query"] = q
            raw.extend(hits)
        except Exception as e:
            trace.add("tavily_failed", query=q, error=type(e).__name__)
    return raw


def select_evidence(raw: list[dict],
                    existing: list[Source] | None = None) -> list[Source]:
    """Dedupe by normalised URL, drop weak/empty hits, cap per domain,
    rank by combined (Tavily relevance + credibility) score."""
    seen = {normalize_url(s.url) for s in existing or []}
    domains: dict[str, int] = {}
    for s in existing or []:
        d = urlparse(s.url).netloc.lower().removeprefix("www.")
        domains[d] = domains.get(d, 0) + 1
    out = list(existing or [])
    scored = []
    for h in raw:
        url, content = h.get("url") or "", (h.get("content") or "").strip()
        if not url or len(content) < 40 or (h.get("score") or 0) < MIN_SCORE:
            continue
        cred, tier, note = credibility_score(url, h.get("title") or "")
        scored.append((h, cred, tier, note))
    # Highest combined score first so the best evidence wins the cap.
    scored.sort(key=lambda t: 0.6 * (t[0].get("score") or 0) + 0.4 * t[1],
                reverse=True)
    for h, cred, tier, note in scored:
        url, content = h.get("url") or "", (h.get("content") or "").strip()
        key = normalize_url(url)
        dom = urlparse(url).netloc.lower().removeprefix("www.")
        if key in seen or domains.get(dom, 0) >= MAX_PER_DOMAIN:
            continue
        seen.add(key)
        domains[dom] = domains.get(dom, 0) + 1
        out.append(Source(
            len(out) + 1, (h.get("title") or dom).strip(), url,
            content[:SNIPPET_CHARS], float(h.get("score") or 0),
            h.get("_query", ""), cred, tier, note))
        if len(out) >= MAX_SOURCES:
            break
    return out


def enrich_with_extract(search, sources: list[Source], trace: Trace) -> list[Source]:
    """Tavily extract for the top 2-3 sources when their snippet is thin.

    Guarded: any failure (no extract method, network error, empty result)
    is logged and the run continues with the original snippets.
    """
    extract = getattr(search, "extract", None)
    if not callable(extract):
        trace.add("extract_skipped", reason="client has no extract method")
        return sources
    thin = [s for s in sorted(sources, key=lambda s: s.combined_score, reverse=True)
            if len(s.content) < EXTRACT_MIN_CHARS][:EXTRACT_TOP_N]
    if not thin:
        trace.add("extract_skipped", reason="snippets already full enough")
        return sources
    for s in thin:
        try:
            res = extract(urls=[s.url], extract_depth="advanced")
            items = res.get("results", []) if isinstance(res, dict) else []
            text = ""
            if items:
                text = (items[0].get("raw_content") or items[0].get("content") or "").strip()
            if len(text) > len(s.content):
                s.content = text[:EXTRACT_CHARS]
                s.extracted = True
                trace.add("extract", source=s.id, chars=len(s.content))
            else:
                trace.add("extract_empty", source=s.id)
        except Exception as e:
            trace.add("extract_failed", source=s.id, error=type(e).__name__)
    return sources


REFINE_SYSTEM = (
    "The first search round returned too little evidence. Propose at most 2 different, more specific or "
    "differently worded web search queries. Return ONLY a JSON array of strings."
)

# ---------------------------------------------------------------- synthesis
SYNTH_SYSTEM = """You are a careful research analyst. Answer the question using ONLY the numbered sources. Rules:

- Write in your own words; do not copy source text.
- Every factual claim must end with citation(s) like [1] or [2][3]. Never cite a number that is not in the list.
- Separate what the sources state (facts) from your own inference; label inference with "Inference:".
- If sources disagree, say so and cite both sides. If the sources do not cover part of the question, say exactly what is missing. Never invent facts, figures, dates or sources.
- Include a short "Conflicts and gaps" section at the end, even if it only says none were found.
Format: a short direct answer, then 'Key findings' bullets, then 'Conflicts and gaps'."""


def format_sources(sources: list[Source]) -> str:
    parts = []
    for s in sources:
        parts.append(
            f"[{s.id}] {s.title}\nURL: {s.url}\n"
            f"Credibility: {s.credibility_tier} ({s.credibility:.2f}) — {s.credibility_note}\n"
            f"{s.content}")
    return "\n\n".join(parts)


def verify_citations(answer: str, sources: list[Source]) -> tuple[str, dict]:
    """Remove citations that point to non-existent sources; report uncited lines."""
    valid = {s.id for s in sources}
    invalid = set()

    def fix(m):
        n = int(m.group(1))
        if n in valid:
            return m.group(0)
        invalid.add(n)
        return ""

    cleaned = re.sub(r"\[(\d+)\]", fix, answer)
    lines = [l for l in cleaned.splitlines()
             if len(l.strip()) > 60 and not l.lstrip().startswith("#")]
    uncited = [l.strip()[:80] for l in lines
               if not re.search(r"\[\d+\]", l)
               and not l.lower().lstrip("-* ").startswith(
                   ("inference", "gap", "missing", "conflict"))]
    return cleaned, {"invalid_citations_removed": sorted(invalid),
                     "uncited_lines": len(uncited)}


def render_sources(answer: str, sources: list[Source]) -> str:
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer)})
    by_id = {s.id: s for s in sources}
    return "\n".join(f"[{n}] {by_id[n].title} - {by_id[n].url}"
                     for n in cited if n in by_id)


# ------------------------------------------------------- verification pass
VERIFY_SYSTEM = """You verify a draft research answer against its sources. For EACH factual claim in the draft, decide whether at least one cited source actually supports it, using ONLY the source texts given. Return ONLY a JSON object like:
{"checks": [{"claim": "<short claim>", "source_ids": [1], "supported": true, "note": "<why>"}, {"claim": "<short claim>", "source_ids": [2], "supported": false, "note": "<why not>"}]}
Mark supported=false when the claim goes beyond what the cited source says, contradicts it, or no cited source covers it. Do not add claims of your own."""


def verify_claims(llm, answer: str, sources: list[Source],
                  trace: Trace) -> dict:
    """Second LLM pass: check each cited claim against its source text.

    Returns {"supported": n, "unsupported": n, "unsupported_claims": [...],
    "status": "verified"|"heuristic_fallback"|"failed"}. Never raises —
    on any failure it falls back to the code-level citation check.
    """
    try:
        raw = chat(llm, VERIFY_SYSTEM,
                   f"Draft answer:\n{answer}\n\nSources:\n{format_sources(sources)}",
                   temperature=0.0, max_tokens=2000)
        m = re.search(r"\{.*\}", raw, flags=re.S)
        data = json.loads(m.group(0)) if m else {}
        checks = data.get("checks", []) if isinstance(data, dict) else []
        if not isinstance(checks, list) or not checks:
            raise ValueError("no checks returned")
        unsupported = [c for c in checks if not c.get("supported")]
        result = {
            "status": "verified",
            "supported": len(checks) - len(unsupported),
            "unsupported": len(unsupported),
            "total_checked": len(checks),
            "unsupported_claims": [
                {"claim": str(c.get("claim", ""))[:200],
                 "source_ids": c.get("source_ids", []),
                 "note": str(c.get("note", ""))[:200]} for c in unsupported],
        }
        trace.add("verify_llm", **{k: v for k, v in result.items()
                                   if k != "unsupported_claims"},
                  unsupported_claims=len(result["unsupported_claims"]))
        return result
    except Exception as e:
        trace.add("verify_llm_failed", error=type(e).__name__,
                  fallback="citation_check_only")
        cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer)})
        valid = {s.id for s in sources}
        return {"status": "heuristic_fallback",
                "supported": len([n for n in cited if n in valid]),
                "unsupported": len([n for n in cited if n not in valid]),
                "total_checked": len(cited),
                "unsupported_claims": []}


def confidence_score(sources: list[Source], verification: dict,
                     uncited_lines: int, answer: str) -> dict:
    """0-100 confidence from evidence quality, not from model self-report.

    Combines: number of usable sources, mean credibility, mean Tavily score,
    verification outcome, and how many long lines lack a citation.
    """
    if not sources:
        return {"score": 0, "level": "none",
                "reasons": ["no usable sources"]}
    n = len(sources)
    mean_cred = sum(s.credibility for s in sources) / n
    mean_rel = sum(s.score for s in sources) / n
    total = verification.get("total_checked") or 0
    supported = verification.get("supported") or 0
    support_ratio = (supported / total) if total else 0.7  # neutral if unmeasured
    cited = len({int(x) for x in re.findall(r"\[(\d+)\]", answer)})
    score = (
        min(n, MAX_SOURCES) / MAX_SOURCES * 25
        + mean_cred * 25
        + mean_rel * 20
        + support_ratio * 20
        + (10 if uncited_lines == 0 else max(0, 10 - uncited_lines * 2))
    )
    score = int(round(max(0, min(100, score))))
    level = "high" if score >= 75 else "medium" if score >= 50 else "low"
    reasons = [
        f"{n} usable source(s)",
        f"mean credibility {mean_cred:.2f}",
        f"verification: {supported}/{total} claims supported"
        + (" (fallback check)" if verification.get("status") != "verified" else ""),
        f"{cited} source(s) cited, {uncited_lines} long uncited line(s)",
    ]
    return {"score": score, "level": level, "reasons": reasons}


def extract_conflicts_gaps(answer: str) -> str:
    """Pull the 'Conflicts and gaps' section out of the answer, if present."""
    m = re.search(r"conflicts?\s+and\s+gaps?\s*:?\s*\n?(.*?)(?:\n#{1,3}\s|\Z)",
                  answer, flags=re.I | re.S)
    if m and m.group(1).strip():
        return m.group(1).strip()
    return ""


# ---------------------------------------------------------------- driver
def research(question: str, llm=None, search=None, use_extract: bool = True) -> dict:
    started = time.time()
    trace = Trace()
    llm = llm or get_llm()
    search = search or get_search()

    queries = plan_queries(llm, question, trace)
    sources = select_evidence(run_searches(search, queries, trace))
    if use_extract and sources:
        sources = enrich_with_extract(search, sources, trace)
    trace.add("evidence", kept=len(sources),
              domains=len({urlparse(s.url).netloc for s in sources}),
              high_credibility=sum(1 for s in sources if s.credibility_tier == "high"),
              low_credibility=sum(1 for s in sources if s.credibility_tier == "low"))

    if len(sources) < MIN_SOURCES:  # one refinement round, then stop
        try:
            extra = parse_json_list(chat(
                llm, REFINE_SYSTEM,
                f"Question: {question}\nPrevious queries: {queries}"))[:2]
        except Exception as e:
            trace.add("refine_failed", error=type(e).__name__)
            extra = []
        if extra:
            trace.add("refine", queries=extra)
            sources = select_evidence(run_searches(search, extra, trace),
                                      existing=sources)
            if use_extract:
                sources = enrich_with_extract(search, sources, trace)
            trace.add("evidence_after_refine", kept=len(sources))

    elapsed = round(time.time() - started, 1)
    if len(sources) < MIN_SOURCES:
        msg = ("INSUFFICIENT EVIDENCE: the live search did not return enough usable sources "
               "to answer this reliably, so no answer was generated. Try rephrasing, or check "
               "your Tavily key and credits.")
        trace.add("refuse", reason="insufficient_evidence", sources=len(sources),
                  elapsed_seconds=elapsed)
        return {"question": question, "answer": msg, "sources": [],
                "sources_text": "", "status": "insufficient_evidence",
                "confidence": {"score": 0, "level": "none",
                               "reasons": ["fewer than 3 usable sources"]},
                "conflicts_gaps": "",
                "verification": {"status": "not_run", "supported": 0,
                                 "unsupported": 0, "total_checked": 0,
                                 "unsupported_claims": []},
                "trace": trace.steps, "elapsed_seconds": elapsed}

    raw_answer = chat(llm, SYNTH_SYSTEM,
                      f"Question: {question}\n\nSources:\n{format_sources(sources)}",
                      temperature=0.1, max_tokens=3000)
    answer, cite_report = verify_citations(raw_answer, sources)
    trace.add("verify", **cite_report)

    verification = verify_claims(llm, answer, sources, trace)
    if verification.get("unsupported_claims"):
        flagged = "; ".join(c.get("claim", "") for c in verification["unsupported_claims"][:3])
        answer += ("\n\nVerification note: the verification pass flagged "
                   f"{verification['unsupported']} claim(s) as unsupported by the cited "
                   f"source(s): {flagged}. Treat those claims with caution.")
        trace.add("verify_flagged",
                  unsupported=verification["unsupported"])

    conf = confidence_score(sources, verification,
                            cite_report["uncited_lines"], answer)
    trace.add("confidence", score=conf["score"], level=conf["level"])
    elapsed = round(time.time() - started, 1)
    return {"question": question, "answer": answer,
            "sources_text": render_sources(answer, sources),
            "sources": [s.__dict__ for s in sources],
            "status": "ok",
            "verification": {**verification, **cite_report},
            "confidence": conf,
            "conflicts_gaps": extract_conflicts_gaps(answer),
            "trace": trace.steps, "elapsed_seconds": elapsed}


# ---------------------------------------------------------------- reports
def build_markdown_report(result: dict) -> str:
    lines = [f"# Research: {result['question']}", ""]
    if result["status"] == "ok":
        conf = result.get("confidence", {})
        lines += [f"**Confidence:** {conf.get('score', '?')}/100 "
                  f"({conf.get('level', '')})", "",
                  result["answer"], "",
                  "## Sources"]
        for s in result.get("sources", []):
            lines.append(f"- [{s['id']}] [{s['title']}]({s['url']}) "
                         f"— credibility: {s.get('credibility_tier', '')} "
                         f"({s.get('credibility', 0):.2f})")
    else:
        lines += [result["answer"]]
    lines += ["", "## Trace"]
    for step in result.get("trace", []):
        lines.append(f"- `{step.get('step')}` — " +
                     ", ".join(f"{k}={v}" for k, v in step.items()
                               if k not in ("t", "step")))
    return "\n".join(lines) + "\n"


def build_html_report(result: dict) -> str:
    """Standalone single-file HTML report (inline CSS, no external assets)."""
    try:
        from report import build_html_report as _from_report
        return _from_report(result)
    except ImportError:
        pass
    # Fallback: minimal inline version if report.py is unavailable.
    esc = html_lib.escape
    conf = result.get("confidence", {})
    body = f"<h1>{esc(result['question'])}</h1><p>{esc(result['answer'])}</p>"
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>Research: {esc(result['question'])}</title></head>"
            f"<body>{body}</body></html>")


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Evidence-first research agent (Nebius Token Factory + Tavily)")
    ap.add_argument("question", help="research question to answer")
    ap.add_argument("--json", action="store_true", help="print full result as JSON")
    ap.add_argument("--trace-file", help="write the research trace (no secrets) to this path")
    ap.add_argument("--html", metavar="PATH", help="write a standalone HTML report to this path")
    ap.add_argument("--md", metavar="PATH", help="write a Markdown report to this path")
    ap.add_argument("--no-extract", action="store_true",
                    help="skip the Tavily extract enrichment step")
    args = ap.parse_args(argv)

    try:
        result = research(args.question, use_extract=not args.no_extract)
    except SystemExit as e:
        # Missing-key messages from get_llm()/get_search() land here.
        print(str(e), file=sys.stderr)
        return 1

    if args.trace_file:
        with open(args.trace_file, "w") as f:
            json.dump(result["trace"], f, indent=2)
        print(f"[trace] wrote {args.trace_file}", file=sys.stderr)
    if args.html:
        with open(args.html, "w") as f:
            f.write(build_html_report(result))
        print(f"[report] wrote {args.html}", file=sys.stderr)
    if args.md:
        with open(args.md, "w") as f:
            f.write(build_markdown_report(result))
        print(f"[report] wrote {args.md}", file=sys.stderr)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\nQuestion: {result['question']}\n")
        if result["status"] == "ok":
            conf = result.get("confidence", {})
            print(f"Confidence: {conf.get('score', '?')}/100 ({conf.get('level', '')})\n")
        print(result["answer"])
        if result.get("sources_text"):
            print(f"\nSources:\n{result['sources_text']}")
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    sys.exit(main())
