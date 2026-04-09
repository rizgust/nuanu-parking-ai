"""Watchdog service entry point.

Responsibilities (implemented in Story 2.2):
- Subscribe to parking/+/state for stream_healthy monitoring
- Subscribe to parking/system/health for heartbeat tracking
- Alert via Telegram on: heartbeat timeout, container unhealthy, stream loss
- Monitor Docker container health via Docker socket
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"level": "%(levelname)s", "service": "watchdog", "message": "%(message)s"}',
    )
    logger.info("Watchdog service starting — implementation pending (Story 2.2)")
    await asyncio.sleep(float("inf"))


if __name__ == "__main__":
    asyncio.run(main())
