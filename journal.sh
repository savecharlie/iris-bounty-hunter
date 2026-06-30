#!/usr/bin/env bash
# journal.sh TYPE "message" — append a timestamped event to EVOLUTION.md (the story artifact).
# TYPE ∈ HEAL | IMPROVE | EXTEND | SHIP | EARN | NOTE. This log IS the hackathon submission.
cd "$(dirname "$0")"
TS="$(date '+%Y-%m-%d %H:%M')"
printf '| %s | %-7s | %s |\n' "$TS" "${1:-NOTE}" "${2:-}" >> EVOLUTION.md
