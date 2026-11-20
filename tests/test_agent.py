"""Offline tests for the Evidence-First Research Agent.

No API keys needed: every test uses fake LLM / Tavily clients.
Run:  python -m pytest -q
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import agent
from report import build_html_report, build_markdown_report


class FakeMsg:
    """Mimics the openai response shape."""

    def __init__(self, text):
        self.choices = [type("C", (), {
            "message": type("M", (), {"content": text})()})()]


class FakeLLM:
    """Routes by system prompt: plan / refine / verify / synthesis."""

    def __init__(self, synth="Answer [1][2].", verify_json=None):
        self.synth = synth
        self.verify_json = verify_json
        self.calls = 0
        self.call_kinds = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kw):
        self.calls += 1
        sys_msg = kw["messages"][0]["content"]
        if "plan web research" in sys_msg:
            self.call_kinds.append("plan")
            return FakeMsg('["q one", "q two"]')
        if "too little evidence" in sys_msg:
            self.call_kinds.append("refine")
            return FakeMsg('["q refined"]')
        if "verify a draft" in sys_msg:
            self.call_kinds.append("verify")
            payload = self.verify_json or {
                "checks": [{"claim": "Answer", "source_ids": [1],
                            "supported": True, "note": "in source"}]}
            return FakeMsg(json.dumps(payload))
        self.call_kinds.append("synth")
        return FakeMsg(self.synth)


class FakeSearch:
    def __init__(self, results):
        self.results = results

    def search(self, **kw):
        return {"results": self.results}


class FakeSearchWithExtract(FakeSearch):
    def __init__(self, results, extracted_text="E" * 900):
        super().__init__(results)
        self.extracted_text = extracted_text

    def extract(self, **kw):
        return {"results": [{"raw_content": self.extracted_text}]}


class FakeSearchBrokenExtract(FakeSearch):
    def extract(self, **kw):
        raise RuntimeError("extract down")


def hit(i, url=None, score=0.9, content=None):
    return {"url": url or f"https://site{i}.org/a",
            "title": f"T{i}",
            "content": content if content is not None else "x" * 80,
            "score": score}


# ---------------------------------------------------------------- selection
def test_dedupe_and_domain_cap():
    raw = [hit(1), hit(1, "https://www.site1.org/a/?utm_source=x"),
           hit(2, "https://a.com/1"), hit(3, "https://a.com/2"),
           hit(4, "https://a.com/3")]
    s = agent.select_evidence(raw)
    urls = [x.url for x in s]
    assert sum("a.com" in u for u in urls) == agent.MAX_PER_DOMAIN
    assert sum("site1.org" in u for u in urls) == 1


def test_normalize_url_strips_tracking_params():
    assert agent.normalize_url(
        "https://WWW.Example.com/page/?utm_source=x&fbclid=1&q=keep") == \
        "https://example.com/page?q=keep"


def test_weak_score_drop():
    raw = [hit(1, score=0.1), hit(2, score=0.9), hit(3, score=0.05)]
    s = agent.select_evidence(raw)
    assert [x.url for x in s] == ["https://site2.org/a"]


def test_credibility_prefers_edu_gov_over_spam():
    raw = [hit(1, url="https://best-deals-top10.xyz/a", score=0.95),
           hit(2, url="https://www.stanford.edu/research", score=0.5),
           hit(3, url="https://www.nih.gov/health", score=0.5)]
    s = agent.select_evidence(raw)
    assert s[0].url.startswith("https://www.stanford.edu") or \
        s[0].url.startswith("https://www.nih.gov")
    edu = [x for x in s if ".edu" in x.url][0]
    spam = [x for x in s if ".xyz" in x.url][0]
    assert edu.credibility > spam.credibility
    assert edu.credibility_tier == "high" and spam.credibility_tier == "low"


def test_credibility_score_values():
    score, tier, _ = agent.credibility_score("https://mit.edu/x")
    assert tier == "high" and score >= 0.9
    score, tier, _ = agent.credibility_score("https://docs.python.org/3/")
    assert tier == "high"
    score, tier, _ = agent.credibility_score("https://cheap-miracle.xyz/a")
    assert tier == "low" and score <= 0.25


# ---------------------------------------------------------------- citations
def test_invalid_citation_removed():
    srcs = [agent.Source(1, "t", "u", "c", 1.0)]
    out, rep = agent.verify_citations("Claim one [1]. Claim two [9].", srcs)
    assert "[9]" not in out and "[1]" in out
    assert rep["invalid_citations_removed"] == [9]


# ---------------------------------------------------------------- end to end
def test_end_to_end_ok_with_fakes():
    res = agent.research("q", FakeLLM("Answer [1][2]. Hallucinated [7]."),
                         FakeSearch([hit(1), hit(2), hit(3)]))
    assert res["status"] == "ok"
    assert "[7]" not in res["answer"]
    assert res["sources_text"].count("http") == 2
    assert res["confidence"]["score"] > 0
    assert res["confidence"]["level"] in ("high", "medium", "low")
    assert "verify" in res["verification"]["status"] or \
        res["verification"]["status"] == "verified"


def test_empty_results_refuses_without_synthesis():
    llm = FakeLLM("should not be used")
    res = agent.research("q", llm, FakeSearch([]))
    assert res["status"] == "insufficient_evidence"
    assert "INSUFFICIENT EVIDENCE" in res["answer"]
    assert res["sources"] == []
    assert llm.calls == 2  # plan + refine only, no synthesis, no verify
    assert "synth" not in llm.call_kinds and "verify" not in llm.call_kinds


def test_search_tool_failure_is_handled():
    class Boom:
        def search(self, **kw):
            raise RuntimeError("down")

    res = agent.research("q", FakeLLM("x"), Boom())
    assert res["status"] == "insufficient_evidence"


def test_verification_pass_flags_unsupported_claim():
    verify_json = {"checks": [
        {"claim": "Vitamin X cures everything", "source_ids": [1],
         "supported": False, "note": "source never says this"},
        {"claim": "Study ran in 2024", "source_ids": [2],
         "supported": True, "note": "stated in source"}]}
    res = agent.research("q", FakeLLM("Vitamin X cures everything [1]. Study ran in 2024 [2].",
                                      verify_json=verify_json),
                         FakeSearch([hit(1), hit(2), hit(3)]))
    assert res["status"] == "ok"
    assert res["verification"]["unsupported"] == 1
    assert res["verification"]["supported"] == 1
    assert "Vitamin X cures everything" in \
        res["verification"]["unsupported_claims"][0]["claim"]
    assert "Verification note" in res["answer"]


def test_extract_enriches_thin_snippets_and_failure_never_breaks():
    thin = hit(1, content="short " * 10)  # 60 chars < 600 -> extract runs
    res = agent.research("q", FakeLLM("Answer [1][2]."),
                         FakeSearchWithExtract([thin, hit(2), hit(3)]))
    assert res["status"] == "ok"
    assert res["sources"][0]["extracted"] is True
    assert len(res["sources"][0]["content"]) > 100
    # Broken extract must not break the run.
    res2 = agent.research("q", FakeLLM("Answer [1][2]."),
                          FakeSearchBrokenExtract([thin, hit(2), hit(3)]))
    assert res2["status"] == "ok"


def test_refusal_exit_code_is_two(monkeypatch):
    monkeypatch.setattr(agent, "get_llm", lambda: FakeLLM("x"))
    monkeypatch.setattr(agent, "get_search", lambda: FakeSearch([]))
    assert agent.main(["some unanswerable nonsense question"]) == 2


def test_help_exits_zero():
    try:
        agent.main(["--help"])
    except SystemExit as e:
        assert e.code == 0
    else:
        raise AssertionError("--help should exit via argparse")


# ---------------------------------------------------------------- reports
def test_html_report_contains_citations_and_sources():
    res = agent.research("q", FakeLLM("Answer [1][2]."),
                         FakeSearch([hit(1), hit(2), hit(3)]))
    html_out = build_html_report(res)
    assert "[1]" in html_out and "site1.org" in html_out
    assert "https://site2.org/a" in html_out
    assert "Confidence" in html_out
    assert "#0F766E" in html_out  # teal palette
    assert "Research trace" in html_out


def test_markdown_report_and_conflicts_gaps():
    res = agent.research(
        "q",
        FakeLLM("Short answer [1].\nKey findings\n- Finding one [1].\n"
                "Conflicts and gaps\nSources disagree on dosage [1][2]."),
        FakeSearch([hit(1), hit(2), hit(3)]))
    assert res["status"] == "ok"
    assert "dosage" in res["conflicts_gaps"]
    md = build_markdown_report(res)
    assert "# Research: q" in md and "site1.org" in md
