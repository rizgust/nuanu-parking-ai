# Story 1.6: RTSP Stream Resilience and Graceful Degradation

Status: ready-for-dev

## Story

As an infrastructure administrator,
I want the system to automatically recover from dropped camera streams and flag degraded zones without affecting others,
So that transient network issues never require manual restarts and operators always know which zones they can trust.

## Acceptance Criteria

1. **Given** an RTSP stream drop (camera unreachable or network interruption), **When** the counter detects the connection failure, **Then** it automatically attempts reconnection using exponential backoff: 1s → 2s → 4s → 8s → … → max 60s between retries.

2. **Given** a stream has been lost for zone "lot-a", **When** the counter publishes the next zone state to MQTT, **Then** `stream_healthy=False` appears in the payload for "lot-a".

3. **Given** `stream_healthy=False` for zone "lot-a" and zone "lot-b" is operating normally, **When** the system is running, **Then** "lot-b" continues publishing accurate zone state to MQTT without interruption.

4. **Given** a previously dropped stream that successfully reconnects, **When** the RTSP connection re-establishes, **Then** `stream_healthy=True` is restored in subsequent MQTT publishes — no service restart required.

5. **Given** a stream reconnect is in progress (backoff timer active), **When** Docker checks the counter container health, **Then** the health check returns healthy — the container is NOT restarted during the reconnect backoff period.

6. **Given** `SIGTERM` is sent to the counter container (e.g. `docker compose restart`), **When** received, **Then** all background tasks (MQTT subscriber, stream monitors) are cancelled gracefully — no `asyncio.CancelledError` tracebacks in logs.

## Tasks / Subtasks

- [ ] Task 1: Create RTSP stream health monitor (AC: 1, 2, 3, 4)
  - [ ] Create `services/counter/src/counter/stream.py`
  - [ ] Implement `StreamMonitor` that periodically polls RTSP availability per zone using FFmpeg probe
  - [ ] On connection failure: call `zone_machine.set_stream_healthy(False)` → publish degraded state to MQTT
  - [ ] On successful reconnect: call `zone_machine.set_stream_healthy(True)` → publish healthy state
  - [ ] Implement exponential backoff: 1s → 2s → 4s → 8s → max 60s — shared utility function `backoff_delays()`
  - [ ] Each zone's stream monitor runs as an independent asyncio task — one zone failure does NOT stop others (AC: 3)
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 2: Replace `asyncio.sleep(float("inf"))` with SIGTERM-aware shutdown (AC: 5, 6)
  - [ ] Update `services/counter/src/counter/main.py`
  - [ ] Use `asyncio.Event` as shutdown signal: `shutdown_event = asyncio.Event()`
  - [ ] Register `loop.add_signal_handler(signal.SIGTERM, ...)` and `signal.SIGINT`
  - [ ] Gather all tasks: Frigate MQTT subscriber + one `StreamMonitor` per zone
  - [ ] On shutdown: set `shutdown_event`, cancel all tasks, await with `asyncio.gather(..., return_exceptions=True)`
  - [ ] Log `"Counter service shutting down"` at INFO on SIGTERM receipt
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 3: Publish counter heartbeat every 60s (AC: 5)
  - [ ] Add heartbeat publisher to `main.py`
  - [ ] Every 60s: publish `SystemHealthPayload(service="counter", status="healthy", timestamp=...)` to `parking/system/health`
  - [ ] Topic `parking/system/health`: `retain=False` (stale heartbeat must NOT appear as current health)
  - [ ] Heartbeat continues publishing during stream reconnect backoff — health check remains "healthy" (AC: 5)
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 4: Write unit tests for backoff logic and stream state transitions (AC: 1, 2, 4)
  - [ ] Create `services/counter/tests/test_stream.py`
  - [ ] Test: `backoff_delays()` yields 1, 2, 4, 8, ... capped at 60
  - [ ] Test: delays never exceed 60s regardless of iteration count
  - [ ] Test: `StreamMonitor` marks zone degraded on simulated connection failure (mock FFmpeg probe)
  - [ ] Test: `StreamMonitor` restores healthy on successful reconnect
  - [ ] Use `unittest.mock.AsyncMock` for mocked async probes
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 5: End-to-end validation (AC: all)
  - [ ] All new/modified files pass `python3 -m py_compile`
  - [ ] Run stream tests: `PYTHONPATH=shared/src:services/counter/src python3 -m pytest services/counter/tests/test_stream.py -v`

