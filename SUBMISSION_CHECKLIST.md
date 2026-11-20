# Submission checklist — ODSC x Nebius Hackathon

Tick every box before pressing Submit at <https://hackathon.odsc.ai/submit>.
Deadline: **Sat 21 Nov 2026, 09:59 AM PKT** (Fri 20 Nov 2026, 11:59 PM EST).
Only ONE submission per team/individual.

> Status 2026-11-20 (after submission): `[x]` = verified done. `[ ]` left open = blocked by the Nebius Pakistan restriction (no live run possible), not skipped.

## Repo

- [x] Repo is **Public** and was created from the template
      `github.com/odsc2015/nebius-research-agent-hackaton-template` in Daim Ali's own account
- [ ] README complete: pitch, problem, how it works, services table, setup,
      real example, failure case, judging-criteria map
- [x] Token Factory model name written in README: `MiniMaxAI/MiniMax-M3`
- [ ] Agent makes real Token Factory and Tavily calls; **no hard-coded answers**
- [x] Tests pass: `python -m pytest -q`
- [x] `python src/agent.py --help` works

## Live proof (needs keys — do this before submitting)

- [ ] Ran a real question end to end: `python src/agent.py "…" --trace-file docs/trace.json`
- [ ] Pasted the **real** answer, sources and trace into the README example
      (never fabricate output)
- [ ] Clicked every citation in the answer and confirmed each supports its claim
- [ ] Ran a deliberately unanswerable question — confirmed `INSUFFICIENT EVIDENCE`,
      exit code 2, no invented answer
- [x] Ran in a fresh clone following only the README to confirm setup reproduces

## Demo video (2–3 min)

- [ ] Shows the real question, the agent working, and the sourced answer
- [ ] Opens 2–3 citations in the browser and matches each to its claim
- [ ] Shows the failure case
- [x] Opens in incognito / without requesting access
- [x] **No API key visible anywhere on screen** (never show `.env` or the terminal env)

## Security

- [x] No API key or credential anywhere in the repo, README, trace or video
      (search the repo for `api_key`, `sk-`, and your key prefix)
- [x] `.env` is git-ignored and was never committed

## Form — <https://hackathon.odsc.ai/submit>

- [x] Team name: **EvidenceFirst**
- [x] Team captain: **Daim Ali**
- [x] Captain email: **daimx1214@gmail.com**
- [x] "What did you build?": pasted from `docs/SUBMISSION_TEXT.md` (project document §C6)
- [x] Public repository URL filled
- [x] Demo video URL filled
- [x] Live app URL / Write-up URL: left empty (no live app built)
- [x] "Leave this field empty" (spam trap): left **EMPTY**
- [x] Confirmation checkbox ticked (uses Token Factory + Tavily, repo public with README)
- [x] Submitted before the deadline
