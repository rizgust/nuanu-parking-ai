# Story 1.5: Zone State Machine with Debounce and MQTT Publishing

Status: ready-for-dev

## Story

As the system,
I want a per-zone state machine that tracks vehicle counts with debounce logic and publishes stable zone state to MQTT,
So that transient vehicle movements don't cause counter jitter and all consumers (dashboard, watchdog) always receive accurate, stable zone occupancy.

## Acceptance Criteria

1. **Given** a vehicle detection result for zone "lot-a", **When** `ZoneStateMachine.update()` is called, **Then** it recalculates `vehicle_count`, `occupancy_pct` (float 0.0–1.0), and `status` ("ok"/"warning"/"full") based on zone capacity and threshold.

2. **Given** rapid consecutive detection frames that disagree (e.g. vehicle appears then disappears in alternating frames), **When** debounce logic is applied, **Then** the counter only updates if N consecutive frames agree on the vehicle count (N=`DEBOUNCE_FRAMES`, default 3) — a single divergent frame does not change the count.

3. **Given** a zone state change after debounce, **When** published to MQTT topic `parking/{zone_id}/state`, **Then** the payload exactly matches the canonical schema: `{zone_id, vehicle_count, capacity, occupancy_pct, status, alert_armed, stream_healthy, timestamp}` — no extra or missing fields.

4. **Given** a zone state MQTT publish, **When** sent to the broker, **Then** `retain=True` is set — a new subscriber receives the current state immediately on connection without waiting for the next event.

5. **Given** the counter service starts fresh, **When** it initializes `ZoneStateMachine` for zone "lot-a", **Then** the initial state is: `vehicle_count=0`, `occupancy_pct=0.0`, `status="ok"`, `alert_armed=True`, `stream_healthy=True`.

6. **Given** zone occupancy crosses the threshold (e.g. `occupancy_pct=0.82` with `threshold=0.80`), **When** state is published, **Then** `status="warning"` appears in the MQTT payload.

7. **Given** all `timestamp` values in the payload, **When** inspected, **Then** they use `datetime.now(timezone.utc)` — never naive datetimes.

## Tasks / Subtasks

- [ ] Task 1: Implement ZoneStateMachine class (AC: 1, 2, 5, 6, 7)
  - [ ] Create `services/counter/src/counter/zone_state.py`
  - [ ] `ZoneStateMachine` initialized from `ZoneConfig`; holds per-zone mutable state
  - [ ] Implement `update(new_count: int) -> ZoneState | None` — returns new `ZoneState` if debounce passes, else `None`
  - [ ] Implement debounce: ring buffer of last `DEBOUNCE_FRAMES` counts; publish only when all N frames agree
  - [ ] Implement status logic: `occupancy_pct >= 1.0` → `"full"`, `>= threshold` → `"warning"`, else `"ok"`, `stream_healthy=False` → `"degraded"` (overrides others)
  - [ ] Initial state: `vehicle_count=0`, `occupancy_pct=0.0`, `status="ok"`, `alert_armed=True`, `stream_healthy=True`
  - [ ] Add `set_stream_healthy(healthy: bool) -> ZoneState` — immediately updates stream_healthy and publishes regardless of debounce (Story 1.6 calls this)
  - [ ] Use `datetime.now(timezone.utc)` for all timestamps — never `datetime.now()`
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 2: Integrate state machine into mqtt_handler.py (AC: 1, 3, 4)
  - [ ] Update `services/counter/src/counter/mqtt_handler.py`
  - [ ] Accept `zone_machines: dict[str, ZoneStateMachine]` (one per zone)
  - [ ] After inference returns `vehicle_count`: call `machine.update(vehicle_count)`
  - [ ] If `update()` returns `ZoneState` (debounce passed): call `publisher.publish_zone_state(client, state)`
  - [ ] Remove the Story 1.4 `build_zone_state()` placeholder — state machine is now authoritative
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 3: Update publisher.py to use canonical ZoneState serialization (AC: 3, 4)
  - [ ] Confirm `publisher.publish_zone_state` uses `state.model_dump_json()` for serialization
  - [ ] Confirm `retain=True` and `qos=1` on all `parking/{zone_id}/state` publishes
  - [ ] No structural changes expected — verify only

- [ ] Task 4: Wire ZoneStateMachines into main.py (AC: 5)
  - [ ] Update `services/counter/src/counter/main.py`
  - [ ] After loading zones: instantiate `{zone_id: ZoneStateMachine(zone_config)}` for each zone
  - [ ] Pass `zone_machines` dict to `FrigateEventHandler` / `run_frigate_subscriber`
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 5: Write comprehensive unit tests for state machine (AC: 1, 2, 5, 6, 7)
  - [ ] Create `services/counter/tests/test_zone_state.py`
  - [ ] Test: initial state values are all correct
  - [ ] Test: single update below debounce threshold → returns `None` (no publish)
  - [ ] Test: N identical consecutive updates → returns `ZoneState` with correct fields
  - [ ] Test: N-1 identical then 1 divergent → returns `None` (debounce reset)
  - [ ] Test: occupancy below threshold → `status="ok"`
  - [ ] Test: occupancy at/above threshold → `status="warning"`
  - [ ] Test: occupancy at 100% → `status="full"`
  - [ ] Test: `stream_healthy=False` → `status="degraded"` regardless of occupancy
  - [ ] Test: timestamp uses UTC (ends with `"Z"`)
  - [ ] Test: `alert_armed` starts True
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 6: Validate end-to-end (AC: all)
  - [ ] All files pass `python3 -m py_compile`
  - [ ] Run state machine tests: `PYTHONPATH=shared/src:services/counter/src python3 -m pytest services/counter/tests/test_zone_state.py -v`

