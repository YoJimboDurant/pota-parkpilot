#!/usr/bin/env python3

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_X = sys.executable
WEB_SCRIPT_X = PROJECT_ROOT / "scripts" / "start_web.py"
WSJTX_SCRIPT_X = PROJECT_ROOT / "scripts" / "start_wsjtx_service.py"


def _spawn_process(script_path_x: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [PYTHON_X, str(script_path_x)],
        cwd=str(PROJECT_ROOT),
        env=os.environ.copy(),
    )


def _terminate_process(proc_x: subprocess.Popen | None, name_x: str) -> None:
    if proc_x is None or proc_x.poll() is not None:
        return

    print(f"Stopping {name_x}...")
    proc_x.terminate()

    try:
        proc_x.wait(timeout=5)
    except subprocess.TimeoutExpired:
        print(f"Force killing {name_x}...")
        proc_x.kill()
        proc_x.wait(timeout=5)


def main() -> int:
    web_proc_x: subprocess.Popen | None = None
    wsjtx_proc_x: subprocess.Popen | None = None

    try:
        print("Starting ParkPilot launcher")
        print(f"Project root: {PROJECT_ROOT}")
        print("Launching WSJT-X monitor...")
        wsjtx_proc_x = _spawn_process(WSJTX_SCRIPT_X)

        time.sleep(1)

        if wsjtx_proc_x.poll() is not None:
            print("WSJT-X monitor exited immediately.")
            return wsjtx_proc_x.returncode or 1

        print("Launching web app...")
        web_proc_x = _spawn_process(WEB_SCRIPT_X)

        while True:
            if wsjtx_proc_x.poll() is not None:
                print("WSJT-X monitor stopped.")
                return wsjtx_proc_x.returncode or 1

            if web_proc_x.poll() is not None:
                print("Web app stopped.")
                return web_proc_x.returncode or 1

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nCaught Ctrl+C. Shutting down...")
        return 0
    finally:
        _terminate_process(web_proc_x, "web app")
        _terminate_process(wsjtx_proc_x, "WSJT-X monitor")


if __name__ == "__main__":
    raise SystemExit(main())
