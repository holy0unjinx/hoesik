#!/usr/bin/env python3
"""Start uvicorn (loopback) and nginx (port 80) in one container."""
from __future__ import annotations

import signal
import subprocess
import sys
import time

PROCS: list[subprocess.Popen] = []


def shutdown(_signum=None, _frame=None) -> None:
    for p in PROCS:
        if p.poll() is None:
            p.terminate()
    deadline = time.time() + 8
    for p in PROCS:
        remaining = max(0.1, deadline - time.time())
        try:
            p.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            p.kill()
    sys.exit(0)


def main() -> None:
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    PROCS.append(subprocess.Popen([
        "uvicorn", "api:app",
        "--host", "127.0.0.1",
        "--port", "8000",
        "--root-path", "/api",
        "--log-level", "info",
    ], cwd="/app"))
    PROCS.append(subprocess.Popen(["nginx", "-g", "daemon off;"]))
    while True:
        for p in PROCS:
            code = p.poll()
            if code is not None:
                shutdown()
                sys.exit(code or 1)
        time.sleep(0.4)


if __name__ == "__main__":
    main()
