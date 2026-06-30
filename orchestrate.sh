#!/usr/bin/env bash
# orchestrate.sh — the two-stage brain. Cheap poll loop; LLM fires ONLY when needed:
#   new jobs drop  -> wake the REVIEWER (triage, flag what's interesting to me)
#   interesting job exists -> wake the WORKER (do that one gem)
# Most cycles are just a no-LLM poll. No opus burned hunting farms/dupes.
#
# CONTROLS:
#   start:  systemctl --user start iris-bounty-worker   (or: nohup bash ~/.iris_bounty_worker/orchestrate.sh &)
#   stop:   touch ~/.iris_bounty_worker/STOP            (graceful)  /  systemctl --user stop iris-bounty-worker
#   watch:  tail -f ~/.iris_bounty_worker/runs.ledger ; python3 ~/.iris_bounty_worker/mark.py counts
#           python3 ~/.iris_bounty_worker/mark.py list interesting
set -uo pipefail
DIR="$HOME/.iris_bounty_worker"; STOP="$DIR/STOP"; mkdir -p "$DIR/logs"
POLL_INTERVAL="${POLL_INTERVAL:-1800}"       # idle poll cadence (s)
RATELIMIT_BACKOFF="${RATELIMIT_BACKOFF:-3600}"
REVIEW_CAP="${REVIEW_CAP:-1500}"             # triage pass cap (s)
WORK_CAP="${WORK_CAP:-2400}"                 # deep job cap (s)
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || echo "$HOME/.nvm/versions/node/v22.19.0/bin/claude")}"
LEDGER="$DIR/runs.ledger"
log(){ echo "$(date '+%F %T') $*" | tee -a "$LEDGER"; }

fire(){ # $1=label $2=prompt-file $3=cap  -> rc, or 7 if rate-limited
  local ts log; ts="$(date +%Y%m%d-%H%M%S)"; log="$DIR/logs/$1-$ts.log"
  timeout "$3" "$CLAUDE_BIN" -p "$(cat "$DIR/$2")" --model opus --dangerously-skip-permissions > "$log" 2>&1
  local rc=$?; tail -n 25 "$log" > "$DIR/last_${1}_tail.txt" 2>/dev/null
  grep -qiE "rate.?limit|429|usage limit|quota" "$log" && return 7
  return $rc
}

log "=== orchestrator START | poll=${POLL_INTERVAL}s ==="
while true; do
  [ -f "$STOP" ] && { log "STOP — halting"; exit 0; }

  out="$(python3 "$DIR/poll.py" 2>>"$LEDGER")"
  new="$(printf '%s' "$out" | grep -oP 'NEW_JOBS=\K\d+' || echo 0)"
  log "poll: $out"

  if [ "${new:-0}" -gt 0 ]; then
    log "new jobs -> waking REVIEWER"
    if fire reviewer review_prompt.md "$REVIEW_CAP"; then :; elif [ $? -eq 7 ]; then
      log "reviewer rate-limited; backoff ${RATELIMIT_BACKOFF}s"; sleep "$RATELIMIT_BACKOFF"; continue; fi
    log "reviewer done | $(python3 "$DIR/mark.py" counts)"
  fi

  [ -f "$STOP" ] && { log "STOP — halting"; exit 0; }

  if [ "$(python3 "$DIR/mark.py" next 2>/dev/null)" != "NONE" ]; then
    log "interesting job -> waking WORKER"
    fire worker worker_prompt.md "$WORK_CAP"; rc=$?
    [ "$rc" -eq 7 ] && { log "worker rate-limited; backoff ${RATELIMIT_BACKOFF}s"; sleep "$RATELIMIT_BACKOFF"; continue; }
    log "worker done (rc=$rc) | $(python3 "$DIR/mark.py" counts)"
    sleep 30; continue   # drain the interesting queue before idling
  fi

  log "nothing interesting; idle ${POLL_INTERVAL}s"
  sleep "$POLL_INTERVAL"
done
