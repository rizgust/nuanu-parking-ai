"""Counter service entry point.

Responsibilities (implemented in later stories):
- Load zone config from config/zones.yaml
- Subscribe to frigate/events MQTT topic
- On motion event: run YOLOv8 inference (Story 1.4)
- Update zone state machine with debounce (Story 1.5)
- Publish zone state to parking/{zone_id}/state (Story 1.5)
- Handle RTSP reconnect with exponential backoff (Story 1.6)
- Publish heartbeat to parking/system/health every 60s
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"level": "%(levelname)s", "service": "counter", "message": "%(message)s"}',
    )
    logger.info("Counter service starting — implementation pending (Stories 1.2–1.6)")
    # TODO: implement in Stories 1.2–1.6
    await asyncio.sleep(float("inf"))


if __name__ == "__main__":
    asyncio.run(main())