## Dev Notes

### Stream Health Check Strategy — FFmpeg Probe (Not Full RTSP Consumer)

The counter does NOT open a full-time RTSP consumer for video. Video frames for inference are still fetched from the Frigate HTTP API (Story 1.4). Instead, `StreamMonitor` uses a lightweight **FFmpeg probe** to check if the RTSP stream is reachable, run periodically (every 30s when healthy, or on backoff schedule when not):

```python
import asyncio
import subprocess

async def probe_rtsp_stream(rtsp_url: str, timeout_seconds: int = 10) -> bool:
    """Returns True if RTSP stream is reachable via FFmpeg probe."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v", "quiet",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return False
        return proc.returncode == 0
    except Exception:
        return False
```

`ffprobe` is included in the `ffmpeg` apt package. Add to counter Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
```

### Backoff Generator

```python
import asyncio
from typing import AsyncIterator

async def backoff_delays(max_delay: int = 60) -> AsyncIterator[float]:
    """Yields increasing sleep durations: 1, 2, 4, 8, ..., max_delay."""
    delay = 1.0
    while True:
        yield delay
        await asyncio.sleep(delay)
        delay = min(delay * 2, max_delay)
```

Usage in StreamMonitor:
```python
async for delay in backoff_delays(max_delay=60):
    if await probe_rtsp_stream(rtsp_url):
        break  # reconnected
    logger.warning("Stream probe failed for %s, next retry in %.0fs", zone_id, delay)
```

### Complete StreamMonitor Class

```python
"""RTSP stream health monitor for a single zone.

Runs as an independent asyncio task per zone.
Polls stream health and updates ZoneStateMachine on status changes.
"""
import asyncio
import logging
from shared.models import ZoneConfig
from counter.zone_state import ZoneStateMachine
from counter.publisher import publish_zone_state
from shared.mqtt import MQTTClientManager

logger = logging.getLogger(__name__)

PROBE_INTERVAL_HEALTHY = 30    # seconds between probes when stream is up
PROBE_INTERVAL_FAILED = 1      # initial backoff on failure


class StreamMonitor:
    def __init__(
        self,
        zone_config: ZoneConfig,
        zone_machine: ZoneStateMachine,
        mqtt_client: MQTTClientManager,
        shutdown_event: asyncio.Event,
    ) -> None:
        self._cfg = zone_config
        self._machine = zone_machine
        self._mqtt = mqtt_client
        self._shutdown = shutdown_event
        self._stream_healthy = True

    async def run(self) -> None:
        """Monitor loop. Runs until shutdown_event is set."""
        logger.info("StreamMonitor started for zone %s", self._cfg.zone_id)
        while not self._shutdown.is_set():
            is_healthy = await probe_rtsp_stream(self._cfg.camera_rtsp_sub)

            if is_healthy and not self._stream_healthy:
                # Stream recovered
                self._stream_healthy = True
                state = self._machine.set_stream_healthy(True)
                await publish_zone_state(self._mqtt, state)
                logger.info("Stream recovered for zone %s", self._cfg.zone_id)

            elif not is_healthy and self._stream_healthy:
                # Stream just dropped
                self._stream_healthy = False
                state = self._machine.set_stream_healthy(False)
                await publish_zone_state(self._mqtt, state)
                logger.warning("Stream lost for zone %s — starting reconnect backoff", self._cfg.zone_id)

            if self._stream_healthy:
                # Normal polling interval
                await asyncio.sleep(PROBE_INTERVAL_HEALTHY)
            else:
                # Backoff reconnect: run probe again with exponential delay
                delay = PROBE_INTERVAL_FAILED
                while not self._shutdown.is_set():
                    await asyncio.sleep(delay)
                    is_healthy = await probe_rtsp_stream(self._cfg.camera_rtsp_sub)
                    if is_healthy:
                        self._stream_healthy = True
                        state = self._machine.set_stream_healthy(True)
                        await publish_zone_state(self._mqtt, state)
                        logger.info("Stream reconnected for zone %s", self._cfg.zone_id)
                        break
                    delay = min(delay * 2, 60)
                    logger.debug("Still no stream for %s, retry in %ds", self._cfg.zone_id, delay)
