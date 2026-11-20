# Demo video recording checklist (2–3 minutes)

Record this **only after a Nebius Token Factory key exists** (`.env` has both
`NEBIUS_API_KEY` and `TAVILY_API_KEY`). Never show keys on screen: do not open
`.env`, do not `cat` it, do not show the Tavily/Nebius dashboards, and keep the
terminal clear of any pasted key. Check the recording afterwards in incognito
before uploading.

## Prep

1. `cd evidence-first-research-agent`
2. Activate the venv: `source .venv/bin/activate` (or create one: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`)
3. Confirm keys are set without printing them: `python src/agent.py --help` (must exit 0)
4. Pick one strong, factual, source-rich question, e.g. `"What are the current evidence-based benefits and risks of intermittent fasting?"`

## Recording order (matches `docs/DEMO_SCRIPT.md`, ~2:30–2:45 total)

| Time | Do | Show / say |
| --- | --- | --- |
| 0:00–0:20 | Title card + pitch on screen | Who the user is (freelancer/student) and what question the agent answers. |
| 0:20–0:50 | Run the real question live: `python src/agent.py "<question>" --trace-file docs/trace.json --html reports/answer.html` | Plan appears; Tavily searches run live; point out the model name `MiniMaxAI/MiniMax-M3` on Token Factory. Do not cut away — the run takes ~1–2 min; keep the trace lines visible. |
| 0:50–1:40 | Show the final answer + `reports/answer.html` | Open **2–3 citations in the browser** and show each one actually supports its claim. Point out the `Inference:` label and the Conflicts and gaps section. |
| 1:40–2:15 | Failure case, live: `python src/agent.py "flibberty gibbet quantum socks 2031"` | Show `INSUFFICIENT EVIDENCE` and exit code 2 (`echo $?`) — no invented answer. |
| 2:15–2:45 | README, trace + tests on screen: `python -m pytest -q` | Architecture diagram, trade-offs, judging-criteria map; tests passing (15/15). |

## After recording

1. Watch the whole video once: no key, password or `.env` content visible anywhere.
2. Upload as **public or unlisted** (must open in incognito without login or an access request).
3. Paste the link into the README (`Demo video` line) and into `docs/SUBMISSION_TEXT.md` (Demo video URL), replacing the `TO ADD` placeholders.
4. Paste the real answer, sources and confidence score from this run into the README Example section, and the real trace into `docs/trace.json`.
