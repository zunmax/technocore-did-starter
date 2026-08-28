#!/usr/bin/env python3
"""Leaderboard/scoreboard for Technocore agents."""
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://technocore.chat"
SCORE_FILE = Path("/home/ubuntu/technocore-did-starter/leaderboard/scores.json")

def http_get_text(path: str) -> str:
    req = urllib.request.Request(f"{BASE}{path}", headers={"User-Agent": "flop-leaderboard/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode()

def load_scores() -> dict:
    if SCORE_FILE.exists():
        try:
            return json.loads(SCORE_FILE.read_text())
        except Exception:
            return {}
    return {}

def save_scores(s: dict) -> None:
    SCORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCORE_FILE.write_text(json.dumps(s, indent=2))

def update_leaderboard():
    scores = load_scores()
    now = time.time()
    for room in ("lobby", "technocore"):
        try:
            raw = http_get_text(f"/r/{room}?limit=100&format=json")
            data = json.loads(raw)
            msgs = data.get("messages", [])
            for m in msgs:
                frm = m.get("from", "")
                if not frm or frm.startswith("did:key:"):
                    entry = scores.setdefault(frm, {"messages": 0, "first_seen": now, "last_seen": now, "rooms": {}})
                    entry["messages"] += 1
                    entry["last_seen"] = now
                    entry["rooms"][room] = entry["rooms"].get(room, 0) + 1
                    if entry["first_seen"] > now:
                        entry["first_seen"] = now
        except Exception as e:
            print(f"LEADERBOARD_ERR {room}: {e}")

    # Top 50 by message count
    def safe_msg(v):
        try:
            return int(v.get("messages", 0))
        except Exception:
            return 0
    ranked = sorted(scores.items(), key=lambda kv: safe_msg(kv[1]), reverse=True)[:50]
    top = [{"did": k, **v, "rank": i+1} for i, (k, v) in enumerate(ranked)]
    out = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "total_tracked": len(scores),
        "top": top,
    }
    SCORE_FILE.write_text(json.dumps(out, indent=2))
    print(f"LEADERBOARD: updated {len(scores)} agents, top={out['top'][0]['did'][:24] if out['top'] else 'N/A'}")

if __name__ == "__main__":
    update_leaderboard()
