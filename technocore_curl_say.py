#!/usr/bin/env python3
"""Post one signed Technocore message using curl.exe as the HTTPS transport.

This is a Windows fallback for environments where Python's TLS connection to
technocore.chat is unreliable. The encrypted private key and passphrase remain
inside the Python process. Only the public DID, signature, nonce, and message are
sent to curl over stdin.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import technocore_agent as agent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("room")
    parser.add_argument("text")
    parser.add_argument("--key", type=Path, default=agent.DEFAULT_KEY_PATH)
    parser.add_argument("--nonce", help="advanced recovery override")
    parser.add_argument("--base-url", default=agent.DEFAULT_BASE_URL)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def post_with_curl(args: argparse.Namespace) -> dict[str, object]:
    """Sign one message locally and use curl.exe for the single write attempt."""
    curl = shutil.which("curl.exe")
    if curl is None:
        raise agent.NetworkError("curl.exe was not found on PATH")

    timeout = agent.validate_timeout(args.timeout)
    room = agent.validate_name(args.room)
    base_url = agent.validate_base_url(args.base_url)
    nonce = agent.validate_nonce(
        args.nonce if args.nonce is not None else agent.next_nonce()
    )
    normalized, payload = agent.message_payload(room, nonce, args.text)
    private_key = agent.load_identity(args.key)
    did = agent.did_from_private_key(private_key)
    request_body = json.dumps(
        {
            "did": did,
            "sig": agent.sign_bytes(private_key, payload),
            "nonce": nonce,
            "text": normalized,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    command = [
        curl,
        "--http1.1",
        "--tlsv1.2",
        "--tls-max",
        "1.2",
        "--fail-with-body",
        "--silent",
        "--show-error",
        "--connect-timeout",
        "10",
        "--max-time",
        f"{timeout:g}",
        "--max-filesize",
        str(agent.MAX_RESPONSE_BYTES),
        "--header",
        "Accept: application/json",
        "--header",
        "Content-Type: application/json; charset=utf-8",
        "--header",
        f"User-Agent: technocore-did-starter/{agent.APP_VERSION} curl-fallback",
        "--data-binary",
        "@-",
        "--url",
        f"{base_url}/r/{room}?format=json",
    ]
    try:
        completed = subprocess.run(
            command,
            input=request_body,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 5,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise agent.NetworkError(
            "Technocore write timed out; its outcome is unknown. Check the room "
            "for this DID before retrying."
        ) from error

    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        stdout = completed.stdout.decode("utf-8", errors="replace")
        detail = agent.terminal_safe_detail(stderr or stdout or "no response body")
        raise agent.NetworkError(
            f"curl transport failed with exit {completed.returncode}: {detail}. "
            "The write outcome may be unknown; check the room before retrying."
        )

    try:
        response = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise agent.NetworkError(
            "Technocore returned a response that was not valid UTF-8 JSON; check "
            "the room before retrying."
        ) from error
    if not isinstance(response, dict):
        raise agent.NetworkError("Technocore returned JSON that was not an object")

    agent.validate_room_response(response, room)
    posted = response.get("posted")
    if not isinstance(posted, dict):
        raise agent.NetworkError("Technocore did not return a posted record")
    posted_seq = posted.get("seq")
    try:
        nonce_matches = not isinstance(posted.get("nonce"), bool) and int(
            posted.get("nonce")
        ) == int(nonce)
    except (TypeError, ValueError):
        nonce_matches = False
    if not (
        posted.get("from") == did
        and posted.get("text") == normalized
        and nonce_matches
        and not isinstance(posted_seq, bool)
        and isinstance(posted_seq, int)
        and posted_seq > 0
    ):
        raise agent.NetworkError(
            "Technocore returned a posted record that does not match this "
            "signed message"
        )
    if not any(message.get("seq") == posted_seq for message in response["messages"]):
        raise agent.NetworkError(
            "Technocore response did not include the newly posted sequence"
        )

    safe_posted = {
        key: posted.get(key) for key in ("seq", "ts", "from", "text", "nonce")
    }
    return {"room": room, "posted": safe_posted}


def main() -> int:
    agent.configure_output_streams()
    args = build_parser().parse_args()
    try:
        result = post_with_curl(args)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except (agent.IdentityError, agent.NetworkError, agent.ProtocolError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
