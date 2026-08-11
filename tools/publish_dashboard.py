import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INTERVAL_SECONDS = 300  # 5 minutes

def run_git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True
    )

while True:
    status = run_git(
        "status",
        "--porcelain",
        "dashboard/data/latest.json",
        "dashboard/data/history.json"
    )

    if status.stdout.strip():
        run_git(
            "add",
            "dashboard/data/latest.json",
            "dashboard/data/history.json"
        )

        commit = run_git(
            "commit",
            "-m",
            "Update live sensor dashboard"
        )

        if commit.returncode == 0:
            push = run_git("push", "origin", "main")

            if push.returncode == 0:
                print("Dashboard pushed to GitHub.")
            else:
                print("Git push failed:")
                print(push.stderr)

    time.sleep(INTERVAL_SECONDS)