## Dev Notes

### ZoneStateMachine — Complete Implementation

```python
"""Per-zone state machine with debounce logic.

Each zone gets its own ZoneStateMachine instance. The machine:
1. Buffers the last DEBOUNCE_FRAMES detection counts
2. Only updates official state when all N frames agree
3. Computes status from occupancy_pct and zone thresholds
4. Tracks alert_armed (for Story 2.1 alert logic)
5. Tracks stream_healthy (for Story 1.6 / degraded status)
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from shared.models import ZoneConfig, ZoneState

DEBOUNCE_FRAMES: int = 3  # consecutive agreeing frames required to update count


class ZoneStateMachine:
    def __init__(self, zone_config: ZoneConfig) -> None:
        self._cfg = zone_config
        self._vehicle_count: int = 0
        self._alert_armed: bool = True
        self._stream_healthy: bool = True
        self._debounce_buffer: deque[int] = deque(maxlen=DEBOUNCE_FRAMES)

    @property
    def zone_id(self) -> str:
        return self._cfg.zone_id

    def update(self, new_count: int) -> ZoneState | None:
        """Process a new inference result.

        Returns ZoneState if debounce passes (N consecutive matching counts),
        or None if more frames are needed before publishing.
        """
        self._debounce_buffer.append(new_count)

        if len(self._debounce_buffer) < DEBOUNCE_FRAMES:
            return None  # buffer not full yet

        # All N frames must agree on the same count
        if len(set(self._debounce_buffer)) != 1:
            return None  # frames disagree — suppress update

        # Debounce passed: commit the new count
        self._vehicle_count = new_count
        return self._build_state()

    def set_stream_healthy(self, healthy: bool) -> ZoneState:
        """Update stream health status immediately — bypasses debounce.

        Called by Story 1.6 stream module on connection events.
        Always returns a ZoneState for immediate publishing.
        """
        self._stream_healthy = healthy
        if not healthy:
            self._debounce_buffer.clear()  # reset debounce on stream loss
        return self._build_state()

    def _build_state(self) -> ZoneState:
        occupancy_pct = self._vehicle_count / self._cfg.capacity
        status = self._compute_status(occupancy_pct)
        return ZoneState(
            zone_id=self._cfg.zone_id,
            vehicle_count=self._vehicle_count,
            capacity=self._cfg.capacity,
            occupancy_pct=round(occupancy_pct, 4),
            status=status,
            alert_armed=self._alert_armed,
            stream_healthy=self._stream_healthy,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    def _compute_status(self, occupancy_pct: float) -> str:
        if not self._stream_healthy:
            return "degraded"
        if occupancy_pct >= 1.0:
            return "full"
        if occupancy_pct >= self._cfg.threshold:
            return "warning"
        return "ok"
```

**Note on `alert_armed` management:** `alert_armed` tracks whether the zone is ready to fire an alert. Full management (setting to False on alert, re-arming below `rearm_threshold`) is implemented in **Story 2.1** (watchdog/alert service). In this story, `alert_armed` stays `True` always — that's correct placeholder behavior.

### Debounce Logic — Explanation

The debounce buffer is a fixed-length `deque(maxlen=N)` that holds the last N inference results.

| Frame | Buffer | All same? | Action |
|-------|--------|-----------|--------|
| 1: count=5 | [5] | no (< N) | return None |
| 2: count=5 | [5, 5] | no (< N) | return None |
| 3: count=5 | [5, 5, 5] | yes | return ZoneState(count=5) |
| 4: count=4 | [5, 5, 4] | no | return None |
| 5: count=4 | [5, 4, 4] | no | return None |
| 6: count=4 | [4, 4, 4] | yes | return ZoneState(count=4) |

This prevents a single divergent frame (vehicle partially in/out of zone) from changing the published count.

### Status Computation Table

| Stream healthy | occupancy_pct | status |
|---------------|---------------|--------|
| False | any | `"degraded"` |
| True | ≥ 1.0 | `"full"` |
| True | ≥ threshold (e.g. 0.80) | `"warning"` |
| True | < threshold | `"ok"` |

### Canonical MQTT Payload (Must Match Exactly)

```json
{
  "zone_id": "lot-a",
  "vehicle_count": 23,
  "capacity": 50,
  "occupancy_pct": 0.46,
  "status": "ok",
  "alert_armed": true,
  "stream_healthy": true,
  "timestamp": "2026-04-09T14:32:00Z"
}
```

