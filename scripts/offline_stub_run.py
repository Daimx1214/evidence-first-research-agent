"""Offline stub run — proves the pipeline end to end WITHOUT keys or live APIs.

Uses fake LLM + fake Tavily clients (same fakes as the tests) and writes
docs/trace.example.json plus a sample HTML report to reports/stub-answer.html.
The output is clearly labelled EXAMPLE — it is not a live run and must never
be presented as one.

Run:  python scripts/offline_stub_run.py
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import agent
from report import build_html_report


class FakeMsg:
    def __init__(self, text):
        self.choices = [type("C", (), {
            "message": type("M", (), {"content": text})()})()]


class FakeLLM:
    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kw):
        sys_msg = kw["messages"][0]["content"]
        if "plan web research" in sys_msg:
            return FakeMsg('["intermittent fasting benefits evidence", '
                           '"intermittent fasting risks side effects", '
                           '"intermittent fasting randomised trial 2024"]')
        if "verify a draft" in sys_msg:
            return FakeMsg(json.dumps({"checks": [
                {"claim": "Trials report modest weight loss",
                 "source_ids": [1], "supported": True,
                 "note": "stated in source"},
                {"claim": "Risks include headaches in some people",
                 "source_ids": [2], "supported": True,
                 "note": "stated in source"}]}))
        return FakeMsg(
            "Short answer: randomised trials report modest weight loss with "
            "intermittent fasting, with some side effects [1][2].\n"
            "Key findings\n"
            "- Trials report modest weight loss versus continuous restriction [1].\n"
            "- Some people report headaches and fatigue early on [2].\n"
            "Conflicts and gaps\n"
            "Sources disagree on long-term adherence; no long-term trial in the sources [1][2].")


class FakeSearch:
    def search(self, **kw):
        return {"results": [
            {"url": "https://www.nih.gov/news/fasting-trial",
             "title": "NIH — Intermittent fasting trial results",
             "content": "Randomised trials report modest weight loss with intermittent fasting. " * 3,
             "score": 0.92},
            {"url": "https://www.nature.com/articles/fasting-review",
             "title": "Nature — Fasting review",
             "content": "Some people report headaches and fatigue early on during fasting. " * 3,
             "score": 0.88},
            {"url": "https://www.bbc.com/news/health-fasting",
             "title": "BBC — Fasting: what the evidence says",
             "content": "Sources disagree on long-term adherence to fasting regimes. " * 3,
             "score": 0.81},
        ]}

    def extract(self, **kw):
        return {"results": [{"raw_content":
                             "Full extracted page text about the fasting trial. " * 40}]}


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    result = agent.research(
        "What are the current evidence-based benefits and risks of intermittent fasting?",
        FakeLLM(), FakeSearch())
    result["note"] = ("EXAMPLE ONLY — produced by scripts/offline_stub_run.py "
                      "with fake LLM/Tavily clients. NOT a live run.")
    trace_path = root / "docs" / "trace.example.json"
    trace_path.write_text(json.dumps(
        {"note": result["note"], "trace": result["trace"],
         "confidence": result["confidence"],
         "verification": result["verification"]}, indent=2))
    html_path = root / "reports" / "stub-answer.html"
    html_path.parent.mkdir(exist_ok=True)
    html_path.write_text(build_html_report(result))
    print(f"status: {result['status']}")
    print(f"confidence: {result['confidence']}")
    print(f"trace: {trace_path}")
    print(f"html:  {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
