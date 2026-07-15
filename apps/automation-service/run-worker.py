import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.core.safe_logging import configure_safe_logging

configure_safe_logging()

from app.worker import run_forever

if __name__ == "__main__":
    interval = int(os.getenv("WORKER_INTERVAL_SECONDS", "60"))
    asyncio.run(run_forever(interval))
