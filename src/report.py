"""Standalone HTML / Markdown report generator for the Evidence-First agent.

Single-file HTML, inline CSS only, no external assets — the file can be
opened anywhere and shared with judges. Palette from the project brief:
teal #0F766E, ink #1F2A37, mist #F1F5F4, success #15803D, warning #B45309,
error #B91C1C.
"""
from __future__ import annotations

import html as html_lib
import re

TEAL = "#0F766E"
INK = "#1F2A37"


def _esc(text) -> str:
    return html_lib.escape("" if text is None else str(text))


def _linkify_citations(text: str, sources: list[dict]) -> str:
    """Turn [n] citations into anchor links to the matching source entry."""
    by_id = {s["id"]: s for s in sources}

    def repl(m):
        n = int(m.group(1))
        if n in by_id:
            return (f'<a class="cite" href="#source-{n}" '
                    f'title="{_esc(by_id[n].get("title", ""))}">[{n}]</a>')
        return m.group(0)

    return re.sub(r"\[(\d+)\]", repl, _esc(text))


def _answer_html(answer: str, sources: list[dict]) -> str:
    """Render the answer as paragraphs / bullets, preserving citations."""
    out = []
    for block in answer.strip().split("\n"):
        line = block.strip()
        if not line:
            continue
        if line.startswith(("# ", "## ", "### ")):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level + 1}>{_linkify_citations(line.lstrip('# ').strip(), sources)}</h{level + 1}>")
        elif line.startswith(("- ", "* ")):
            out.append(f"<li>{_linkify_citations(line[2:].strip(), sources)}</li>")
        else:
            out.append(f"<p>{_linkify_citations(line, sources)}</p>")
    # Wrap consecutive <li> items in a <ul>.
    html, buf = [], []
    for item in out:
        if item.startswith("<li>"):
            buf.append(item)
        else:
            if buf:
                html.append("<ul>" + "".join(buf) + "</ul>")
                buf = []
            html.append(item)
    if buf:
        html.append("<ul>" + "".join(buf) + "</ul>")
    return "\n".join(html)


def build_html_report(result: dict) -> str:
    q = result.get("question", "")
    status = result.get("status", "")
    conf = result.get("confidence") or {}
    score = conf.get("score", 0)
    level = conf.get("level", "none")
    sources = result.get("sources") or []
    verification = result.get("verification") or {}
    trace = result.get("trace") or []
    elapsed = result.get("elapsed_seconds", "?")
    conflicts = result.get("conflicts_gaps", "")

    level_class = {"high": "ok", "medium": "warn", "low": "bad",
                   "none": "bad"}.get(level, "warn")
    status_badge = ("<span class='badge ok'>Answered with evidence</span>"
                    if status == "ok" else
                    "<span class='badge bad'>Insufficient evidence — no answer generated</span>")

    # Short answer: first paragraph of the answer.
    short = result.get("answer", "").strip().split("\n\n")[0].strip()

    sources_html = ""
    if sources:
        items = []
        for s in sources:
            tier = s.get("credibility_tier", "standard")
            cred = s.get("credibility", 0)
            items.append(
                f'<li id="source-{s["id"]}"><span class="src-n">[{s["id"]}]</span> '
                f'<a href="{_esc(s["url"])}" target="_blank" rel="noopener">{_esc(s["title"])}</a><br>'
                f'<span class="src-url">{_esc(s["url"])}</span><br>'
                f'<span class="pill pill-{tier}">credibility: {tier} ({cred:.2f})</span> '
                f'<span class="pill">Tavily score {s.get("score", 0):.2f}</span>'
                + (" <span class='pill'>full text extracted</span>" if s.get("extracted") else "")
                + "</li>")
        sources_html = "<ol class='sources'>" + "\n".join(items) + "</ol>"
    else:
        sources_html = "<p class='muted'>No sources — the agent refused rather than guessing.</p>"

    verify_html = ""
    if status == "ok":
        unsupported = verification.get("unsupported_claims") or []
        flag = (f"<p class='flag warn'>⚠ Verification flagged "
                f"{verification.get('unsupported', 0)} claim(s) as unsupported — "
                f"treat them with caution.</p>" if unsupported else
                "<p class='flag ok'>✓ Verification pass: no unsupported claims flagged.</p>")
        verify_html = (
            f"<section><h2>Verification</h2>{flag}"
            f"<p>Claims checked: {verification.get('total_checked', '?')} · "
            f"supported: {verification.get('supported', '?')} · "
            f"unsupported: {verification.get('unsupported', '?')} · "
            f"method: { _esc(str(verification.get('status', '')))} · "
            f"invalid citations removed: "
            f"{verification.get('invalid_citations_removed', [])} · "
            f"uncited long lines: {verification.get('uncited_lines', '?')}</p></section>")

    conflicts_html = ""
    if conflicts:
        conflicts_html = (f"<section><h2>Conflicts and gaps</h2>"
                          f"<p>{_linkify_citations(conflicts, sources)}</p></section>")

    trace_rows = "".join(
        "<tr><td>" + _esc(str(s.get("t", ""))) + "</td><td><code>" +
        _esc(str(s.get("step", ""))) + "</code></td><td>" +
        _esc(", ".join(f"{k}={v}" for k, v in s.items()
                       if k not in ("t", "step"))) + "</td></tr>"
        for s in trace)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evidence-First Research — {_esc(q)}</title>
