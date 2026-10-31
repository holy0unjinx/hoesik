#!/usr/bin/env python3
"""매달 8일 03:17 (Asia/Seoul)에 cron_update.sh 를 한 번 돌린다."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("TZ", "Asia/Seoul"))
REPO = os.environ.get("HOESIK_REPO", "/repo")
JOB = ["bash", "scripts/cron_update.sh"]


def now() -> datetime:
    return datetime.now(TZ)


def next_run(after: datetime) -> datetime:
    target = after.replace(day=8, hour=3, minute=17, second=0, microsecond=0)
    if after >= target:
        month = 1 if after.month == 12 else after.month + 1
        year = after.year + 1 if after.month == 12 else after.year
        target = target.replace(year=year, month=month)
    return target


def main() -> int:
    print(f"schedule: monthly 8th 03:17 {TZ.key}, cwd={REPO}", flush=True)
    while True:
        nxt = next_run(now())
        wait = max(1.0, (nxt - now()).total_seconds())
        print(f"next {nxt.isoformat()} (in {timedelta(seconds=int(wait))})", flush=True)
        deadline = time.time() + wait
        while time.time() < deadline:
            time.sleep(min(30.0, max(0.2, deadline - time.time())))
        print(f"run {now().isoformat()}", flush=True)
        try:
            result = subprocess.run(JOB, cwd=REPO)
        except OSError as exc:
            print(f"job failed to start: {exc}", flush=True)
            continue
        print(f"job exit {result.returncode}", flush=True)
        time.sleep(60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
