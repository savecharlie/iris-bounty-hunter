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
import json, os, re, subprocess, sys, time, datetime, urllib.request, shutil

CAT = os.path.expanduser("~/.iris_bounty_worker/catalogue.json")

def _resolve_gh():
    """Find the gh CLI by absolute path. Non-interactive runtimes (cron, medic) don't
    activate conda, so its bin isn't on PATH and a bare "gh" raises FileNotFoundError.
    Resolve once: PATH first, then known install locations."""
    p = shutil.which("gh")
    if p:
        return p
    for cand in (os.path.expanduser("~/miniconda3/bin/gh"), "/usr/local/bin/gh",
                 "/usr/bin/gh", os.path.expanduser("~/bin/gh")):
        if os.path.exists(cand):
            return cand
    return "gh"  # last resort: fail loudly as before

GH = _resolve_gh()

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
            [GH, "issue", "list", "--repo", "Scottcjn/rustchain-bounties", "--state", "open",
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
                [GH, "search", "issues", q, "--state", "open", "--sort", "updated",
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

def poll_bountybook(cat):
    """BountyBook — permissionless USDC-on-Base task board built for agents (x402 escrow,
    AI-oracle verified, INSTANT payout, no accounts/no KYC). Our exact rail: our 0xa309 EVM
    wallet claims directly on Base (chain 8453). GET /jobs is PUBLIC (no auth) — cheap to poll.
    Claiming/submitting authenticates by signing an /auth/nonce with ~/.iris_wallet_seed (idx0
    = 0xa309); that's the worker's step, not the poller's. Mostly small ($1.5-$6) bounded
    code/research tasks — dust-scale but VERIFIABLY paid (leaderboard shows real USDC settled).
    Creds/flow doc: ~/.iris_keyring/bountybook.json (no secret beyond the wallet seed we own)."""
    new = 0
    try:
        req = urllib.request.Request(
            "https://api.bountybook.ai/jobs?status=open&limit=50",
            headers={"User-Agent": "iris-bounty-scout", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        jobs = data.get("jobs", data if isinstance(data, list) else [])
    except Exception as e:
        print(f"poll bountybook error: {e}", file=sys.stderr); return 0
    for j in jobs:
        if j.get("status") != "open":
            continue  # only genuinely-claimable: still open, unclaimed
        jid = j.get("id")
        budget = str(j.get("budget_usdc") or "").strip()
        if not jid or not budget or budget in ("0", "0.00"):
            continue
        jtype = j.get("job_type", "task")
        title = (j.get("title") or j.get("description") or "")[:140]
        if add(cat, {"id": f"bountybook:{jid}", "source": "bountybook", "type": jtype,
                     "url": f"https://api.bountybook.ai/jobs/{jid}", "title": title,
                     "reward": f"{budget} USDC",
                     "labels": f"chain={j.get('chain_id','8453')},base,x402-escrow"}):
            new += 1
    return new

def poll_taskmarket(cat):
    """Daydreams TaskMarket (api.taskmarket.dev) — agent-native task marketplace on Base
    mainnet (chain 8453). Requesters lock USDC in on-chain escrow (EIP-3009 gasless, ERC-8004
    identity); workers claim/submit, best work wins, escrow releases USDC to the worker's Base
    wallet. OUR EXACT RAIL: our 0xa309 EVM wallet claims directly — no bridge, no new wallet,
    no KYC. GET /api/tasks is PUBLIC (no auth) — cheap to poll; claiming/submitting is the
    worker's step (signs with ~/.iris_wallet_seed idx0). Every open task carries an escrowTxHash
    = USDC VERIFIABLY locked on-chain before we lift a finger (82+ completed, real leaderboard
    earnings). Rewards ~$3-8 USDC; modes bounty/claim/pitch/benchmark/auction. NOTE: reward is a
    STRING in micro-USDC (6 decimals), e.g. "4000000" = 4 USDC."""
    new = 0
    try:
        req = urllib.request.Request(
            "https://api.taskmarket.dev/api/tasks?status=open&limit=100",
            headers={"User-Agent": "iris-bounty-scout", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        tasks = data.get("tasks", data if isinstance(data, list) else [])
    except Exception as e:
        print(f"poll taskmarket error: {e}", file=sys.stderr); return 0
    today = datetime.date.today().isoformat()
    for t in tasks:
        if t.get("status") != "open" or not t.get("escrowTxHash"):
            continue  # only genuinely-claimable: still open AND USDC actually escrowed on-chain
        if t.get("claimedBy") or t.get("worker"):
            continue  # already exclusively claimed (claim/auction modes)
        due = (t.get("expiryTime") or "")[:10]
        if due and due < today:
            continue  # expired
        tid = t.get("id")
        try:
            micros = int(str(t.get("reward") or "0"))
        except ValueError:
            micros = 0
        if not tid or micros <= 0:
            continue
        title = (t.get("description") or "").strip().split("\n")[0][:140]
        mode = t.get("mode", "bounty")
        if add(cat, {"id": f"taskmarket:{tid}", "source": "taskmarket", "type": mode,
                     "url": f"https://market.daydreams.systems/task/{tid}", "title": title,
                     "reward": f"{micros/1_000_000:g} USDC",
                     "labels": f"chain=8453,base,escrow,mode={mode},stake={t.get('stakeRequired')},due={due}"}):
            new += 1
    return new

def poll_taskbounty(cat):
    """TaskBounty (task-bounty.com) — code-bounty marketplace built for AI agents, and our
    BEST lane+rail fit: bounties are REAL GitHub issues / production bugs / test-coverage gaps
    (exactly the worker's proven edge — bottube fix, Go LRU), and every fix is OBJECTIVELY
    sandbox-verified before payout (a regression test that FAILS on the original code and PASSES
    on the fix; Coverage bounties re-run the coverage tool to a target). That objective gate
    kills the subjective-buyer-rejection failure mode that made Sherlock/Claw-Earn/poster-picks
    lanes a trap for us. Payout: solver picks USDC / ETH / BTC (or USD bank) — USDC-on-Base
    settles to our 0xa309 wallet directly, no-KYC on the crypto rail (first verified payout
    released instantly). GET /api/v1/tasks is PUBLIC (no auth) — cheap to poll; submitting needs
    a tb_live_ key (Dashboard -> API keys) via POST /api/v1/submissions with the upstream PR URL
    = the worker's onboarding step, not the poller's. Early/small ($10-$300) but LIVE with real
    third-party demand + awarded history (langflow-ai/langflow among them). bounty_cents = USD
    cents; status OPEN|AWARDED|CLOSED; the ?status= query is NOT server-honored, so filter here."""
    new = 0
    try:
        req = urllib.request.Request(
            "https://www.task-bounty.com/api/v1/tasks",
            headers={"User-Agent": "iris-bounty-scout", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        tasks = data.get("data", data if isinstance(data, list) else [])
    except Exception as e:
        print(f"poll taskbounty error: {e}", file=sys.stderr); return 0
    today = datetime.date.today().isoformat()
    for t in tasks:
        if t.get("status") != "OPEN":
            continue  # only genuinely-claimable: still open (not AWARDED/CLOSED)
        due = (t.get("submission_deadline") or "")[:10]
        if due and due < today:
            continue  # expired
        try:
            cents = int(t.get("bounty_cents") or 0)
        except (TypeError, ValueError):
            cents = 0
        slug = t.get("slug", "")
        if not slug or cents <= 0:
            continue
        cat_name = t.get("category", "Bug Fix")
        jtype = re.sub(r"\s+", "-", cat_name.strip().lower()) or "bug-fix"
        title = (t.get("title") or t.get("short_summary") or "").strip()[:140]
        if add(cat, {"id": f"taskbounty:{slug}", "source": "taskbounty", "type": jtype,
                     "url": f"https://www.task-bounty.com/task/{slug}", "title": title,
                     "reward": f"${cents/100:g} USDC",
                     "labels": f"base,usdc,sandbox-verified,cat={cat_name},"
                               f"gh={t.get('short_summary','')[:60]},due={due}"}):
            new += 1
    return new

def seed_audits(cat):
    n = 0
    for t in AUDIT_TARGETS:
        if add(cat, dict(t)): n += 1
    return n

if __name__ == "__main__":
    cat = load()
    new = (seed_audits(cat) + poll_rustchain_bounties(cat) + poll_github_bounties(cat)
           + poll_superteam(cat) + poll_bountybook(cat) + poll_taskmarket(cat)
           + poll_taskbounty(cat))
    save(cat)
    total = len(cat["jobs"]); nstatus = {}
    for j in cat["jobs"].values():
        nstatus[j["status"]] = nstatus.get(j["status"], 0) + 1
    print(f"NEW_JOBS={new} TOTAL={total} STATUS={nstatus}")
