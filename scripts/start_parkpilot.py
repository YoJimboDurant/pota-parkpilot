#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_X = sys.executable


def _spawn_module(module_name_x: str) -> subprocess.Popen:
    return subprocess.Popen(
        [PYTHON_X, "-m", module_name_x],
        cwd=str(PROJECT_ROOT),
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
        wsjtx_proc_x = _spawn_module("scripts.start_wsjtx_service")

        time.sleep(1)

        if wsjtx_proc_x.poll() is not None:
            print("WSJT-X monitor exited immediately.")
            return wsjtx_proc_x.returncode or 1

        print("Launching web app...")
        web_proc_x = _spawn_module("scripts.start_web")

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