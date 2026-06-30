#!/usr/bin/env bash
# loop.sh — the heartbeat. One fresh Iris finishes, the next wakes. Forever, until stopped.
# Sequential by construction: run_one.sh BLOCKS until that job's Iris exits, then we wake the next.
#
# CONTROLS:
#   start:  systemctl --user start iris-bounty-worker      (or: nohup bash ~/.iris_bounty_worker/loop.sh &)
#   stop:   touch ~/.iris_bounty_worker/STOP               (graceful: finishes current job, then halts)
#           systemctl --user stop iris-bounty-worker       (hard stop)
#   resume: rm ~/.iris_bounty_worker/STOP ; (re)start
#   tune:   CADENCE_SEC=900 systemctl ... (pause between jobs; default 300s)
#   watch:  tail -f ~/.iris_bounty_worker/runs.ledger   /   ls -t ~/.iris_bounty_worker/logs | head
set -uo pipefail
DIR="$HOME/.iris_bounty_worker"
STOP="$DIR/STOP"
CADENCE_SEC="${CADENCE_SEC:-300}"          # pause between jobs (a drip, not a firehose)
RATELIMIT_BACKOFF="${RATELIMIT_BACKOFF:-3600}"  # back off ~1h if usage-limited
LEDGER="$DIR/runs.ledger"

echo "=== loop START $(date '+%F %T') | cadence=${CADENCE_SEC}s ===" | tee -a "$LEDGER"
while true; do
  if [ -f "$STOP" ]; then
    echo "=== STOP file present — halting $(date '+%F %T') ===" | tee -a "$LEDGER"; exit 0
  fi
  bash "$DIR/run_one.sh"
  rc=$?
  if [ "$rc" -eq 7 ]; then
    echo "loop: rate-limited, backing off ${RATELIMIT_BACKOFF}s" | tee -a "$LEDGER"
    sleep "$RATELIMIT_BACKOFF"; continue
  fi
  # graceful stop check again (job may have run long)
  [ -f "$STOP" ] && { echo "=== STOP after job — halting ===" | tee -a "$LEDGER"; exit 0; }
  sleep "$CADENCE_SEC"
done
