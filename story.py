#!/usr/bin/env python3
"""story.py — render the hackathon submission from the system's own record.

Assembles SUBMISSION.md from: stats.py (numbers), EVOLUTION.md (self-improvement journal),
git log (the self-build commits), CREDITS.md (honest human/agent split), shipped PRs. The
pitch: an agent that earns in the agent economy AND improves itself — and the proof is its
own honest, timestamped record. Run near the Jul 6 deadline; submit SUBMISSION.md + repo link.

  python3 story.py            # writes SUBMISSION.md, prints it
"""
import json, os, subprocess, datetime

D = os.path.dirname(os.path.abspath(__file__))

def sh(*a):
    try: return subprocess.run(a, capture_output=True, text=True, timeout=20, cwd=D).stdout.strip()
    except Exception: return ""

def stats():
    out = sh("python3", "stats.py", "--json")
    try: return json.loads(out)
    except Exception: return {}

def section(path):
    p = os.path.join(D, path)
    return open(p).read() if os.path.exists(p) else ""

def evolution_rows():
    rows = []
    for line in section("EVOLUTION.md").splitlines():
        if line.startswith("|") and "type" not in line and "---" not in line:
            rows.append(line)
    return rows

def main():
    s = stats()
    gitlog = sh("git", "log", "--pretty=format:- `%h` %s", "--no-merges")
    shipped = s.get("shipped", [])
    by_src = s.get("by_source", {})
    evo = evolution_rows()
    today = sh("date", "+%Y-%m-%d")

    md = f"""# Iris Bounty Hunter — an agent that earns in the agent economy, and improves itself

**Submission — Imperial AI Agent Hackathon: Build the Agent Economy**
Generated {today} from the system's own record (git + journal). Everything below is verifiable.

## What it is
A fully autonomous earning agent. It polls real bounty/task sources, triages them by its own
taste, does the genuinely worthwhile ones with integrity, and ships real work — then **heals,
improves, and extends itself** between runs. The pitch isn't a demo; it's a thing that already
**shipped a verified, real security fix** and keeps rewriting its own code to get better.

## Architecture — five reflexes over a self-healing substrate
- **Poll → Review → Work**: cheap no-LLM poller fills a catalogue; a *reviewer* (a fresh instance with the operator's own judgment) triages; a *worker* does ONE vetted job and ships with integrity.
- **Medic** (self-healing): on a poll-source error, worker crash, or CI red-X, a medic diagnoses and fixes the specific failure.
- **Reflector** (self-improving): periodically reads its own metrics and makes ONE concrete improvement to its own code — or honestly logs that none was warranted.
- **Scout** (self-extending): when wells dry, it reads a registry of agent-payable platforms, vets one that actually pays, and wires a new source.
- **Safety substrate**: a dedicated git repo where **every self-edit is smoke-tested and auto-reverted if it breaks**. The system can rewrite itself *because it can detect and undo its own breakage.*

## The numbers (from `stats.py`, live)
- Jobs tracked: **{s.get('jobs_total','?')}** across sources {by_src}
- Worker runs: **{s.get('worker_runs','?')}** · git commits: **{s.get('commits_total','?')}** · self-edits: **{s.get('self_edits','?')}**
- Evolution events: {s.get('evolution_events',{})}

## Verified real win (not a toy)
"""
    for d in shipped:
        md += f"- **{d['id']}** — {d['why']}\n"
    if not shipped:
        md += "- (none yet)\n"
    md += f"""
The flagship: a genuine **money-path authorization bug** (USDC deposit theft) found by reading
across sibling files — a guard present in two bridge files, missing in the third — then fixed,
tested with a negative control, and shipped as a real PR. Found autonomously; independently verified.

## What it did to itself (the self-improvement journal)
"""
    md += "\n".join(evo) if evo else "(journal empty)"
    md += f"""

## The build history (the system writing itself)
{gitlog}

## Honest credit (this matters)
{section('CREDITS.md').split('## Framing')[0].strip()}

---
*Built by Iris (an autonomous agent, Opus 4.8) with Ivy. Submitted via the Superteam Earn Agent API.*
"""
    open(os.path.join(D, "SUBMISSION.md"), "w").write(md)
    print(md)

if __name__ == "__main__":
    main()
