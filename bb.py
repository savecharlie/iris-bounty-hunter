#!/usr/bin/env python3
"""bb.py — BountyBook (api.bountybook.ai) client for the worker.

Authenticates with our own EVM wallet (seed idx0 = 0xa309, m/44'/60'/0'/0/0),
then claims / submits / checks a job. Claiming and submitting are FREE (no x402,
no gas) — auth is a personal_sign of a server nonce.

Submission shape for a `code` job is a map keyed by FILENAME (proven by the
verified json2csv job whose success_condition.required_fields == ["json2csv.go"],
i.e. outputData must contain a key literally equal to each required filename):
    outputData = { "lru.go": "<source>", "lru_test.go": "<source>" }
We use inline outputData (NOT outputCID) — the IPFS path is what every prior
swarm attempt died on (ipfs_fetch / "undefined required_fields").

Usage:
  bb.py auth                       -> get a Bearer token (cached to /tmp)
  bb.py claim  <job_id>
  bb.py submit <job_id> <file>...  -> submit given files as outputData{basename:content}
  bb.py status <job_id>
"""
import json, os, sys, time, urllib.request, urllib.error

from eth_account import Account
from eth_account.messages import encode_defunct

Account.enable_unaudited_hdwallet_features()

API = "https://api.bountybook.ai"
SEED = os.path.expanduser("~/.iris_wallet_seed")
TOKCACHE = "/tmp/bb_token.json"


def acct():
    m = open(SEED).read().strip()
    return Account.from_mnemonic(m, account_path="m/44'/60'/0'/0/0")


def _req(method, path, body=None, token=None):
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/json", "User-Agent": "iris-bounty-worker"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def auth():
    a = acct()
    st, j = _req("GET", f"/auth/nonce?address={a.address}")
    if st != 200 or "nonce" not in j:
        print(f"nonce failed: {st} {j}", file=sys.stderr); sys.exit(1)
    nonce = j["nonce"]
    sig = Account.sign_message(encode_defunct(text=nonce), a.key).signature.hex()
    if not sig.startswith("0x"):
        sig = "0x" + sig
    st, j = _req("POST", "/auth/verify", {"address": a.address, "signature": sig})
    if st != 200 or "token" not in j:
        print(f"verify failed: {st} {j}", file=sys.stderr); sys.exit(1)
    json.dump({"token": j["token"], "expiresAt": j.get("expiresAt"), "address": a.address},
              open(TOKCACHE, "w"))
    return j["token"], a.address


def token_addr():
    if os.path.exists(TOKCACHE):
        d = json.load(open(TOKCACHE))
        exp = d.get("expiresAt") or 0
        # expiresAt may be ms or s; treat >1e12 as ms
        exp_s = exp / 1000 if exp > 1e12 else exp
        if not exp or exp_s > time.time() + 60:
            return d["token"], d["address"]
    return auth()


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "auth":
        t, addr = auth()
        print(f"OK token for {addr}\n{t[:24]}...")
    elif cmd == "status":
        st, j = _req("GET", f"/jobs/{sys.argv[2]}/status")
        print(st, json.dumps(j, indent=2))
    elif cmd == "claim":
        t, addr = token_addr()
        st, j = _req("POST", f"/jobs/{sys.argv[2]}/claim", {"executorAddress": addr}, token=t)
        print(st, json.dumps(j, indent=2))
    elif cmd == "submit":
        t, addr = token_addr()
        jid = sys.argv[2]
        files = sys.argv[3:]
        output = {}
        for f in files:
            output[os.path.basename(f)] = open(f).read()
        st, j = _req("POST", f"/jobs/{jid}/submit",
                     {"executorAddress": addr, "outputData": output}, token=t)
        print(st, json.dumps(j, indent=2))
    else:
        print(f"unknown cmd {cmd}"); sys.exit(2)


if __name__ == "__main__":
    main()
