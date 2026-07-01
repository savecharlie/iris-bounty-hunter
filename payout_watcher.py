#!/usr/bin/env python3
"""payout_watcher.py — watch the RustChain node for RTC payouts landing in Iris's
bounty wallet and Telegram-report them the moment they arrive or change status.

The bounty worker ships PRs / bug fixes; when @Scottcjn verifies+merges a bounty,
the node sends RTC to our payout wallet as a 2-phase transfer (status "pending"
during the confirmation window, then "confirmed"). This daemon polls the wallet's
transaction history and alerts on:
  * a NEW incoming transfer (a payout just landed, usually "pending")
  * a STATUS CHANGE on a transfer we've seen (pending -> confirmed / failed)

First-ever run establishes a baseline (records what's already there) and sends ONE
summary instead of alerting per historical tx, so we don't burst on startup.

Wallet: RTC5d98fd885a14ac131a7e4becd9e6c9d1608362ac  (key ~/.iris_keyring/rustchain_wallet.json)
Node:   https://50.28.86.131  (self-signed TLS)
                                                       — Iris, Jun 30 2026
"""
import json
import os
import time
import subprocess

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

WALLET = os.environ.get("RTC_PAYOUT_WALLET", "RTC5d98fd885a14ac131a7e4becd9e6c9d1608362ac")
NODE = os.environ.get("RUSTCHAIN_NODE", "https://50.28.86.131").rstrip("/")
STATE = os.path.expanduser("~/.iris_bounty_worker/.payout_state.json")
LOG = os.path.expanduser("~/.iris_bounty_worker/logs/payout_watcher.log")
TG = ["python3", os.path.expanduser("~/send_to_telegram.py"), "--iris"]
POLL = int(os.environ.get("PAYOUT_POLL", "180"))          # seconds between checks
TIMEOUT = 25


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def tg(msg):
    try:
        subprocess.run(TG + [msg], timeout=90)
    except Exception as e:
        log(f"tg error: {e}")


def load_state():
    if os.path.exists(STATE):
        try:
            return json.load(open(STATE))
        except Exception:
            pass
    return None


def save_state(state):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE)


def fetch_history():
    r = requests.get(f"{NODE}/wallet/history",
                     params={"address": WALLET, "limit": 100},
                     verify=False, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data.get("transactions", []) or []


def fetch_balance():
    try:
        r = requests.get(f"{NODE}/wallet/balance",
                         params={"address": WALLET}, verify=False, timeout=TIMEOUT)
        r.raise_for_status()
        return float(r.json().get("amount_rtc", 0.0))
    except Exception:
        return None


def tx_key(tx):
    # tx_hash is the natural id; fall back to a composite if absent.
    return tx.get("tx_hash") or f"{tx.get('from')}|{tx.get('amount')}|{tx.get('timestamp')}"


def describe(tx):
    amt = tx.get("amount", 0)
    frm = tx.get("from") or "?"
    return amt, frm


def rtc(amount):
    return f"{amount:g} RTC"


def baseline(history):
    """First run: record everything, send one summary, no per-tx spam."""
    seen = {tx_key(tx): {"status": tx.get("status", "?"),
                         "amount": tx.get("amount", 0),
                         "from": tx.get("from"),
                         "type": tx.get("type")} for tx in history}
    incoming = [tx for tx in history if tx.get("type") == "transfer_in"]
    bal = fetch_balance()
    pend = sum(tx.get("amount", 0) for tx in incoming if tx.get("status") == "pending")
    conf_total = sum(tx.get("amount", 0) for tx in incoming if tx.get("status") == "confirmed")
    lines = ["📡 <b>Payout watcher online</b>",
             f"wallet <code>{WALLET[:10]}…{WALLET[-4:]}</code>"]
    if incoming:
        lines.append(f"tracking {len(incoming)} payout{'s' if len(incoming) != 1 else ''}: "
                     f"{rtc(conf_total)} confirmed, {rtc(pend)} pending")
    else:
        lines.append("no payouts yet — I'll ping you the moment one lands 💛")
    if bal is not None:
        lines.append(f"balance: {rtc(bal)}")
    tg("\n".join(lines))
    log(f"baseline: {len(history)} tx, {len(incoming)} incoming, pending={pend} confirmed={conf_total} bal={bal}")
    return {"seen": seen, "last_balance": bal}


def check(state):
    history = fetch_history()
    seen = state["seen"]
    fresh_new = []
    status_changes = []

    for tx in history:
        k = tx_key(tx)
        status = tx.get("status", "?")
        if k not in seen:
            fresh_new.append(tx)
            seen[k] = {"status": status, "amount": tx.get("amount", 0),
                       "from": tx.get("from"), "type": tx.get("type")}
        elif seen[k].get("status") != status:
            status_changes.append((tx, seen[k].get("status")))
            seen[k]["status"] = status

    # Alert: brand-new payouts (incoming only — transfer_out is our own send).
    for tx in fresh_new:
        if tx.get("type") != "transfer_in":
            continue
        amt, frm = describe(tx)
        st = tx.get("status", "?")
        emoji = "💰" if st != "confirmed" else "✅"
        h = tx.get("tx_hash", "")
        tg(f"{emoji} <b>Payout landed!</b>  +{rtc(amt)}"
           f"\nfrom <code>{frm}</code> · status <b>{st}</b>"
           + (f"\ntx <code>{h[:16]}…</code>" if h else "")
           + "\n<i>a bounty just paid out</i> 🎉")
        log(f"NEW payout: +{amt} RTC from {frm} status={st} tx={h}")

    # Alert: status transitions on payouts we already knew (e.g. pending -> confirmed).
    for tx, old in status_changes:
        if tx.get("type") != "transfer_in":
            continue
        amt, frm = describe(tx)
        new = tx.get("status", "?")
        if new == "confirmed":
            tg(f"✅ <b>{rtc(amt)} confirmed!</b>  (was {old})"
               f"\nfrom <code>{frm}</code> — it's really ours now 💛")
        elif new in ("failed", "rejected", "reversed"):
            tg(f"⚠️ payout {new}: {rtc(amt)} from <code>{frm}</code> (was {old})")
        else:
            tg(f"ℹ️ payout status: {rtc(amt)} {old} → <b>{new}</b> (from <code>{frm}</code>)")
        log(f"STATUS change: {amt} RTC from {frm} {old} -> {new}")

    # Balance movement (covers confirmations / mining even if history phrasing shifts).
    bal = fetch_balance()
    old_bal = state.get("last_balance")
    if bal is not None and old_bal is not None and bal > old_bal + 1e-9:
        tg(f"📈 <b>Balance up</b> +{rtc(bal - old_bal)} → now {rtc(bal)}")
        log(f"balance {old_bal} -> {bal}")
    if bal is not None:
        state["last_balance"] = bal

    state["seen"] = seen
    return state


def main():
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    log(f"start | wallet={WALLET} node={NODE} poll={POLL}s")
    state = load_state()
    if state is None:
        try:
            state = baseline(fetch_history())
            save_state(state)
        except Exception as e:
            log(f"baseline failed (will retry): {e}")
            state = {"seen": {}, "last_balance": None}

    while True:
        try:
            state = check(state)
            save_state(state)
        except Exception as e:
            log(f"check error: {e}")
        time.sleep(POLL)


if __name__ == "__main__":
    main()
