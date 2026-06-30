#!/usr/bin/env bash
# selfcheck.sh — smoke-test the system. Exit 0 = healthy, 1 = broken.
# Run after ANY self-edit; guard.sh uses this to decide commit vs auto-revert.
set -uo pipefail
cd "$(dirname "$0")"
fail(){ echo "SELFCHECK FAIL: $*"; exit 1; }

# 1. every python file compiles
for f in *.py; do python3 -m py_compile "$f" 2>/dev/null || fail "py_compile $f"; done
# 2. poll.py loads cleanly (catches syntax/import errors at module load)
python3 -c "import importlib.util as u; s=u.spec_from_file_location('poll','poll.py'); m=u.module_from_spec(s); s.loader.exec_module(m)" 2>/dev/null || fail "poll.py import"
# 3. mark.py runs
python3 mark.py counts >/dev/null 2>&1 || fail "mark.py counts"
# 4. catalogue is valid JSON if present
[ -f catalogue.json ] && { python3 -c "import json;json.load(open('catalogue.json'))" 2>/dev/null || fail "catalogue.json invalid"; }
# 5. required components present
for p in poll.py mark.py orchestrate.sh review_prompt.md worker_prompt.md; do
  [ -f "$p" ] || fail "missing $p"
done
echo "SELFCHECK OK"
