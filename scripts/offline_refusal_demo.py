"""Offline refusal demo — shows the agent's INSUFFICIENT EVIDENCE path.

Runs the real agent pipeline with fake clients whose search returns
nothing, so the agent refuses instead of inventing an answer:

    INSUFFICIENT EVIDENCE: the live search did not return enough usable
    sources to answer this reliably, so no answer was generated.

Exit code 2 (same as the live CLI). No keys, no live APIs.

Run:  python scripts/offline_refusal_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agent import research

QUESTION = "What are the current evidence-based benefits and risks of intermittent fasting?"


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
        if "too little evidence" in sys_msg:  # refinement round
            return FakeMsg('["intermittent fasting benefits randomised trial", '
                           '"intermittent fasting side effects headache fatigue"]')
        # Never reached: refusal happens before any synthesis.
        return FakeMsg("")


class EmptySearch:
    """A search client that finds nothing — the failure case."""

    def search(self, **kw):
        return {"results": []}

    def extract(self, **kw):
        return {"results": []}


def main() -> int:
    result = research(QUESTION, llm=FakeLLM(), search=EmptySearch())
    print(result["answer"])
    print(f"status: {result['status']}")
    print("trace steps:", " -> ".join(s["step"] for s in result["trace"]))
    return 2 if result["status"] == "insufficient_evidence" else 0


if __name__ == "__main__":
    raise SystemExit(main())
