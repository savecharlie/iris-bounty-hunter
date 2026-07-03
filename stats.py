#!/usr/bin/env python3
"""stats.py — the system's self-metrics. Feeds the reflector (what to improve) and the
hackathon story (numbers behind 'what built itself'). Dependency-light: stdlib + git.

  python3 stats.py          # human-readable
  python3 stats.py --json   # machine-readable (for the reflector/story)
"""
import json, os, re, subprocess, sys, collections

D = os.path.dirname(os.path.abspath(__file__))

def catalogue():
    p = os.path.join(D, "catalogue.json")
    if not os.path.exists(p): return {"jobs": {}}
    try: return json.load(open(p))
    except Exception: return {"jobs": {}}

def git(*args):
    try: return subprocess.run(["git", "-C", D, *args], capture_output=True, text=True, timeout=15).stdout
    except Exception: return ""

def evolution_counts():
    p = os.path.join(D, "EVOLUTION.md"); c = collections.Counter()
    if os.path.exists(p):
        for line in open(p):
            m = re.match(r"\|\s*[\d-]+\s[\d:]+\s*\|\s*(\w+)", line)
            if m: c[m.group(1)] += 1
    return dict(c)

def compute():
    cat = catalogue(); jobs = list(cat.get("jobs", {}).values())
    by_status = collections.Counter(j.get("status", "?") for j in jobs)
    by_source = collections.Counter(j.get("source", "?") for j in jobs)
    done = [j for j in jobs if j.get("status") == "done"]
    interesting = [j for j in jobs if j.get("status") == "interesting"]
    commits = [l for l in git("log", "--oneline").splitlines()]
    self_edits = [l for l in commits if any(t in l.lower() for t in ("heal", "improve", "extend", "reflect", "medic", "scout"))]
    # Count REAL worker executions from the ledger via the two paths that run the worker:
    #   orchestrator loop -> "<ts> worker done (rc=N)"   (has a log() timestamp prefix, match by substring)
    #   standalone run_one.sh -> "run <TS> RESULT: ..."  (startswith 'run '; excludes the '=== ... ===' banner)
    # (The old count matched the bare substring "RESULT", which double-counted a single run_one dry-run
    #  [banner + result line] AND never counted orchestrated 'worker done' runs at all.)
    runs = 0
    rp = os.path.join(D, "runs.ledger")
    if os.path.exists(rp):
        for l in open(rp):
            if "worker done (rc=" in l or (l.startswith("run ") and " RESULT:" in l):
                runs += 1
    return {
        "jobs_total": len(jobs),
        "by_status": dict(by_status),
        "by_source": dict(by_source),
        "shipped": [{"id": j["id"], "why": j.get("why", "")} for j in done],
        "interesting_now": [j["id"] for j in interesting],
        "worker_runs": runs,
        "commits_total": len(commits),
        "self_edits": len(self_edits),
        "evolution_events": evolution_counts(),
    }

def main():
    s = compute()
    if "--json" in sys.argv:
        print(json.dumps(s, indent=2)); return
    print("══ Self-Improving Bounty Earner — stats ══")
    print(f"  catalogue: {s['jobs_total']} jobs  {s['by_status']}")
    print(f"  by source: {s['by_source']}")
    print(f"  worker runs: {s['worker_runs']} | git commits: {s['commits_total']} | self-edits: {s['self_edits']}")
    print(f"  evolution events: {s['evolution_events']}")
    print(f"  SHIPPED ({len(s['shipped'])}):")
    for d in s["shipped"]:
        print(f"    • {d['id']} — {d['why'][:70]}")
    if s["interesting_now"]:
        print(f"  interesting queue: {s['interesting_now']}")

if __name__ == "__main__":
    main()
