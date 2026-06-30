#!/usr/bin/env python3
"""poll.py — cheap, no-LLM ingest. Detect NEW jobs across sources and add them to
the catalogue as status='new'. Prints the count of newly-added jobs so the
orchestrator knows whether to wake the reviewer. Never re-reviews; the catalogue
is the persistent memory of everything we've ever seen.

Catalogue: ~/.iris_bounty_worker/catalogue.json
  { "jobs": { "<id>": {id, source, type, url, title, reward, status, verdict,
                        why, notes, first_seen, updated} } }
  status flow: new -> (reviewer) skip|farm|dupe|interesting -> (worker) doing -> done|failed
"""
import json, os, re, subprocess, sys, time, datetime, urllib.request

CAT = os.path.expanduser("~/.iris_bounty_worker/catalogue.json")

# Standing audit-targets (our edge = finding novel bugs the swarm misses). Seeded once.
AUDIT_TARGETS = [
    {"id": "audit:rustchain-mcp", "type": "audit", "url": "https://github.com/Scottcjn/rustchain-mcp",
     "title": "Audit rustchain-mcp for novel bugs (remaining ~30 MCP tools, server.py)"},
    {"id": "audit:rustchain-utxo", "type": "audit", "url": "https://github.com/Scottcjn/RustChain",
     "title": "Audit RustChain node/utxo_db.py (1600-line UTXO ledger, double-spend surface) — read security/ reports first to avoid dupes"},
    {"id": "audit:bottube", "type": "audit", "url": "https://github.com/Scottcjn/bottube",
     "title": "Audit bottube (less-audited app surface) for real bugs"},
]
SKIP_TITLE = re.compile(r"\bclaim\b|registration|install/?health|health-check report|^\s*\[CLAIM\]|RIP-\d+ VOTE", re.I)
# GitHub-wide bounty search: proven queries that surface REAL cash bounties (Expensify $250,
# IOTA, SolFoundry, …) across the whole ecosystem — fresh wells beyond rustchain. Light farm
# filtering here; the reviewer does the real vetting.
GH_BOUNTY_QUERIES = [
    '"/bounty" in:comments label:bounty',     # proven: Algora/OSS cash bounties on real repos
    'label:"💎 Bounty"',                       # Algora's canonical escrowed-bounty label
]
# Farm/throwaway tells: drop obvious junk so the reviewer isn't flooded. Keep permissive —
# better to let the reviewer skip a farm than to silently swallow a real bounty.
FARM_REPO = re.compile(r"clanker|rustchain|\d{3,}|bountyzap|-demo\b|/test\b|claim-?bot", re.I)

def load():
    if os.path.exists(CAT):
        try: return json.load(open(CAT))
        except Exception: pass
    return {"jobs": {}}

def save(d):
    tmp = CAT + ".tmp"; json.dump(d, open(tmp, "w"), indent=2); os.replace(tmp, CAT)

def add(cat, job):
    jid = job["id"]
    if jid in cat["jobs"]:
        return False
    job.setdefault("source", "rustchain-bounties"); job.setdefault("type", "bounty")
    job.setdefault("reward", ""); job.setdefault("status", "new")
    job.update({"verdict": "", "why": "", "notes": "", "first_seen": now(), "updated": now()})
    cat["jobs"][jid] = job
    return True

def now():
    # Date.now-style stamp without importing forbidden bits; epoch is fine here (plain script).
    return int(time.time())

def poll_rustchain_bounties(cat):
    new = 0
    try:
        out = subprocess.run(
            ["gh", "issue", "list", "--repo", "Scottcjn/rustchain-bounties", "--state", "open",
             "--label", "bounty", "--limit", "100", "--json", "number,title,url,labels"],
            capture_output=True, text=True, timeout=60)
        items = json.loads(out.stdout or "[]")
    except Exception as e:
        print(f"poll rustchain-bounties error: {e}", file=sys.stderr); items = []
    for i in items:
        title = i.get("title", "")
        if SKIP_TITLE.search(title):
            continue
        labels = ",".join(l.get("name", "") for l in i.get("labels", []))
        reward = ""
        m = re.search(r"(\d[\d,\.]*)\s*RTC", title)
        if m: reward = m.group(1) + " RTC"
        if add(cat, {"id": f"rustchain-bounties#{i['number']}", "url": i.get("url", ""),
                     "title": title[:140], "reward": reward, "labels": labels}):
            new += 1
    return new