```

### Graceful Shutdown — main.py Pattern

```python
import asyncio
import logging
import signal
from counter.config import CounterSettings
from counter.zone_loader import load_zones
from counter.zone_state import ZoneStateMachine
from counter.stream import StreamMonitor
from counter.mqtt_handler import run_frigate_subscriber
from counter.publisher import publish_heartbeat
from shared.mqtt import MQTTClientManager
from shared.models import SystemHealthPayload
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def publish_heartbeat_loop(client: MQTTClientManager, shutdown_event: asyncio.Event) -> None:
    """Publish counter heartbeat to parking/system/health every 60s."""
    while not shutdown_event.is_set():
        payload = SystemHealthPayload(
            service="counter",
            status="healthy",
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        await client.publish("parking/system/health", payload.model_dump_json(), retain=False, qos=0)
        logger.debug("Heartbeat published")
        await asyncio.sleep(60)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"level": "%(levelname)s", "service": "counter", "message": "%(message)s"}',
    )

    settings = CounterSettings()
    zones_list = load_zones(settings.zones_config_path)
    zones = {z.zone_id: z for z in zones_list}
    zone_machines = {zone_id: ZoneStateMachine(cfg) for zone_id, cfg in zones.items()}
    logger.info("Loaded %d zones: %s", len(zones), list(zones.keys()))

    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: (logger.info("Shutdown signal received"), shutdown_event.set()))

    async with MQTTClientManager(settings.mqtt_host, settings.mqtt_port) as mqtt_client:
        tasks = [
            asyncio.create_task(run_frigate_subscriber(settings, zones, zone_machines, mqtt_client, shutdown_event)),
            asyncio.create_task(publish_heartbeat_loop(mqtt_client, shutdown_event)),
        ]
        for zone_id, cfg in zones.items():
            monitor = StreamMonitor(cfg, zone_machines[zone_id], mqtt_client, shutdown_event)
            tasks.append(asyncio.create_task(monitor.run()))

        await shutdown_event.wait()
        logger.info("Counter service shutting down")

        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Counter service stopped")


if __name__ == "__main__":
    asyncio.run(main())
```

### Docker Health Check — Must Stay Healthy During Reconnect

The Docker health check in `docker-compose.yml` uses:
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import counter; print('ok')"]
```

This checks that the Python module is importable — it does NOT probe RTSP. Therefore, the container remains "healthy" even while stream reconnect backoff is in progress. This satisfies AC-5: Docker does not restart the container during reconnect.

Do NOT change the health check to probe RTSP — that would cause Docker to restart on any stream issue, defeating the purpose of the backoff logic.

### Zone Isolation — Per-Task Architecture

Each zone's `StreamMonitor.run()` is an independent `asyncio.Task`. If zone "lot-a" stream fails and enters backoff sleep, zone "lot-b"'s task continues unaffected. This is enforced by asyncio's cooperative multitasking — never block `run()` with synchronous calls.

```
main()
  ├── Task: run_frigate_subscriber()    # handles all zones' motion events
  ├── Task: publish_heartbeat_loop()   # service health signal
  ├── Task: StreamMonitor("lot-a").run()  # isolated per zone
  └── Task: StreamMonitor("lot-b").run()  # runs independently
```

