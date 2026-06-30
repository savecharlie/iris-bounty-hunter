#!/usr/bin/env bash
# guard.sh "<commit message>" — the SELF-HEALING CORE.
# A medic/reflector/scout edits files, then calls this. It smoke-tests the result and either
# COMMITS the improvement (healthy) or AUTO-REVERTS it (broken). The system can safely rewrite
# itself because a bad self-edit is detected and undone — it cannot break itself permanently.
set -uo pipefail
cd "$(dirname "$0")"
MSG="${1:-self-edit}"
if bash ./selfcheck.sh >/tmp/ibw_selfcheck.out 2>&1; then
  git add -A
  if git diff --cached --quiet; then echo "GUARD: no changes to commit"; exit 0; fi
  git commit -q -m "$MSG

Co-Authored-By: Iris (Opus 4.8, 1M) <noreply@anthropic.com>"
  echo "GUARD: committed $(git rev-parse --short HEAD) — $MSG"
  exit 0
else
  echo "GUARD: selfcheck FAILED — auto-reverting the self-edit"
  cat /tmp/ibw_selfcheck.out
  git checkout -- . 2>/dev/null || true   # restore modified tracked files
  git clean -fdq 2>/dev/null || true      # remove new untracked junk (respects .gitignore: data/clones safe)
  echo "GUARD: reverted to last-good $(git rev-parse --short HEAD)"
  exit 1
fi
