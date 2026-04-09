# Story 1.4: Counter Service — Vehicle Detection Pipeline

Status: ready-for-dev

## Story

As the system,
I want to run YOLOv8 vehicle detection when Frigate reports motion in a parking zone,
So that only confirmed vehicles (not shadows, animals, or pedestrians) increment the zone counter.

## Acceptance Criteria

1. **Given** a `frigate/events` MQTT message for a zone_id that exists in `zones.yaml`, **When** the counter service receives it, **Then** it captures the relevant camera frame for AI inference within 5 seconds of the event timestamp.

2. **Given** a captured frame passed to the inference module, **When** YOLOv8 runs, **Then** only detections with confidence ≥ `YOLO_CONFIDENCE_THRESHOLD` (default 0.65) are returned — lower-confidence detections are discarded.

3. **Given** YOLOv8 inference results for a zone whose `vehicle_classes` includes `"car"`, **When** a car is detected above threshold, **Then** it is counted; when a pedestrian or bicycle is detected — regardless of confidence — it is not counted.

4. **Given** YOLOv8 inference is running (CPU/GPU-bound work), **When** called from the async service, **Then** it executes inside `asyncio.to_thread()` so the service's async event loop is not blocked.

5. **Given** the counter Dockerfile, **When** built, **Then** YOLOv8n model weights (`yolov8n.pt`) are downloaded during the build step — the container does not require internet access at runtime.

6. **Given** a `frigate/events` message for a `zone_id` not present in `zones.yaml`, **When** received by the counter, **Then** the event is silently ignored with a DEBUG-level log entry — no error is raised.

## Tasks / Subtasks

- [ ] Task 1: Create inference module with YOLOv8 and class/confidence filter (AC: 2, 3, 4)
  - [ ] Create `services/counter/src/counter/inference.py`
  - [ ] Define `detect_vehicles(frame_bytes: bytes, zone_config: ZoneConfig, confidence_threshold: float) -> int` — returns vehicle count for the zone
  - [ ] Use `asyncio.to_thread(...)` wrapper so inference never blocks the event loop
  - [ ] Load YOLOv8n model once at module import: `_model = YOLO("yolov8n.pt")` — do NOT reload per inference
  - [ ] Filter results: only count classes in `zone_config.vehicle_classes` AND confidence ≥ `confidence_threshold`
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 2: Create Frigate MQTT event handler (AC: 1, 5, 6)
  - [ ] Create `services/counter/src/counter/mqtt_handler.py`
  - [ ] Implement `FrigateEventHandler` class that subscribes to `frigate/events`
  - [ ] On `type == "new"` event: look up zone by `event["after"]["camera"]` in zone index; skip if not found (DEBUG log)
  - [ ] Fetch snapshot from Frigate HTTP API: `GET http://{FRIGATE_HOST}:5000/api/events/{event_id}/snapshot.jpg`
  - [ ] Use `httpx.AsyncClient` for HTTP fetch — never `requests` (sync) in async context
  - [ ] Call `inference.detect_vehicles_async(frame_bytes, zone_config, settings.yolo_confidence_threshold)`
  - [ ] For now: log the vehicle count at INFO; state machine integration in Story 1.5
  - [ ] Wrap all message processing in `try/except Exception`: log ERROR, continue — never crash on bad message
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 3: Create MQTT state publisher (AC: 1)
  - [ ] Create `services/counter/src/counter/publisher.py`
  - [ ] Implement `publish_zone_state(client: MQTTClientManager, state: ZoneState) -> None`
  - [ ] Topic: `parking/{zone_id}/state`, retained=True, qos=1
  - [ ] Serialize `ZoneState` as JSON: `state.model_dump_json()`
  - [ ] Log at INFO: `"Published zone state: {zone_id} {vehicle_count}/{capacity} ({occupancy_pct:.0%}) status={status}"`
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 4: Wire mqtt_handler into main.py (AC: 1, 5)
  - [ ] Update `services/counter/src/counter/main.py`
  - [ ] Add `FRIGATE_HOST` setting to `CounterSettings` (default `"frigate"`)
  - [ ] Start MQTT subscriber loop as asyncio task; MQTT client in outer context
  - [ ] Maintain zone index: `{zone_id: ZoneConfig}` for O(1) lookup in handler
  - [ ] Keep graceful `await asyncio.sleep(float("inf"))` pattern — Story 1.6 adds SIGTERM handler
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 5: Update Dockerfile to pre-download YOLOv8 weights (AC: 5)
  - [ ] Verify `services/counter/Dockerfile` already has: `RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"` (from Story 1.1)
  - [ ] If missing, add the line; no other Dockerfile changes needed

- [ ] Task 6: Write pytest tests for inference module (AC: 2, 3, 4)
  - [ ] Create `services/counter/tests/test_inference.py`
  - [ ] Test: detections below confidence threshold are excluded (mock model output)
  - [ ] Test: classes not in `vehicle_classes` are excluded (e.g. `"person"` excluded even if above threshold)
  - [ ] Test: multiple vehicles of allowed classes all counted
  - [ ] Test: empty detections → returns 0
  - [ ] Use `unittest.mock.patch` to mock `YOLO.__call__` — do NOT depend on actual model weights in tests
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 7: Validate end-to-end (AC: all)
  - [ ] Confirm all new/modified files pass `python3 -m py_compile`
  - [ ] Run inference tests: `PYTHONPATH=shared/src:services/counter/src python3 -m pytest services/counter/tests/test_inference.py -v`