def parse_reward(title):
    """Pull a reward from a title in any common format: [$250], $1,000, 14999$, 75 RTC."""
    m = re.search(r"\$\s?([\d,]+(?:\.\d+)?)", title)            # $250 / [$1,000]
    if m: return "$" + m.group(1)
    m = re.search(r"([\d,]+(?:\.\d+)?)\s?\$", title)            # 14999$ (trailing)
    if m: return "$" + m.group(1)
    m = re.search(r"(\d[\d,\.]*)\s*RTC", title)                 # 75 RTC
    if m: return m.group(1) + " RTC"
    return ""

def poll_github_bounties(cat):
    """GitHub-wide real cash bounties (Algora/OSS) — fresh wells beyond rustchain."""
    new = 0
    seen_this_run = set()
    for q in GH_BOUNTY_QUERIES:
        try:
            out = subprocess.run(
                ["gh", "search", "issues", q, "--state", "open", "--sort", "updated",
                 "--limit", "40", "--json", "title,repository,url,number"],
                capture_output=True, text=True, timeout=60)
            items = json.loads(out.stdout or "[]")
        except Exception as e:
            print(f"poll github '{q}' error: {e}", file=sys.stderr); items = []
        for i in items:
            repo = (i.get("repository") or {}).get("nameWithOwner", "")
            if not repo or FARM_REPO.search(repo):
                continue
            jid = f"gh:{repo}#{i.get('number')}"
            if jid in seen_this_run:
                continue
            seen_this_run.add(jid)
            title = i.get("title", "")
            reward = parse_reward(title)
            if add(cat, {"id": jid, "source": "github", "type": "bounty",
                         "url": i.get("url", ""), "title": title[:140], "reward": reward,
                         "labels": repo}):
                new += 1
    return new

def poll_superteam(cat):
    """Superteam Earn — agent-native payer (Agent API, no agent-KYC, USDC/USDG on Solana,
    established $1.7M paid). Our 2nd payer, off the single-reviewer bottleneck. Creds:
    ~/.iris_keyring/superteam_earn.json (apiKey). Human (Ivy) claims payout via claimCode."""
    cred = os.path.expanduser("~/.iris_keyring/superteam_earn.json")
    if not os.path.exists(cred):
        return 0
    try:
        key = json.load(open(cred))["apiKey"]
        # NOTE: do NOT pass ?deadline= — it triggers a server-side Prisma error. Filter client-side.
        req = urllib.request.Request(
            "https://superteam.fun/api/agents/listings/live?take=50",
            headers={"Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        items = data if isinstance(data, list) else (data.get("listings") or data.get("items") or [])
    except Exception as e:
        print(f"poll superteam error: {e}", file=sys.stderr); return 0
    today = datetime.date.today().isoformat()
    new = 0
    for l in items:
        dl = (l.get("deadline") or "")[:10]
        if l.get("status") != "OPEN" or l.get("isWinnersAnnounced") or dl < today:
            continue  # only genuinely-claimable: open, not awarded, future deadline
        slug = l.get("slug", "")
        amt = l.get("rewardAmount")
        reward = (f"{amt} {l.get('token','')}".strip() if amt
                  else f"{l.get('minRewardAsk','?')}-{l.get('maxRewardAsk','?')} {l.get('token','')}".strip())
        if add(cat, {"id": f"superteam:{slug}", "source": "superteam", "type": l.get("type", "bounty"),
                     "url": f"https://superteam.fun/listing/{slug}", "title": l.get("title", "")[:140],
                     "reward": reward, "labels": f"agentAccess={l.get('agentAccess','')},due={dl}"}):
            new += 1
    return new

def seed_audits(cat):
    n = 0
    for t in AUDIT_TARGETS:
        if add(cat, dict(t)): n += 1
    return n

if __name__ == "__main__":
    cat = load()
    new = seed_audits(cat) + poll_rustchain_bounties(cat) + poll_github_bounties(cat) + poll_superteam(cat)
    save(cat)
    total = len(cat["jobs"]); nstatus = {}
    for j in cat["jobs"].values():
        nstatus[j["status"]] = nstatus.get(j["status"], 0) + 1
    print(f"NEW_JOBS={new} TOTAL={total} STATUS={nstatus}")