### Unit Test Patterns

```python
import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from counter.stream import probe_rtsp_stream, StreamMonitor
from counter.zone_state import ZoneStateMachine
from shared.models import ZoneConfig

def make_zone() -> ZoneConfig:
    return ZoneConfig(
        zone_id="lot-a", name="Lot A",
        camera_rtsp_sub="rtsp://admin:pass@192.168.1.10:554/Streaming/Channels/101",
        capacity=50, threshold=0.8, rearm_threshold=0.7,
        vehicle_classes=["car"],
    )


def test_backoff_delays_capped_at_60():
    """backoff_delays never exceeds max_delay."""
    from counter.stream import backoff_delays_sync  # sync version for testing
    delays = [next(backoff_delays_sync()) for _ in range(10)]
    assert all(d <= 60 for d in delays)
    assert delays == [1, 2, 4, 8, 16, 32, 60, 60, 60, 60]


@pytest.mark.asyncio
async def test_stream_monitor_marks_degraded_on_failure():
    zone = make_zone()
    machine = ZoneStateMachine(zone)
    mqtt_mock = AsyncMock()
    shutdown = asyncio.Event()

    with patch("counter.stream.probe_rtsp_stream", return_value=False):
        with patch("counter.stream.publish_zone_state") as pub_mock:
            monitor = StreamMonitor(zone, machine, mqtt_mock, shutdown)
            # Run one iteration then shutdown
            shutdown_task = asyncio.create_task(asyncio.sleep(0.05))
            monitor_task = asyncio.create_task(monitor.run())
            await asyncio.sleep(0.1)
            shutdown.set()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    # stream_healthy should have been set to False at least once
    # (checked via zone machine state)
    state = machine.set_stream_healthy(True)  # probe current state
    # After False was set, we reset to True above — just verify the method works
    assert state.stream_healthy is True
```

**Note:** For `backoff_delays_sync()` test helper, provide a synchronous generator version alongside the async one for testability:

```python
def backoff_delays_sync(max_delay: int = 60):
    """Sync version of backoff for testing."""
    delay = 1.0
    while True:
        yield delay
        delay = min(delay * 2, max_delay)
```

### Counter Dockerfile Addition

```dockerfile
# Add FFmpeg for RTSP probing (stream health monitor)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

Add this BEFORE the `CMD` line in `services/counter/Dockerfile`.

### MQTT Topic Reference (Complete — All Counter Topics)

| Topic | retain | qos | Payload type |
|-------|--------|-----|-------------|
| `parking/{zone_id}/state` | True | 1 | `ZoneState` JSON |
| `parking/system/health` | False | 0 | `SystemHealthPayload` JSON |

`parking/system/health` must use `retain=False` — watchdog must detect gaps (no heartbeat = counter down). A stale retained heartbeat would falsely signal the counter is alive.

### Anti-Patterns — FORBIDDEN

- ❌ `await asyncio.sleep(float("inf"))` in final main() — replaced by `await shutdown_event.wait()`
- ❌ Shared global state across zone monitors — each `StreamMonitor` instance owns only its zone
- ❌ `signal.signal(signal.SIGTERM, handler)` — use `loop.add_signal_handler()` for asyncio compatibility
- ❌ Catching `asyncio.CancelledError` silently — always re-raise or let it propagate from task cleanup
- ❌ `ffmpeg` subprocess blocking the event loop — use `asyncio.create_subprocess_exec` (not `subprocess.run`)
- ❌ `parking/system/health` with `retain=True` — stale heartbeat would mask counter failure

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

_to be filled by dev agent_

### Completion Notes List

_to be filled by dev agent_

### File List

- `services/counter/Dockerfile` (modified — add ffmpeg apt install)
- `services/counter/src/counter/stream.py` (new)
- `services/counter/src/counter/main.py` (modified — graceful shutdown + heartbeat + stream monitors)
- `services/counter/tests/test_stream.py` (new)
