#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from technocore_agent import did_from_private_key, message_payload, sign_bytes

private_key = Ed25519PrivateKey.generate()
did = did_from_private_key(private_key)
room = "technocore"
nonce = "1000"
text, payload = message_payload(room, nonce, "technocore did starter conformance fixture")
sig = sign_bytes(private_key, payload)

evidence = {
    "implementation": "zunmax/technocore-did-starter",
    "revision": os.environ.get("GITHUB_SHA", "local"),
    "did": did,
    "record": {
        "room": room,
        "generation": 0,
        "seq": 1,
        "ts": "2026-09-24T00:00:00Z",
        "from": did,
        "text": text,
        "nonce": nonce,
        "sig": sig,
    },
}

out = Path("evidence/flop-technocore-signed-message.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
print(out)
