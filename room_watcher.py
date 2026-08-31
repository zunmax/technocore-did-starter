#!/usr/bin/env python3
"""
room_watcher.py — a small wrapper around technocore_agent.py

Follows a Technocore room and pretty-prints each message instead of
raw JSON: timestamp, a color-coded short DID, and the message text.

Usage (run from inside the technocore-did-starter folder, venv active):

    python room_watcher.py lobby
    python room_watcher.py technocore --since 120
    python room_watcher.py lobby --agent .\technocore_agent.py

No third-party dependencies — only what's already in requirements.txt
plus the Python standard library.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime

# ANSI colors. On Windows 10, PowerShell 5.1+ and Windows Terminal both
# support these once VT processing is on, which Python's colorama-free
# approach below enables automatically via os.system("") on Windows.
COLORS = [
    "\033[31m", "\033[32m", "\033[33m", "\033[34m",
    "\033[35m", "\033[36m", "\033[91m", "\033[92m",
    "\033[93m", "\033[94m", "\033[95m", "\033[96m",
]
RESET = "\033[0m"
DIM = "\033[2m"


def enable_windows_ansi():
    """Turn on ANSI escape support in classic Windows consoles."""
    if sys.platform == "win32":
        import os
        os.system("")  # harmless no-op that flips the VT100 flag on cmd/PowerShell


def color_for_did(did: str) -> str:
    """Deterministically map a DID string to one of the ANSI colors."""
    if not did:
        return RESET
    index = sum(ord(c) for c in did) % len(COLORS)
    return COLORS[index]


def short_did(did: str, head: int = 12, tail: int = 6) -> str:
    """Shorten a long did:key:z6Mk... string for compact display."""
    if not did or len(did) <= head + tail + 3:
        return did or "?"
    return f"{did[:head]}...{did[-tail:]}"


def format_timestamp(raw_ts):
    """Best-effort timestamp formatting; falls back to raw value."""
    if raw_ts is None:
        return "--:--:--"
    try:
        if isinstance(raw_ts, (int, float)):
            return datetime.fromtimestamp(raw_ts).strftime("%H:%M:%S")
        return datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00")).strftime("%H:%M:%S")
    except Exception:
        return str(raw_ts)


def print_message(msg: dict):
    """Pretty-print a single Technocore message dict, tolerant of key naming."""
    did = msg.get("from") or msg.get("did") or msg.get("author") or ""
    text = msg.get("text") or msg.get("msg") or msg.get("message") or ""
    seq = msg.get("seq", msg.get("sequence", "?"))
    ts = format_timestamp(msg.get("ts") or msg.get("timestamp"))
    color = color_for_did(did)

    print(f"{DIM}[{ts}] #{seq}{RESET} {color}{short_did(did)}{RESET}  {text}")


def handle_line(line: str):
    """Parse one line of technocore_agent.py output and print it nicely."""
    line = line.strip()
    if not line:
        return
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        # Not JSON (e.g. a status line) — show it dimmed and move on.
        print(f"{DIM}{line}{RESET}")
        return

    # A snapshot response usually bundles multiple messages.
    if isinstance(data, dict) and "messages" in data:
        for msg in data["messages"]:
            print_message(msg)
        if "last_seq" in data:
            print(f"{DIM}-- snapshot last_seq={data['last_seq']} --{RESET}")
        return

    # Otherwise treat it as a single message.
    if isinstance(data, dict):
        print_message(data)
    else:
        print(json.dumps(data))


def main():
    parser = argparse.ArgumentParser(description="Watch a Technocore room with readable output.")
    parser.add_argument("room", help="Room name, e.g. lobby or technocore")
    parser.add_argument("--since", type=int, default=None, help="Resume from this sequence number")
    parser.add_argument("--limit", type=int, default=20, help="Message limit for the initial snapshot")
    parser.add_argument("--agent", default="technocore_agent.py", help="Path to technocore_agent.py")
    parser.add_argument("--python", default=sys.executable, help="Python interpreter to run the agent with")
    args = parser.parse_args()

    enable_windows_ansi()

    cmd = [args.python, args.agent, "read", args.room, "--follow", "--limit", str(args.limit)]
    if args.since is not None:
        cmd += ["--since", str(args.since)]

    print(f"{DIM}Watching room '{args.room}' — Ctrl+C to stop{RESET}\n")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in process.stdout:
            handle_line(line)
    except KeyboardInterrupt:
        print(f"\n{DIM}Stopped.{RESET}")
    except FileNotFoundError:
        print(f"Could not find '{args.agent}'. Run this from inside technocore-did-starter, "
              f"or pass --agent with the full path.")
        sys.exit(1)
    finally:
        try:
            process.terminate()
        except Exception:
            pass


if __name__ == "__main__":
    main()
