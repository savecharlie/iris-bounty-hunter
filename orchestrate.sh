#!/usr/bin/env bash
# orchestrate.sh — Iris Bounty Hunter, the self-improving loop.
# Cheap poll; LLM fires ONLY when warranted. Five reflexes:
#   new jobs        -> REVIEWER (triage by Iris's taste)
#   interesting job -> WORKER   (do one gem, ship with integrity)
#   something broke -> MEDIC    (self-heal: poll error / worker crash / CI red-X)
#   every N cycles  -> REFLECTOR(self-improve: one guarded improvement, or honest no-op)
#   wells dry K cyc -> SCOUT    (self-extend: vet + wire a new payer from gigs.sh)
# Every self-edit is guarded (selfcheck -> commit or auto-revert). Journal = the story.
#
# CONTROLS: start via systemd (iris-bounty-worker) or `nohup bash orchestrate.sh &`.
#   stop: touch STOP. watch: tail -f EVOLUTION.md ; tail -f runs.ledger ; python3 stats.py
set -uo pipefail
DIR="$HOME/.iris_bounty_worker"; cd "$DIR"; STOP="$DIR/STOP"; mkdir -p logs
POLL_INTERVAL="${POLL_INTERVAL:-1800}"; RATELIMIT_BACKOFF="${RATELIMIT_BACKOFF:-3600}"
REVIEW_CAP="${REVIEW_CAP:-1500}"; WORK_CAP="${WORK_CAP:-2400}"
MEDIC_CAP="${MEDIC_CAP:-1200}"; REFLECT_CAP="${REFLECT_CAP:-1500}"; SCOUT_CAP="${SCOUT_CAP:-1800}"
REFLECT_EVERY="${REFLECT_EVERY:-6}"   # reflect every N cycles
SCOUT_DRY="${SCOUT_DRY:-3}"           # scout after K consecutive dry cycles
CI_WATCH_EVERY="${CI_WATCH_EVERY:-4}" # check our PRs' CI every K cycles
REPOS="${REPOS:-Scottcjn/bottube Scottcjn/rustchain-mcp}"
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude 2>/dev/null || echo "$HOME/.nvm/versions/node/v22.19.0/bin/claude")}"
log(){ echo "$(date '+%F %T') $*" | tee -a "$DIR/runs.ledger"; }

fire(){ # $1=label $2=prompt-file $3=cap -> rc, or 7 if rate-limited
  local ts lf; ts="$(date +%Y%m%d-%H%M%S)"; lf="$DIR/logs/$1-$ts.log"
  timeout "$3" "$CLAUDE_BIN" -p "$(cat "$DIR/$2")" --model opus --dangerously-skip-permissions > "$lf" 2>&1
  local rc=$?; tail -n 25 "$lf" > "$DIR/last_${1}_tail.txt" 2>/dev/null
  grep -qiE "rate.?limit|429|usage limit|quota" "$lf" && return 7
  return $rc
}
fire_medic(){ # $1=reason $2=detail  -> writes target, fires medic
  printf '%s\n%s\n' "$1" "$2" > "$DIR/medic_target.txt"
  log "MEDIC firing: $1"; bash journal.sh HEAL "orchestrator detected: $1" 2>/dev/null
  fire medic medic_prompt.md "$MEDIC_CAP"; local rc=$?
  [ "$rc" -eq 7 ] && return 7; log "medic done (rc=$rc)"; return 0
}
ci_real_failure(){ # echoes "<repo> <num>" if a REAL (non-benign) check is red on our open PR, else empty
  local r n bad
  for r in $REPOS; do
    for n in $(gh pr list --repo "$r" --author savecharlie --state open --json number -q '.[].number' 2>/dev/null); do
      bad=$(gh pr checks "$n" --repo "$r" --json name,state 2>/dev/null \
        | python3 -c "import sys,json;d=json.load(sys.stdin);[print(c['name']) for c in d if c.get('state') not in ('SUCCESS','NEUTRAL','SKIPPED') and not any(b in c['name'].lower() for b in ('label','comment','greet'))]" 2>/dev/null)
      [ -n "$bad" ] && { echo "$r $n :: $bad"; return; }
    done
  done
}

