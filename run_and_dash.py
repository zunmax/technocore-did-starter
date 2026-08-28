#!/usr/bin/env python3
"""One-click: run agent + refresh dashboard."""
import subprocess
import sys
from pathlib import Path

BASE = Path("/home/ubuntu/technocore-did-starter")
PY = BASE / ".venv/bin/python"
LIVE = BASE / "flop_live.py"
DASH_BUILD = BASE / "dashboard/build_dashboard.py"
DASH_RENDER = BASE / "dashboard/render_dashboard.py"

def run(cmd, label):
    print(f"\n=== {label} ===")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.stdout:
        print(r.stdout.strip())
    if r.returncode != 0:
        print(f"FAILED: {r.stderr[:300]}")
        sys.exit(1)

run(f"cd {BASE} && {PY} {LIVE}", "AGENT RUN")
run(f"cd {BASE}/dashboard && {PY} {DASH_BUILD} dashboard.json", "BUILD DASHBOARD JSON")
run(f"cd {BASE}/dashboard && {PY} {DASH_RENDER}", "RENDER DASHBOARD HTML")
print("\nDone. Open dashboard:")
print(f"file://{BASE}/dashboard/index.html")
