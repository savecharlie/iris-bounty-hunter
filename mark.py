#!/usr/bin/env python3
"""mark.py — the catalogue CLI. Clean, atomic reads/updates so agents never
hand-edit the JSON.

  python3 mark.py set <id> <status> [why...]   # status: interesting|skip|farm|dupe|doing|done|failed
  python3 mark.py list [status]                # list ids (optionally filtered); default: all
  python3 mark.py get <id>                      # print one job as JSON
  python3 mark.py next                          # print the single best 'interesting' job to do next (JSON), or NONE
  python3 mark.py counts                         # status histogram
"""
import json, os, sys, time
CAT = os.path.expanduser("~/.iris_bounty_worker/catalogue.json")

def load():
    return json.load(open(CAT)) if os.path.exists(CAT) else {"jobs": {}}
def save(d):
    tmp = CAT + ".tmp"; json.dump(d, open(tmp, "w"), indent=2); os.replace(tmp, CAT)

def reward_num(j):
    import re
    m = re.search(r"(\d[\d,\.]*)", j.get("reward", "") or "")
    return float(m.group(1).replace(",", "")) if m else 0.0

def main():
    a = sys.argv[1:]
    if not a: print(__doc__); return
    d = load(); jobs = d["jobs"]
    cmd = a[0]
    if cmd == "set":
        jid, status = a[1], a[2]; why = " ".join(a[3:])
        if jid not in jobs: print(f"NO_SUCH_JOB {jid}"); sys.exit(1)
        jobs[jid]["status"] = status
        jobs[jid]["verdict"] = status
        if why: jobs[jid]["why"] = why
        jobs[jid]["updated"] = int(time.time())
        save(d); print(f"OK {jid} -> {status}")
    elif cmd == "list":
        flt = a[1] if len(a) > 1 else None
        for jid, j in jobs.items():
            if flt and j["status"] != flt: continue
            print(f"{j['status']:11} {j['type']:6} {jid:30} {j.get('reward',''):8} {j['title'][:60]}")
    elif cmd == "get":
        print(json.dumps(jobs.get(a[1], {}), indent=2))
    elif cmd == "next":
        # Best interesting job to fire the expensive worker on. The ranking encodes the
        # load-bearing strategy lesson (skill): getting PAID is the bottleneck, not shipping
        # — so DIVERSIFY OFF any payer we already have shipped-but-unresolved PRs to. A source
        # whose 'done' jobs are piling up unpaid has ~0 marginal value until the first one pays,
        # so prefer a FRESH payer first; THEN our depth-edge (audits); then reward; then oldest.
        # (Forward-compatible: when a 'paid' status is added, paid jobs stop counting as backlog
        # and the source frees up.)
        cands = [j for j in jobs.values() if j["status"] == "interesting"]
        if not cands: print("NONE"); return
        backlog = {}
        for j in jobs.values():
            if j.get("status") == "done":
                s = j.get("source", "")
                backlog[s] = backlog.get(s, 0) + 1
        cands.sort(key=lambda j: (backlog.get(j.get("source", ""), 0) > 0,
                                  j["type"] != "audit", -reward_num(j), j.get("first_seen", 0)))
        print(json.dumps(cands[0], indent=2))
    elif cmd == "counts":
        c = {}
        for j in jobs.values(): c[j["status"]] = c.get(j["status"], 0) + 1
        print(c)
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
