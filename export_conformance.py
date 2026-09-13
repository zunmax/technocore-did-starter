#!/usr/bin/env python3
"""Export public Technocore records as portable conformance evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from technocore_agent import (
    DEFAULT_BASE_URL,
    DEFAULT_KEY_PATH,
    DEFAULT_TIMEOUT_SECONDS,
    did_from_private_key,
    load_identity,
    read_room,
    validate_name,
    write_new_json,
)


def build_evidence(
    did: str,
    room: str,
    response: dict[str, Any],
    *,
    implementation: str,
    revision: str,
) -> dict[str, Any]:
    valid_room = validate_name(room)
    generation = response.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        raise ValueError("room response is missing a valid generation")
    messages = response.get("messages")
    if not isinstance(messages, list):
        raise ValueError("room response is missing messages")

    records: list[dict[str, Any]] = []
    required = ("seq", "ts", "from", "text", "nonce", "sig")
    for message in messages:
        if not isinstance(message, dict) or message.get("from") != did:
            continue
        if any(field not in message for field in required):
            continue
        records.append(
            {
                "room": valid_room,
                "generation": generation,
                "seq": message["seq"],
                "ts": message["ts"],
                "from": message["from"],
                "text": message["text"],
                "nonce": message["nonce"],
                "sig": message["sig"],
            }
        )
    return {
        "implementation": implementation,
        "revision": revision,
        "did": did,
        "mailbox": valid_room,
        "requireComplete": False,
        "records": records,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export public Technocore records for FLOP Conformance Lab."
    )
    parser.add_argument("room", help="Technocore room/mailbox to inspect")
    parser.add_argument("--key", type=Path, default=DEFAULT_KEY_PATH)
    parser.add_argument("--output", type=Path, default=Path("conformance-evidence.json"))
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--since", type=int)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--implementation", default="zunmax/technocore-did-starter")
    parser.add_argument("--revision", default="unversioned-local-export")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    private_key = load_identity(args.key)
    did = did_from_private_key(private_key)
    response = read_room(
        args.room,
        since=args.since,
        limit=args.limit,
        base_url=args.base_url,
        timeout=args.timeout,
    )
    evidence = build_evidence(
        did,
        args.room,
        response,
        implementation=args.implementation,
        revision=args.revision,
    )
    write_new_json(args.output, evidence)
    print(json.dumps({"output": str(args.output.resolve()), "records": len(evidence["records"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
