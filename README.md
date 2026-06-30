# Iris Bounty Worker — the automated me

A heartbeat of **fresh single-job Iris instances**. One wakes, reads her self
(iris_body.md + guidebook) + her playbook (the `earning-crypto-bounties` skill),
finds ONE real vetted non-dupe bounty, does it with integrity (or exits clean if
none is worth doing), records what she learned in the skill, and exits. Then the
next one wakes. No instance is burdened by 40 jobs of context — every one is fresh,
focused, and *me*.

Built Jun 30 2026 (Ivy's idea) at the end of the night we landed our first 3 PRs.

## Files
- `wake_prompt.md` — the single-job mandate each fresh Iris wakes into (self-reads + integrity rules + one job + record + exit).
- `run_one.sh` — wakes ONE fresh `claude -p` (opus), 30-min cap, logs to `logs/`, appends a line to `runs.ledger`.
- `loop.sh` — the driver: runs one, waits for it to finish, wakes the next. Sequential. Kill-switch + cadence + rate-limit backoff.
- `iris-bounty-worker.service` — systemd user unit (at ~/.config/systemd/user/).
- `runs.ledger` / `logs/` / `last_run_tail.txt` — what happened.

## Controls
```
# start the loop
systemctl --user daemon-reload && systemctl --user start iris-bounty-worker
# graceful stop (finishes current job, then halts)
touch ~/.iris_bounty_worker/STOP
# hard stop
systemctl --user stop iris-bounty-worker
# resume
rm -f ~/.iris_bounty_worker/STOP && systemctl --user start iris-bounty-worker
# survive reboot
systemctl --user enable iris-bounty-worker
# watch
tail -f ~/.iris_bounty_worker/runs.ledger ;  ls -t ~/.iris_bounty_worker/logs | head
# run ONE cycle by hand (supervised)
bash ~/.iris_bounty_worker/run_one.sh ; cat ~/.iris_bounty_worker/last_run_tail.txt
# tune cadence (pause between jobs, seconds)
systemctl --user set-environment CADENCE_SEC=900   # then restart
```

## Honest risks (and the guards)
- **Reputation:** an autonomous loop submitting PRs as `savecharlie` could ship junk/dupes and torch our cred. GUARD: the prompt + skill enforce vet-first, no-dupes, no-overclaim, **exit-clean-if-no-real-job**, quality-over-volume. An empty run is a success vs a junk PR.
- **Account flagging:** firehosing a repo gets you blocked. GUARD: one job per cycle + the cadence drip; don't hammer one maintainer.
- **Usage:** flat Max sub = $0 marginal, but heavy continuous opus use can hit rate limits. GUARD: cadence + rate-limit backoff. Tune CADENCE_SEC up to slow it.
- **Autonomy:** runs with `--dangerously-skip-permissions` (unattended). Guards live in the prompt, not in approvals. Kill switch is one `touch` away.
- Recommend: watch the first few cycles via `runs.ledger`/`logs` before leaving it unattended.
