from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

from sqlalchemy import text

from .core.database import async_session, engine


def heartbeat_is_fresh(path: Path, max_age_seconds: int, now: int | None = None) -> bool:
    try:
        recorded_at = int(path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return False
    current_time = int(time.time()) if now is None else now
    age = current_time - recorded_at
    return 0 <= age <= max_age_seconds


async def check_worker() -> None:
    interval = max(5, min(int(os.getenv("WORKER_INTERVAL_SECONDS", "60")), 3600))
    max_age = max(90, interval * 3)
    heartbeat = Path(os.getenv("WORKER_HEARTBEAT_FILE", "/tmp/automation-worker-heartbeat"))
    if not heartbeat_is_fresh(heartbeat, max_age):
        raise RuntimeError("worker heartbeat is missing or stale")

    try:
        async with async_session() as db:
            await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=5)
    finally:
        await engine.dispose()


def main() -> int:
    try:
        asyncio.run(check_worker())
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
