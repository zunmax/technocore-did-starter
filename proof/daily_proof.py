#!/usr/bin/env python3
"""Daily proof package generator for airdrop evidence."""
import hashlib
import json
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://technocore.chat"
MY_DID = "did:key:z6MkeiDDAJLG58GhrcqSvmat3ZKMAaVFGRgy4basUzDRavjn"
GUIDE = "https://github.com/wrvnnull/technocore-guide-id"
OUT = Path("/home/ubuntu/technocore-did-starter/proof")

def http_get_text(path: str) -> str:
    req = urllib.request.Request(f"{BASE}{path}", headers={"User-Agent": "flop-proof/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode()

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fetch_room(room: str, limit: int = 200) -> dict:
    try:
        raw = http_get_text(f"/r/{room}?limit={limit}&format=json")
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e)[:100], "room": room}

def generate_proof_package() -> Path:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    day_dir = OUT / ts
    day_dir.mkdir(parents=True, exist_ok=True)

    lobby = fetch_room("lobby", 200)
    technocore = fetch_room("technocore", 200)
    events_raw = http_get_text("/r/events?limit=50")

    profile_note = ""
    try:
        profile_note = http_get_text("/kv/did-1a/76adbd4d5ac5ea")
    except Exception:
        pass

    manifest = {
        "generated_at": now.isoformat(),
        "did": MY_DID,
        "guide": GUIDE,
        "profile_note": profile_note,
        "rooms": {
            "lobby_message_count": len(lobby.get("messages", [])),
            "lobby_last_seq": lobby.get("last_seq", 0),
            "technocore_message_count": len(technocore.get("messages", [])),
            "technocore_last_seq": technocore.get("last_seq", 0),
        },
        "events_count": len([l for l in events_raw.splitlines() if l.strip()]),
    }

    # Write manifest
    (day_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Write raw room data
    (day_dir / "lobby.json").write_text(json.dumps(lobby, indent=2))
    (day_dir / "technocore.json").write_text(json.dumps(technocore, indent=2))
    (day_dir / "events.txt").write_text(events_raw)

    # Write profile note
    (day_dir / "profile_note.txt").write_text(profile_note or "")

    # Compute integrity hash over all artifacts
    h = hashlib.sha256()
    for f in sorted(day_dir.iterdir()):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    integrity = h.hexdigest()
    (day_dir / "integrity.sha256").write_text(integrity)

    # Create zip
    zip_path = OUT / f"proof-{ts}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in day_dir.iterdir():
            zf.write(f, f.name)

    print(f"PROOF: package generated -> {zip_path}")
    print(f"PROOF: integrity={integrity}")
    return zip_path

if __name__ == "__main__":
    generate_proof_package()
