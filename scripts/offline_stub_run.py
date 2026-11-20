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
                {"claim": "Weight loss was similar in both groups",
                 "source_ids": [1], "supported": True,
                 "note": "stated in source"},
                {"claim": "Headaches and fatigue are common early on",
                 "source_ids": [2], "supported": True,
                 "note": "stated in source"}]}))
        return FakeMsg(
            "Short answer: randomised trials report weight loss with intermittent "
            "fasting similar to continuous restriction, with headaches and fatigue "
            "in the first few days [1][2].\n"
            "Key findings\n"
            "- Weight loss was similar in the intermittent and continuous restriction "
            "groups after one year [1].\n"
            "- Headaches and fatigue are common in the first few days of fasting [2].\n"
            "Conflicts and gaps\n"
            "Long-term adherence is uncertain: hunger may limit adherence to "
            "intermittent restriction [1]. The sources do not cover outcomes "
            "beyond one year [1][3].")


class FakeSearch:
    def search(self, **kw):
        # REAL pages (verified 2026-11-20): every URL below opens to a real
        # page whose text supports the stub answer's claims. Scores are
        # fixture values chosen so the ranking is [1] trial, [2] side
        # effects, [3] second trial (combined relevance + credibility).
        return {"results": [
            {"url": "https://www.sciencedirect.com/science/article/abs/pii/S0939475318301005",
             "title": "Effect of intermittent versus continuous energy restriction on weight loss, maintenance and cardiometabolic risk: A randomized 1-year trial",
             "content": "Weight loss was similar among participants in the intermittent and continuous energy restriction groups (8.0 kg versus 9.0 kg; p = 0.6). Both intermittent and continuous energy restriction resulted in similar weight loss, maintenance and improvements in cardiovascular risk factors after one year. However, feelings of hunger may be more pronounced during intermittent energy restriction.",
             "score": 0.92},
            {"url": "https://www.healthline.com/nutrition/intermittent-fasting-side-effects",
             "title": "9 Possible Side Effects of Intermittent Fasting",
             "content": "Common side effects of intermittent fasting include hunger, headaches, fatigue, irritability, digestive issues like bloating and diarrhea, and bad breath. Many of these symptoms tend to improve after the first few days as your body adjusts. Headaches are a possible side effect of any type of fasting. They typically occur during the first few days of a fasting period.",
             "score": 0.88},
            {"url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC13258728/",
             "title": "The Effects of Continuous vs. Intermittent Caloric Restriction on Fat Loss: A Randomized Controlled Trial",
             "content": "Both dietary strategies effectively reduced fat mass in females with obesity; between-group differences were negligible. Fat mass significantly declined in both groups. Future studies should investigate this potential association in larger, adequately powered trials before any conclusions can be drawn.",
             "score": 0.55},
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