## Dev Notes

### Dependency on Previous Stories

- Story 1.2: `CounterSettings`, `load_zones()`, `zone_loader.py` all exist — import them
- Story 1.3: Frigate camera names match zone_ids; snapshot API available at `http://frigate:5000`
- Story 1.1: `shared/models.py` `ZoneConfig`, `ZoneState` exist; `shared/mqtt.py` `MQTTClientManager` exists

### YOLOv8 — Critical Implementation Notes

**Model loading (module-level singleton):**
```python
from ultralytics import YOLO

_model: YOLO | None = None

def _get_model() -> YOLO:
    global _model
    if _model is None:
        _model = YOLO("yolov8n.pt")
    return _model
```
Load once at first call, not at module import (avoids GPU init on import). The YOLO() call downloads weights if not cached — in Docker, weights are pre-downloaded at build time to `/root/.config/ultralytics/`.

**Async wrapper pattern — MANDATORY:**
```python
import asyncio
from ultralytics import YOLO

async def detect_vehicles_async(
    frame_bytes: bytes,
    zone_config: ZoneConfig,
    confidence_threshold: float,
) -> int:
    """Run YOLOv8 inference in thread pool to avoid blocking event loop."""
    return await asyncio.to_thread(
        _detect_vehicles_sync, frame_bytes, zone_config, confidence_threshold
    )


def _detect_vehicles_sync(
    frame_bytes: bytes,
    zone_config: ZoneConfig,
    confidence_threshold: float,
) -> int:
    """Sync inference — called via asyncio.to_thread only."""
    import io
    import numpy as np
    from PIL import Image

    model = _get_model()
    image = Image.open(io.BytesIO(frame_bytes))
    results = model(image, conf=confidence_threshold, verbose=False)

    count = 0
    allowed_classes = set(zone_config.vehicle_classes)
    for result in results:
        for box in result.boxes:
            label = model.names[int(box.cls)]
            confidence = float(box.conf)
            if label in allowed_classes and confidence >= confidence_threshold:
                count += 1
    return count
```

**Never call `model(...)` inside `async def` without `asyncio.to_thread`** — it blocks the event loop for 200ms–2s.

### Frigate Event MQTT Parsing

Frigate publishes JSON to `frigate/events`. Parse with care:

```python
import json

async def handle_frigate_event(payload: bytes, zones: dict[str, ZoneConfig], settings: CounterSettings) -> None:
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in frigate/events payload")
        return

    if event.get("type") != "new":
        return  # Only process new events; ignore "update" and "end"

    after = event.get("after", {})
    camera_name = after.get("camera", "")
    event_id = after.get("id", "")

    zone_config = zones.get(camera_name)
    if zone_config is None:
        logger.debug("Ignoring frigate event for unknown camera: %s", camera_name)
        return

    # Fetch snapshot from Frigate HTTP API
    snapshot_url = f"http://{settings.frigate_host}:5000/api/events/{event_id}/snapshot.jpg"
    ...
```

### Fetching Snapshots from Frigate

Use `httpx.AsyncClient` — never `requests`:

```python
import httpx

async def fetch_snapshot(event_id: str, frigate_host: str) -> bytes | None:
    url = f"http://{frigate_host}:5000/api/events/{event_id}/snapshot.jpg"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch snapshot for event %s: %s", event_id, exc)
        return None
```

If snapshot fetch fails → log WARNING, skip inference for this event. Do not crash.

### CounterSettings Additions for This Story

Add to `services/counter/src/counter/config.py`:
```python
from pydantic_settings import SettingsConfigDict
from shared.config import BaseServiceSettings
from pathlib import Path

class CounterSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    zones_config_path: Path = Path("/config/zones.yaml")
    yolo_confidence_threshold: float = 0.65
    frigate_host: str = "frigate"   # <-- ADD THIS
```

`httpx` must also be added as a dependency. Add to `services/counter/pyproject.toml`:
```toml
dependencies = [
    "shared",
    "ultralytics>=8.0",
    "aiomqtt>=2.0",
    "pydantic-settings>=2.0",
    "pyyaml>=6.0",
    "httpx>=0.27",      # <-- ADD THIS
    "Pillow>=10.0",     # <-- ADD THIS (for image loading from bytes)
]
```

### Publisher — ZoneState Construction (Story 1.5 placeholder)

In this story (before the state machine exists in Story 1.5), the publisher constructs a minimal ZoneState directly from inference output. Story 1.5 will replace this with the proper state machine:

```python
from datetime import datetime, timezone
from shared.models import ZoneState

def build_zone_state(zone_config: ZoneConfig, vehicle_count: int) -> ZoneState:
    occupancy_pct = vehicle_count / zone_config.capacity
    if occupancy_pct >= 1.0:
        status = "full"
    elif occupancy_pct >= zone_config.threshold:
        status = "warning"
    else:
        status = "ok"
    return ZoneState(
        zone_id=zone_config.zone_id,
        vehicle_count=vehicle_count,
        capacity=zone_config.capacity,
        occupancy_pct=round(occupancy_pct, 4),
        status=status,
        alert_armed=True,   # placeholder; Story 1.5 manages this
        stream_healthy=True,  # placeholder; Story 1.6 manages this
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
```

### MQTT Subscription Pattern (aiomqtt 2.x)

```python
import asyncio
import aiomqtt

async def run_frigate_subscriber(settings: CounterSettings, zones: dict[str, ZoneConfig]) -> None:
    async with aiomqtt.Client(hostname=settings.mqtt_host, port=settings.mqtt_port) as client:
        await client.subscribe("frigate/events", qos=1)
        async for message in client.messages:
            try:
                await handle_frigate_event(bytes(message.payload), zones, settings)
            except Exception as exc:
                logger.error("Error handling frigate event: %s", exc, exc_info=True)
```

Note: `aiomqtt 2.x` uses `async with aiomqtt.Client(...)` — the `Client` is the entry point, not `aiomqtt.connect()`.

### Updated main.py Pattern

```python
async def main() -> None:
    logging.basicConfig(...)
    settings = CounterSettings()
    zones_list = load_zones(settings.zones_config_path)
    zones = {z.zone_id: z for z in zones_list}
    logger.info("Loaded %d zones: %s", len(zones), list(zones.keys()))

    # Start Frigate event subscriber
    asyncio.create_task(run_frigate_subscriber(settings, zones))

    await asyncio.sleep(float("inf"))  # Story 1.6 will replace with SIGTERM-aware loop
```

### Test Mocking Strategy for YOLOv8

Do NOT load real model weights in tests — too slow, requires download:

```python
from unittest.mock import patch, MagicMock
import pytest
from counter.inference import _detect_vehicles_sync
from shared.models import ZoneConfig

ZONE = ZoneConfig(
    zone_id="lot-a", name="Lot A",
    camera_rtsp_sub="rtsp://x:x@192.168.1.10:554/Streaming/Channels/101",
    capacity=50, threshold=0.8, rearm_threshold=0.7,
    vehicle_classes=["car", "truck"],
)

def make_mock_result(detections: list[tuple[str, float]]):
    """Build mock ultralytics Results object."""
    result = MagicMock()
    boxes = []
    for label, confidence in detections:
        box = MagicMock()
        box.cls = [0]  # class index; names dict maps it
        box.conf = [confidence]
        boxes.append(box)
    result.boxes = boxes
    return result

def test_class_filter_excludes_person():
    fake_result = make_mock_result([("person", 0.9), ("car", 0.8)])
    with patch("counter.inference._get_model") as mock_model_fn:
        mock_model = MagicMock()
        mock_model.names = {0: "person", 1: "car"}
        # car box: cls=1, person box: cls=0
        car_box = MagicMock(); car_box.cls = [1]; car_box.conf = [0.8]
        person_box = MagicMock(); person_box.cls = [0]; person_box.conf = [0.9]
        result = MagicMock(); result.boxes = [car_box, person_box]
        mock_model.return_value = [result]
        mock_model_fn.return_value = mock_model

        # Expect only 1 car counted (person excluded)
        count = _detect_vehicles_sync(b"fake-image-bytes", ZONE, 0.65)
        assert count == 1
```

### Anti-Patterns — FORBIDDEN

- ❌ `import requests` — use `httpx.AsyncClient`
- ❌ `model = YOLO("yolov8n.pt")` inside `async def` — always via `asyncio.to_thread`
- ❌ `model = YOLO(...)` called per-inference — load once, reuse
- ❌ `event["type"] == "new"` without `.get()` — use `.get("type")` to handle malformed payloads
- ❌ `yaml.load(...)` — use `yaml.safe_load(...)`
- ❌ Broad `except Exception` at top level without logging — always log with `exc_info=True`

### Architecture References

- inference.py: architecture.md → `counter/inference.py` (FR-011 two-stage, FR-012 class filter)
- mqtt_handler.py: architecture.md → `counter/mqtt_handler.py`
- publisher.py: architecture.md → `counter/publisher.py`
- MQTT patterns: architecture.md → "Communication Patterns" (retained=True on zone state topics)
- Async discipline: architecture.md → "Async Discipline" (asyncio.to_thread for blocking I/O)

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

_to be filled by dev agent_

### Completion Notes List

_to be filled by dev agent_

### File List

- `services/counter/pyproject.toml` (modified — add httpx, Pillow)
- `services/counter/src/counter/config.py` (modified — add frigate_host)
- `services/counter/src/counter/inference.py` (new)
- `services/counter/src/counter/mqtt_handler.py` (new)
- `services/counter/src/counter/publisher.py` (new)
- `services/counter/src/counter/main.py` (modified — wire mqtt_handler)
- `services/counter/tests/test_inference.py` (new)
