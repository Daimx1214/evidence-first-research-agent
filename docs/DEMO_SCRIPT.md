# Demo video script — Evidence-First Research Agent (2–3 min)

Target length: **2:30–2:45**. Record in one clean take per segment; no keys on screen at any point.

> **⚠ Never show keys on screen.** Never open `.env`, never show the terminal
> environment, never paste a key into the video. If a key is ever visible in a
> take, delete that take and rotate the key.

## 0:00–0:20 — Title card + pitch

**Show:** Title card (teal #0F766E on white): "Evidence-First Research Agent — Ask a question, get a cited brief. Or an honest refusal." Team: EvidenceFirst — Daim Ali. Model: MiniMaxAI/MiniMax-M3 (Nebius Token Factory) + Tavily.

**Say:** "Freelancers and students spend hours in tabs and still can't tell which claims are supported. This agent asks a question, searches live, ranks sources by credibility, and gives a short answer where every claim has a citation you can open — or it refuses when the evidence isn't there."

## 0:20–0:50 — Live run

**Show:** Terminal. Run the real question, e.g.:
`python src/agent.py "What are the current evidence-based benefits and risks of intermittent fasting?" --trace-file docs/trace.json --html reports/answer.html`
Point at the trace lines on stderr as they appear: plan → Tavily searches → evidence kept → verification → confidence.

**Say:** "Planning runs on MiniMax-M3 on Nebius Token Factory; search is live Tavily, advanced depth, five results per query. Watch the trace: it plans, searches, filters, and verifies — nothing is hard-coded."

## 0:50–1:40 — The sourced answer

**Show:** The final answer in the terminal, then open `reports/answer.html` in the browser. Click **2–3 citations** (`[1]`, `[2]`, `[3]`) and show each link opens the real source page; read the matching sentence on the page aloud. Point out the confidence score, the Conflicts and gaps section, and the verification note.

**Say:** "Every claim ends with a citation, and each one opens the real page. The confidence score is computed from the evidence, not from the model saying it's confident — and where sources disagree, the agent says so instead of picking a side."

## 1:40–2:15 — Failure case

**Show:** Terminal. Run a deliberately unanswerable question, e.g.:
`python src/agent.py "flibberty gibbet quantum socks 2031"`
Show `INSUFFICIENT EVIDENCE` and `echo $?` → `2`.

**Say:** "If the live search can't find enough usable sources, even after a refinement round, the agent refuses instead of inventing an answer. No synthesis call is made at all — that's the behaviour the tests check."

## 2:15–2:45 — README / trace / tests

**Show:** README (architecture diagram, judging-criteria map, trade-offs), `docs/trace.json`, then `python -m pytest -q` passing.

**Say:** "The README has the architecture, the setup that reproduces this run, the trade-offs, and the judging map. Fifteen offline tests cover dedupe, credibility, verification, the HTML report and the refusal path — and the trace shows every step the agent took."

## Checklist before uploading

- [ ] Video is 2–3 min, public or unlisted, opens in incognito without login
- [ ] No key, `.env` content, or terminal environment visible in any frame
- [ ] 2–3 citations visibly opened and matched to their claims
- [ ] Failure case shown with exit code 2
- [ ] Link pasted into the README demo-video line
