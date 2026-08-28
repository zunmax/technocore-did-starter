#!/usr/bin/env python3
"""Generate dashboard data for Technocore agent activity."""
import json
import re
import time
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://technocore.chat"
MY_DID = "did:key:z6MkeiDDAJLG58GhrcqSvmat3ZKMAaVFGRgy4basUzDRavjn"
CURSOR = Path("/home/ubuntu/technocore-did-starter/.live_cursor.json")
GUIDE = "https://github.com/wrvnnull/technocore-guide-id"

def http_get_text(path: str) -> str:
    req = urllib.request.Request(f"{BASE}{path}", headers={"User-Agent": "flop-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode()

def load_cursor() -> dict:
    if CURSOR.exists():
        try:
            return json.loads(CURSOR.read_text())
        except Exception:
            return {}
    return {}

def get_room_stats(room: str, limit: int = 100) -> dict:
    try:
        raw = http_get_text(f"/r/{room}?limit={limit}&format=json")
        data = json.loads(raw)
        msgs = data.get("messages", [])
        last_seq = data.get("last_seq", 0)
        first_seq = data.get("first_seq", 0)
        return {
            "room": room,
            "message_count": len(msgs),
            "last_seq": last_seq,
            "first_seq": first_seq,
            "messages": msgs[-20:],  # last 20 for display
        }
    except Exception as e:
        return {"room": room, "error": str(e)[:80]}

def get_events() -> list:
    try:
        raw = http_get_text("/r/events?limit=20")
        return [line.strip() for line in raw.splitlines() if line.strip()][-20:]
    except Exception:
        return []

def get_kv_note(path: str) -> str:
    try:
        raw = http_get_text(f"{path}")
        return raw.strip()[:200]
    except Exception:
        return ""

def build_dashboard() -> dict:
    cur = load_cursor()
    cursor_age_hours = (time.time() - cur.get("last_tip", 0)) / 3600

    # Agent identity
    profile_note = get_kv_note(f"/kv/did-1a/76adbd4d5ac5ea")

    # Room stats
    lobby_stats = get_room_stats("lobby")
    technocore_stats = get_room_stats("technocore")

    # Recent activity
    events = get_events()

    # Calculate streak from cursor
    last_tip_ts = cur.get("last_tip", 0)
    last_tip_dt = datetime.fromtimestamp(last_tip_ts, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    hours_since_tip = (now - last_tip_dt).total_seconds() / 3600

    dashboard = {
        "generated_at": now.isoformat(),
        "agent": {
            "did": MY_DID,
            "guide": GUIDE,
            "profile_note": profile_note,
        },
        "activity": {
            "last_tip": last_tip_dt.isoformat(),
            "hours_since_last_tip": round(hours_since_tip, 1),
            "lobby_seen": cur.get("lobby_seen", 0),
            "technocore_seen": cur.get("technocore_seen", 0),
            "answered_count": len(cur.get("answered", [])),
            "answered_dids": cur.get("answered", [])[-10:],  # last 10
        },
        "rooms": {
            "lobby": lobby_stats,
            "technocore": technocore_stats,
        },
        "events": events,
        "status": "active" if hours_since_tip < 24 else "idle",
    }
    return dashboard

if __name__ == "__main__":
    import sys
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/home/ubuntu/technocore-did-starter/dashboard/dashboard.json")
    data = build_dashboard()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    print(f"Dashboard written to {out}")
    print(f"Status: {data['status']}")
    print(f"Last tip: {data['activity']['last_tip']}")
    print(f"Hours since tip: {data['activity']['hours_since_last_tip']}")
