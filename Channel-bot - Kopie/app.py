"""Launcher for Channel Manager bot and dashboard.

This script starts the Discord bot (src.bot) and the web dashboard (src.web.dashboard)
using separate subprocesses. It checks for .env presence before launching.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


def ensure_env() -> None:
    """Ensure .env exists so downstream services can load credentials."""
    if not ENV_PATH.exists():
        print("[ERROR] .env file not found. Copy .env.example to .env and fill your values.")
        sys.exit(1)


def start_process(name: str, args: List[str]) -> subprocess.Popen:
    """Start a subprocess with inherited environment and project working directory."""
    print(f"[START] {name}: {' '.join(args)}")
    return subprocess.Popen(args, cwd=str(ROOT), env=os.environ.copy())


def main() -> None:
    ensure_env()

    # Load .env so both bot and dashboard get OAuth/env config
    load_dotenv(dotenv_path=ENV_PATH)

    processes: List[Tuple[str, subprocess.Popen]] = []
    python_exe = sys.executable

    # Start Discord bot
    bot_proc = start_process("Discord bot", [python_exe, "-m", "src.bot"])
    processes.append(("Discord bot", bot_proc))

    # Small delay to avoid overlapping startup logs
    time.sleep(1.0)

    # Start dashboard
    dashboard_proc = start_process("Dashboard", [python_exe, "src/web/dashboard.py"])
    processes.append(("Dashboard", dashboard_proc))

    dashboard_port = os.getenv("DASHBOARD_PORT", "6767")
    print(f"[INFO] Dashboard available at http://jthweb.yugp.me:{dashboard_port}")
    print("[INFO] Press Ctrl+C to stop both services.")

    try:
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"[WARN] {name} exited with code {ret}. Stopping remaining processes.")
                    raise SystemExit(ret)
            time.sleep(1.0)
    except (KeyboardInterrupt, SystemExit):
        print("[INFO] Shutting down processes...")
        for name, proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for name, proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print(f"[WARN] {name} did not exit in time; killing.")
                proc.kill()
        print("[INFO] All processes stopped.")


if __name__ == "__main__":
    main()
