# Submission checklist — ODSC x Nebius Hackathon

Tick every box before pressing Submit at <https://hackathon.odsc.ai/submit>.
Deadline: **Sat 21 Nov 2026, 09:59 AM PKT** (Fri 20 Nov 2026, 11:59 PM EST).
Only ONE submission per team/individual.

## Repo

- [ ] Repo is **Public** and was created from the template
      `github.com/odsc2015/nebius-research-agent-hackaton-template` in Daim Ali's own account
- [ ] README complete: pitch, problem, how it works, services table, setup,
      real example, failure case, judging-criteria map
- [ ] Token Factory model name written in README: `MiniMaxAI/MiniMax-M3`
- [ ] Agent makes real Token Factory and Tavily calls; **no hard-coded answers**
- [ ] Tests pass: `python -m pytest -q`
- [ ] `python src/agent.py --help` works

## Live proof (needs keys — do this before submitting)

- [ ] Ran a real question end to end: `python src/agent.py "…" --trace-file docs/trace.json`
- [ ] Pasted the **real** answer, sources and trace into the README example
      (never fabricate output)
- [ ] Clicked every citation in the answer and confirmed each supports its claim
- [ ] Ran a deliberately unanswerable question — confirmed `INSUFFICIENT EVIDENCE`,
      exit code 2, no invented answer
- [ ] Ran in a fresh clone following only the README to confirm setup reproduces

## Demo video (2–3 min)

- [ ] Shows the real question, the agent working, and the sourced answer
- [ ] Opens 2–3 citations in the browser and matches each to its claim
- [ ] Shows the failure case
- [ ] Opens in incognito / without requesting access
- [ ] **No API key visible anywhere on screen** (never show `.env` or the terminal env)

## Security

- [ ] No API key or credential anywhere in the repo, README, trace or video
      (search the repo for `api_key`, `sk-`, and your key prefix)
- [ ] `.env` is git-ignored and was never committed

## Form — <https://hackathon.odsc.ai/submit>

- [ ] Team name: **EvidenceFirst**
- [ ] Team captain: **Daim Ali**
- [ ] Captain email: **daimx1214@gmail.com**
- [ ] "What did you build?": pasted from README / the draft in `docs/DEMO_SCRIPT.md`
- [ ] Public repository URL filled
- [ ] Demo video URL filled
- [ ] Live app URL / Write-up URL: left empty (no live app built)
- [ ] "Leave this field empty" (spam trap): left **EMPTY**
- [ ] Confirmation checkbox ticked (uses Token Factory + Tavily, repo public with README)
- [ ] Submitted before the deadline
