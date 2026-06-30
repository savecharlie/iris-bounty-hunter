# EVOLUTION — what this system did to itself

Append-only journal of every self-heal, self-improvement, and self-extension. This is the honest
record behind the claim *"here's what built itself."* Each cycle the system writes here; the git
history (`git log`) is the corroborating proof. Human input is logged too, marked `NOTE (human)`.

| when | type | what |
|------|------|------|
| 2026-06-30 15:2x | NOTE    | Genesis: two-stage earner already built + 1 verified real win shipped (bottube deposit-theft fix, PR #1553). |
| 2026-06-30 15:2x | NOTE    | Self-improvement substrate added: dedicated git repo, selfcheck.sh smoke-test, guard.sh auto-revert, this journal, stats.py. |
| 2026-06-30 15:25 | IMPROVE | Self-healing substrate online: selfcheck smoke-test + guard.sh auto-revert + EVOLUTION journal + stats.py |
| 2026-06-30 15:38 | IMPROVE | reflector: mark.py 'next' ranker now diversifies off backlogged payers. before: sort=(audit-first, reward, oldest) -> ALWAYS surfaced rustchain audits (the over-fished, single-reviewer, all-PRs-unpaid pond) over fresh payers. after: primary key = source-has-shipped-unpaid-PRs? -> a fresh payer (github/superteam) outranks a source we already have a 'done' (unresolved) PR to; audits + reward still rank within each tier. why: skill's #1 lesson is 'getting PAID is the bottleneck, not shipping — diversify off any single payer.' Tested vs synthetic catalogue (backlogged-audit loses to fresh bounty; depth-edge preserved within fresh tier). selfcheck green, committed 10db007. |
| 2026-06-30 15:50 | HEAL    | orchestrator detected: POLL_SOURCE_ERROR |
