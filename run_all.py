#!/usr/bin/env python3
"""Master runner: execute all Technocore modules in order."""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("/home/ubuntu/technocore-did-starter")
PY = BASE / ".venv/bin/python"
MODULES = [
    ("Agent", BASE / "flop_live.py"),
    ("Dashboard Build", BASE / "dashboard/build_dashboard.py"),
    ("Dashboard Render", BASE / "dashboard/render_dashboard.py"),
    ("Keyword Watcher", BASE / "notifier/keyword_watcher.py"),
    ("Auto Welcome", BASE / "notifier/auto_welcome.py"),
    ("Daily Proof", BASE / "proof/daily_proof.py"),
    ("Leaderboard", BASE / "leaderboard/scoreboard.py"),
    ("Monitor", BASE / "monitor/rate_limit_monitor.py"),
]

def run(label, script):
    print(f"\n=== {label} ===")
    r = subprocess.run(
        [str(PY), str(script)],
        capture_output=True,
        text=True,
        cwd=str(BASE),
    )
    if r.stdout:
        print(r.stdout.strip())
    if r.returncode != 0:
        print(f"FAILED: {label}")
        if r.stderr:
            print(r.stderr[:300])
        # don't abort everything for one module
    else:
        print(f"OK: {label}")

def main():
    print(f"Technocore master runner @ {datetime.now(timezone.utc).isoformat()}")
    for label, script in MODULES:
        run(label, script)
    print("\n=== DONE ===")

if __name__ == "__main__":
    from datetime import datetime, timezone
    main()
