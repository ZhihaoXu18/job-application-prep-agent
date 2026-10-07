#!/usr/bin/env python3
"""One-command offline acceptance suite. Uses only synthetic/mock data."""

import shutil
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    node = shutil.which("node")
    if node is None:
        print("Node.js is required for the frontend checks; no software was installed.", file=sys.stderr)
        return 1
    checks = (
        [sys.executable, "-m", "unittest", "-v", "test_job_agent.py", "test_web_ui.py",
         "test_direction_suggestions.py", "test_status_history.py", "test_resume_evidence.py", "test_direction_report.py"],
        [node, "--check", "web/app.js"],
        [node, "test_web_app.cjs"],
    )
    for command in checks:
        result = subprocess.run(command, cwd=root, check=False)
        if result.returncode:
            return result.returncode
    print("Week 2 offline acceptance checks passed. No paid model calls or live vacancy validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