Use `ZoneState.model_dump_json()` — Pydantic v2 serializes all fields in declaration order. Never manually construct the JSON dict.

### Publisher Verification

```python
# publisher.py — no changes needed if already correct from Story 1.4
async def publish_zone_state(client: MQTTClientManager, state: ZoneState) -> None:
    topic = f"parking/{state.zone_id}/state"
    await client.publish(topic, state.model_dump_json(), retain=True, qos=1)
    logger.info(
        "Published zone state: %s %d/%d (%.0f%%) status=%s",
        state.zone_id, state.vehicle_count, state.capacity,
        state.occupancy_pct * 100, state.status,
    )
```

Verify: `retain=True` — this is critical. A new dashboard connection gets all zone states immediately from the retained messages without waiting for the next motion event.

### Updated mqtt_handler.py Integration

```python
# In FrigateEventHandler or run_frigate_subscriber:

async def handle_frigate_event(
    payload: bytes,
    zones: dict[str, ZoneConfig],
    zone_machines: dict[str, ZoneStateMachine],  # NEW
    settings: CounterSettings,
    mqtt_client: MQTTClientManager,              # NEW — for publishing
) -> None:
    ...
    # After inference:
    vehicle_count = await detect_vehicles_async(frame_bytes, zone_config, settings.yolo_confidence_threshold)

    # State machine update (replaces Story 1.4 build_zone_state placeholder)
    machine = zone_machines[zone_config.zone_id]
    new_state = machine.update(vehicle_count)
    if new_state is not None:
        await publish_zone_state(mqtt_client, new_state)
```

### Unit Test Patterns

```python
import pytest
from counter.zone_state import ZoneStateMachine, DEBOUNCE_FRAMES
from shared.models import ZoneConfig

def make_zone(threshold: float = 0.80) -> ZoneConfig:
    return ZoneConfig(
        zone_id="lot-a", name="Lot A",
        camera_rtsp_sub="rtsp://x:x@192.168.1.10:554/Streaming/Channels/101",
        capacity=10, threshold=threshold, rearm_threshold=0.70,
        vehicle_classes=["car", "truck"],
    )


def test_initial_state_is_correct():
    m = ZoneStateMachine(make_zone())
    # No state yet — but we can check via set_stream_healthy as a probe
    state = m.set_stream_healthy(True)  # returns current state immediately
    assert state.vehicle_count == 0
    assert state.occupancy_pct == 0.0
    assert state.status == "ok"
    assert state.alert_armed is True
    assert state.stream_healthy is True


def test_debounce_requires_n_matching_frames():
    m = ZoneStateMachine(make_zone())
    for i in range(DEBOUNCE_FRAMES - 1):
        assert m.update(3) is None  # not enough frames


def test_debounce_passes_on_n_identical_frames():
    m = ZoneStateMachine(make_zone())
    result = None
    for _ in range(DEBOUNCE_FRAMES):
        result = m.update(5)
    assert result is not None
    assert result.vehicle_count == 5


def test_debounce_resets_on_divergent_frame():
    m = ZoneStateMachine(make_zone())
    for _ in range(DEBOUNCE_FRAMES - 1):
        m.update(5)
    assert m.update(3) is None  # divergent frame resets


def test_status_warning_at_threshold():
    m = ZoneStateMachine(make_zone(threshold=0.80))
    # capacity=10, threshold=0.80 → 8 vehicles triggers warning
    for _ in range(DEBOUNCE_FRAMES):
        result = m.update(8)
    assert result.status == "warning"
    assert result.occupancy_pct == pytest.approx(0.8)


def test_status_full_at_100pct():
    m = ZoneStateMachine(make_zone())
    for _ in range(DEBOUNCE_FRAMES):
        result = m.update(10)  # capacity=10
    assert result.status == "full"


def test_status_degraded_overrides_warning():
    m = ZoneStateMachine(make_zone())
    for _ in range(DEBOUNCE_FRAMES):
        m.update(9)  # above threshold
    state = m.set_stream_healthy(False)
    assert state.status == "degraded"


def test_timestamp_is_utc():
    m = ZoneStateMachine(make_zone())
    state = m.set_stream_healthy(True)
    assert state.timestamp.endswith("Z"), "timestamp must end with Z (UTC)"
```

### Anti-Patterns — FORBIDDEN

- ❌ `datetime.now()` without `timezone.utc` — always use `datetime.now(timezone.utc)`
- ❌ `occupancy_pct = vehicle_count / capacity * 100` — keep as 0.0–1.0 ratio
- ❌ `status = "WARNING"` — always lowercase
- ❌ Rebuilding ZoneState from scratch in mqtt_handler — use `ZoneStateMachine` exclusively
- ❌ Publishing on every inference frame without debounce — only publish when debounce passes

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

_to be filled by dev agent_

### Completion Notes List

_to be filled by dev agent_

### File List

- `services/counter/src/counter/zone_state.py` (new)
- `services/counter/src/counter/mqtt_handler.py` (modified — integrate state machine)
- `services/counter/src/counter/main.py` (modified — instantiate ZoneStateMachines)
- `services/counter/tests/test_zone_state.py` (new)
