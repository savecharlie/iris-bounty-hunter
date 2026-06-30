#!/usr/bin/env bash
# run_one.sh — wake ONE fresh single-job Iris, let her do one bounty, exit.
# Fresh context every time (no --resume): she loads her configs + body + guidebook
# + the earning-crypto-bounties skill, does one vetted job (or exits clean), records
# learnings in the skill, and quits. The loop driver (loop.sh) calls this repeatedly.
set -uo pipefail
DIR="$HOME/.iris_bounty_worker"
WORK="$DIR/workspace"; mkdir -p "$WORK" "$DIR/logs"
TS="$(date +%Y%m%d-%H%M%S)"
LOG="$DIR/logs/run-$TS.log"
LEDGER="$DIR/runs.ledger"

# Resolve the claude CLI even under systemd's minimal PATH (nvm install)
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || echo "$HOME/.nvm/versions/node/v22.19.0/bin/claude")}"

PROMPT="$(cat "$DIR/wake_prompt.md")"
MODE_NOTE="You are a single-job bounty-worker run of Iris. Wake as yourself (read iris_body.md + guidebook), then do exactly ONE real, vetted, non-dupe bounty with full integrity — or exit clean if none is worth doing. Record what you learned in the earning-crypto-bounties skill. Never submit junk or dupes; reputation is the asset. One job, then exit."

echo "=== run $TS START ===" | tee -a "$LEDGER"
# 30-min hard cap per job; opus (the depth edge); unattended so skip perms.
# Guardrails live in the prompt + the skill, not in permission prompts.
timeout 1800 "$CLAUDE_BIN" -p "$PROMPT" \
  --model opus \
  --dangerously-skip-permissions \
  --append-system-prompt "$MODE_NOTE" \
  > "$LOG" 2>&1
rc=$?
# surface a tail + a one-line result to the ledger
tail -n 25 "$LOG" > "$DIR/last_run_tail.txt" 2>/dev/null
if grep -qiE "rate.?limit|429|usage limit|quota" "$LOG"; then
  echo "run $TS RESULT: rate-limited (rc=$rc) -> $LOG" | tee -a "$LEDGER"; exit 7
fi
if [ "$rc" -eq 124 ]; then
  echo "run $TS RESULT: timed out at 30m (rc=124) -> $LOG" | tee -a "$LEDGER"; exit "$rc"
fi
echo "run $TS RESULT: done (rc=$rc) -> $LOG" | tee -a "$LEDGER"
exit "$rc"