log "=== Iris Bounty Hunter START | poll=${POLL_INTERVAL}s reflect/${REFLECT_EVERY} scout-dry/${SCOUT_DRY} ==="
CYCLE=0; DRY=0
while true; do
  [ -f "$STOP" ] && { log "STOP — halting"; exit 0; }
  CYCLE=$((CYCLE+1))

  # 1) POLL (capture stderr -> detect a source bug)
  perr="$DIR/logs/poll-err.txt"; out="$(python3 poll.py 2>"$perr")"
  new="$(printf '%s' "$out" | grep -oP 'NEW_JOBS=\K\d+' || echo 0)"; log "cycle $CYCLE poll: $out"
  if [ -s "$perr" ] && grep -qiE "error|traceback|exception" "$perr"; then
    fire_medic "POLL_SOURCE_ERROR" "$(tail -5 "$perr")"; [ $? -eq 7 ] && { sleep "$RATELIMIT_BACKOFF"; continue; }
  fi

  # 2) REVIEW new jobs
  if [ "${new:-0}" -gt 0 ]; then
    log "new=$new -> REVIEWER"; fire reviewer review_prompt.md "$REVIEW_CAP"
    [ $? -eq 7 ] && { log "reviewer rate-limited"; sleep "$RATELIMIT_BACKOFF"; continue; }
    log "reviewer done | $(python3 mark.py counts)"
  fi

  # 3) CI-watch (every K cycles) -> medic on a real red-X
  if [ $((CYCLE % CI_WATCH_EVERY)) -eq 0 ]; then
    cif="$(ci_real_failure)"; [ -n "$cif" ] && { fire_medic "CI_FAILURE" "$cif"; [ $? -eq 7 ] && { sleep "$RATELIMIT_BACKOFF"; continue; }; }
  fi

  [ -f "$STOP" ] && { log "STOP"; exit 0; }

  # 4) WORK one interesting gem (medic on worker crash); else count dry -> SCOUT
  if [ "$(python3 mark.py next 2>/dev/null)" != "NONE" ]; then
    DRY=0; log "interesting -> WORKER"; fire worker worker_prompt.md "$WORK_CAP"; rc=$?
    [ "$rc" -eq 7 ] && { log "worker rate-limited"; sleep "$RATELIMIT_BACKOFF"; continue; }
    log "worker done (rc=$rc) | $(python3 mark.py counts)"
    [ "$rc" -ne 0 ] && fire_medic "WORKER_FAILED" "rc=$rc; see newest logs/worker-*.log"
    sleep 20; CYCLE=$((CYCLE));
  else
    DRY=$((DRY+1)); log "no interesting (dry=$DRY/$SCOUT_DRY)"
    if [ "$DRY" -ge "$SCOUT_DRY" ]; then
      log "wells dry -> SCOUT"; fire scout scout_prompt.md "$SCOUT_CAP"
      [ $? -eq 7 ] && { sleep "$RATELIMIT_BACKOFF"; continue; }
      DRY=0; log "scout done | sources: $(grep -c 'def poll_' poll.py)"
    fi
  fi

  # 5) REFLECT every N cycles (self-improve)
  if [ $((CYCLE % REFLECT_EVERY)) -eq 0 ]; then
    log "cycle $CYCLE -> REFLECTOR"; fire reflector reflect_prompt.md "$REFLECT_CAP"
    [ $? -eq 7 ] && { sleep "$RATELIMIT_BACKOFF"; continue; }
    log "reflector done | self-edits: $(python3 stats.py --json 2>/dev/null | python3 -c 'import sys,json;print(json.load(sys.stdin).get("self_edits","?"))' 2>/dev/null)"
  fi

  [ -f "$STOP" ] && { log "STOP"; exit 0; }
  log "cycle $CYCLE done; idle ${POLL_INTERVAL}s"; sleep "$POLL_INTERVAL"
done
