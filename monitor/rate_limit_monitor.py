#!/usr/bin/env python3
"""Rate-limit and health monitor for Technocore."""
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://technocore.chat"
STATE = Path("/home/ubuntu/technocore-did-starter/monitor/state.json")

def http_get_text(path: str, label: str = "") -> tuple[int, str]:
    req = urllib.request.Request(f"{BASE}{path}", headers={"User-Agent": "flop-monitor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, str(e)[:200]
    except Exception as e:
        return 0, str(e)[:200]

def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            return {}
    return {}

def save_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2))

def monitor():
    state = load_state()
    now = time.time()
    checks = state.setdefault("checks", [])
    backoff = state.setdefault("backoff", 1)

    statuses = {}
    for p in ("/rooms", "/r/lobby?limit=1", "/r/events?limit=1"):
        code, body = http_get_text(p, p)
        statuses[p] = {"code": code, "body": body[:80]}
        if code == 429:
            backoff = min(backoff * 2, 3600)
            print(f"MONITOR: 429 on {p}, backoff={backoff}s")
        elif code == 200:
            backoff = max(1, backoff // 2)

    checks.append({"ts": now, "statuses": statuses})
    if len(checks) > 200:
        checks = checks[-200:]
    state["checks"] = checks
    state["backoff"] = backoff
    state["last_check"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    print(f"MONITOR: backoff={backoff}s, checks={len(checks)}")
    for p, s in statuses.items():
        print(f"  {p}: {s['code']}")

if __name__ == "__main__":
    monitor()
