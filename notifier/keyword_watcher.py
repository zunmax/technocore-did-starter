#!/usr/bin/env python3
"""Keyword watcher + notifier for Technocore rooms."""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import technocore_agent as tc

BASE = "https://technocore.chat"
CURSOR = Path("/home/ubuntu/technocore-did-starter/.live_cursor.json")
MY_DID = "did:key:z6MkeiDDAJLG58GhrcqSvmat3ZKMAaVFGRgy4basUzDRavjn"

KEYWORDS = [
    "scam", "wallet", "seed", "claim", "FLOP", "airdrop", "private key",
    "passphrase", "verify", "safe", "guide", "tutorial", "help", "new",
    "begin", "start", "setup", "generate", "did", "nonce", "sign",
    "confus", "gimana", "bagaimana", "cara", "langkah", "error",
]

def http_get_text(path: str) -> str:
    req = urllib.request.Request(f"{BASE}{path}", headers={"User-Agent": "flop-notifier/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode()

def load_cursor() -> dict:
    if CURSOR.exists():
        try:
            return json.loads(CURSOR.read_text())
        except Exception:
            return {}
    return {}

def save_cursor(c: dict) -> None:
    CURSOR.write_text(json.dumps(c))

def send_telegram(message: str, chat_id: str, token: str) -> bool:
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = urllib.parse.quote(json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "HTML"}))
        req = urllib.request.Request(url, data=payload.encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception as e:
        print(f"TELEGRAM_ERR: {e}")
        return False

def send_discord_webhook(message: str, webhook_url: str) -> bool:
    try:
        payload = json.dumps({"content": message}).encode()
        req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status < 300
    except Exception as e:
        print(f"DISCORD_ERR: {e}")
        return False

def check_rooms(notifier_cursor_path: Path, telegram_token: str = "", telegram_chat: str = "", discord_webhook: str = ""):
    cur = load_cursor()
    notif_cur_path = notifier_cursor_path
    notif_cur = {}
    if notif_cur_path.exists():
        try:
            notif_cur = json.loads(notif_cur_path.read_text())
        except Exception:
            notif_cur = {}

    alerts = []
    seen_keywords = notif_cur.get("keyword_seen", {})

    for room in ("lobby", "technocore"):
        try:
            r = tc.read_room(room, limit=80, base_url=BASE)
            msgs = r.get("messages", [])
            for m in msgs:
                seq = m.get("seq", 0)
                msg_id = f"{room}:{seq}"
                if msg_id in seen_keywords:
                    continue
                frm = m.get("from", "")
                text = m.get("text", "")
                matched = [kw for kw in KEYWORDS if kw.lower() in text.lower()]
                if matched:
                    seen_keywords[msg_id] = {
                        "room": room,
                        "seq": seq,
                        "from": frm,
                        "keywords": matched,
                        "ts": time.time(),
                    }
                    alerts.append({
                        "room": room,
                        "seq": seq,
                        "from": frm,
                        "keywords": matched,
                        "text": text[:200],
                    })
        except Exception as e:
            alerts.append({"error": f"{room}: {str(e)[:60]}"})

    notif_cur["keyword_seen"] = seen_keywords
    notif_cur_path.write_text(json.dumps(notif_cur))

    if alerts:
        lines = [f"🔔 <b>Technocore Keyword Alert</b> ({len(alerts)} hit)"]
        for a in alerts:
            if "error" in a:
                lines.append(f"⚠️ {a['error']}")
            else:
                lines.append(f"• <b>{a['from'][:24]}</b> in <b>#{a['room']}</b>")
                lines.append(f"  Keywords: {', '.join(a['keywords'])}")
                lines.append(f"  Text: {a['text'][:120]}...")
                lines.append(f"  https://technocore.chat/r/{a['room']}?since={a['seq']}")
        msg = "\n".join(lines)

        sent = False
        if telegram_token and telegram_chat:
            sent = send_telegram(msg, telegram_chat, telegram_token)
        if discord_webhook:
            sent = send_discord_webhook(msg.replace("<b>", "**").replace("</b>", "**"), discord_webhook) or sent

        print(f"NOTIFIER: {len(alerts)} alerts sent={sent}")
    else:
        print("NOTIFIER: no keyword hits")

if __name__ == "__main__":
    notif_cur = Path("/home/ubuntu/technocore-did-starter/notifier/.keyword_cursor.json")
    notif_cur.parent.mkdir(parents=True, exist_ok=True)
    check_rooms(notif_cur)