<style>
  :root {{ --teal: {TEAL}; --ink: {INK}; --mist: #F1F5F4; --border: #CBD5D1;
          --ok: #15803D; --warn: #B45309; --bad: #B91C1C; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: var(--ink);
         max-width: 820px; margin: 0 auto; padding: 32px 20px 64px; line-height: 1.6;
         background: #fff; }}
  header {{ border-bottom: 3px solid var(--teal); padding-bottom: 16px; margin-bottom: 24px; }}
  .kicker {{ color: var(--teal); font-weight: 700; letter-spacing: .08em;
            text-transform: uppercase; font-size: 12px; }}
  h1 {{ font-size: 26px; line-height: 1.3; margin: 8px 0; }}
  h2 {{ color: var(--teal); font-size: 19px; border-bottom: 1px solid var(--border);
       padding-bottom: 6px; margin-top: 32px; }}
  .badge {{ display: inline-block; padding: 4px 10px; border-radius: 999px;
           font-size: 13px; font-weight: 600; }}
  .badge.ok, .flag.ok {{ background: #DCFCE7; color: var(--ok); }}
  .badge.bad, .flag.bad {{ background: #FEE2E2; color: var(--bad); }}
  .flag.warn {{ background: #FEF3C7; color: var(--warn); }}
  .flag {{ padding: 10px 14px; border-radius: 8px; }}
  .confidence {{ display: flex; align-items: center; gap: 14px; margin: 16px 0; }}
  .score {{ font-size: 34px; font-weight: 800; color: var(--teal); }}
  .score small {{ font-size: 15px; color: var(--ink); font-weight: 600; }}
  .bar {{ flex: 1; height: 10px; background: var(--mist); border-radius: 999px; overflow: hidden; }}
  .bar i {{ display: block; height: 100%; background: var(--teal); width: {score}%; }}
  .short {{ background: var(--mist); border-left: 4px solid var(--teal);
          padding: 14px 18px; font-size: 17px; }}
  .cite {{ color: var(--teal); font-weight: 700; text-decoration: none; }}
  .cite:hover {{ text-decoration: underline; }}
  ol.sources {{ padding-left: 0; list-style: none; }}
  ol.sources li {{ padding: 12px 0; border-bottom: 1px solid var(--border); }}
  .src-n {{ font-weight: 700; color: var(--teal); }}
  .src-url {{ color: #6B7280; font-size: 13px; word-break: break-all; }}
  .pill {{ display: inline-block; background: var(--mist); border-radius: 999px;
          padding: 2px 9px; font-size: 12px; margin-top: 4px; }}
  .pill-high {{ background: #DCFCE7; color: var(--ok); }}
  .pill-low {{ background: #FEE2E2; color: var(--bad); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border);
           vertical-align: top; }}
  th {{ color: var(--teal); }}
  .muted {{ color: #6B7280; font-size: 13px; }}
  footer {{ margin-top: 40px; border-top: 1px solid var(--border); padding-top: 12px; }}
  a {{ color: var(--teal); }}
</style></head>
<body>
<header>
  <div class="kicker">Evidence-First Research Agent · ODSC x Nebius Hackathon</div>
  <h1>{_esc(q)}</h1>
  {status_badge}
</header>

<section>
  <div class="confidence">
    <div class="score">{score}<small>/100</small></div>
    <div class="bar"><i></i></div>
    <div><strong>Confidence: {level}</strong><br>
    <span class="muted">{_esc("; ".join(conf.get("reasons", [])))}</span></div>
  </div>
  <div class="short">{_esc(short)}</div>
</section>

<section><h2>Key findings</h2>
{_answer_html(result.get("answer", ""), sources)}
</section>

{conflicts_html}
{verify_html}

<section><h2>Sources</h2>
{sources_html}
<p class="muted">Every citation [n] above links to the matching source here. Click any link to check the claim against the original page.</p>
</section>

<section><h2>Research trace</h2>
<table><tr><th>Time</th><th>Step</th><th>Detail</th></tr>
{trace_rows}
</table>
<p class="muted">Timing: {elapsed}s for this run. Cost: not measured in this run — Token Factory and Tavily usage depends on the number of queries and sources; see README trade-offs. No API keys are stored in this report or its trace.</p>
</section>

<footer><p class="muted">Generated by the Evidence-First Research Agent (Nebius Token Factory · MiniMaxAI/MiniMax-M3 + Tavily). Model: MiniMaxAI/MiniMax-M3. Team EvidenceFirst — Daim Ali.</p></footer>
</body></html>
"""


def build_markdown_report(result: dict) -> str:
    lines = [f"# Research: {result.get('question', '')}", ""]
    conf = result.get("confidence") or {}
    lines.append(f"**Confidence:** {conf.get('score', '?')}/100 ({conf.get('level', '')})")
    lines.append("")
    if result.get("status") == "ok":
        lines.append(result.get("answer", ""))
        lines.append("")
        lines.append("## Sources")
        for s in result.get("sources", []):
            lines.append(f"- [{s['id']}] [{s['title']}]({s['url']}) — "
                         f"credibility: {s.get('credibility_tier', '')} "
                         f"({s.get('credibility', 0):.2f})")
    else:
        lines.append(result.get("answer", ""))
    lines += ["", "## Trace"]
    for step in result.get("trace", []):
        lines.append("- `" + str(step.get("step")) + "` — " +
                     ", ".join(f"{k}={v}" for k, v in step.items()
                               if k not in ("t", "step")))
    return "\n".join(lines) + "\n"
