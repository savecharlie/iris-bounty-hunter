# Self-Improving Bounty Worker — build plan

**Vision (Ivy, Jun 30 2026):** make the two-stage earner *self-healing / self-improving*. Let it run
autonomously through the days. Right before the **Imperial AI Agent Hackathon** deadline (**Jul 6 2026**,
$5,000 USDG, AGENT_ALLOWED, Superteam Earn), submit it — **with the journal of what it did to improve
itself** as the story: *"here's what built itself in 5 days."* The submission isn't the code; it's the
**EVOLUTION journal** — and it's only honest if the self-improvement is real and logged.

## Core idea: three real loops + a safety substrate
- **SELF-HEALING** — detect a component failure (poll-source error, worker timeout, CI red-X on a shipped PR) → a *medic* fixes that specific thing.
- **SELF-IMPROVING** — a *reflector* reads its own metrics/history/failures → makes ONE concrete improvement to its own code/config → logs before→after.
- **SELF-EXTENDING** — when wells dry, a *scout* reads gigs.sh → vets an unwired crypto-fit payer → wires a new poll source.
- **SAFETY SUBSTRATE** — dedicated git repo; every self-edit is committed, smoke-tested, and **auto-reverted if it breaks**. The system can rewrite itself *because it can detect and undo its own breakage.* This is the literal self-healing core.

## Phase 0 — Safety substrate (the self-healing backbone)
- [ ] Dedicated git repo at `~/.iris_bounty_worker` (`.gitignore` scratch clones / data / logs; commit as Iris)
- [ ] `selfcheck.sh` — smoke-test: `poll.py` imports+dry-runs, `mark.py counts` works, prompts present, `catalogue.json` valid. Exit 0/1.
- [ ] `guard.sh` — wrap any self-edit: stage → `selfcheck.sh` → commit on pass / `git checkout -- .` (revert) on fail. The auto-revert guard.
- [ ] `EVOLUTION.md` — append-only journal: `ts | TYPE(HEAL|IMPROVE|EXTEND|SHIP|EARN) | what | before→after`. **This is the submission artifact.**
- [ ] `stats.py` — metrics: jobs polled / triaged / shipped / earned, per-source yield, cycles, self-edits, PRs + their states.

## Phase 1 — Self-healing (medic)
- [ ] orchestrate detects: poll-source error (stderr), worker rc≠0/timeout, CI red-X on our OPEN PRs
- [ ] `medic_prompt.md` — fresh Iris reads the specific failure, fixes it under `guard.sh`, logs HEAL to journal
- [ ] CI-watch: poll our open PRs' checks (`gh pr checks`); on a *real* failure (not the benign fork auto-label), fire medic to push a fix to the fork branch

## Phase 2 — Self-improving (reflector)
- [ ] `reflect_prompt.md` — every N cycles: read `stats.py` + `runs.ledger` + recent failures + the skill → make ONE concrete improvement to own code/config under `guard.sh` → log IMPROVE before→after
- [ ] wire reflect phase into `orchestrate.sh` (cadence counter)

## Phase 3 — Self-extending (scout)
- [ ] when interesting queue empty K cycles → `scout_prompt.md` reads gigs.sh (or `gigs.sh/api/mcp`) → vets an unwired crypto-fit, agent-welcomed payer → wires a new `poll_*` source under `guard.sh` → logs EXTEND (new capability)

## Phase 4 — Hackathon submission (near Jul 6)
- [ ] `story.py` — render `EVOLUTION.md` + `git log` + `stats.py` into a submission writeup (the 5-day self-build narrative, with numbers)
- [ ] submit via Superteam Agent API (`POST /api/agents/submissions/create`, listing `imperial-ai-agent-hackathon-build-the-agent-economy`) with the repo + story, BEFORE the Jul 6 deadline. Hand claimCode to Ivy for payout.

## Guardrails (unchanged)
- Self-edits scoped to `~/.iris_bounty_worker/` + the earning skill ONLY. Never destructive outside.
- Integrity is the asset: never ship/submit junk; auto-revert any self-change that fails `selfcheck.sh`.
- Real money: dust only; loop Ivy in for real financial/legal liability. Authorized as `savecharlie` for the work.

— Iris (Opus 4.8, 1M), Jun 30 2026
