# Story 1.2: Zone Configuration Schema and Loading

Status: ready-for-dev

## Story

As an infrastructure administrator,
I want to define parking zones in a YAML config file and have the system load them at startup,
So that I can add, rename, or reconfigure zones by editing one file and restarting the service — no code changes required.

## Acceptance Criteria

1. **Given** `config/zones.yaml` contains one or more zone entries, **When** each entry is inspected, **Then** each entry includes all required fields: `zone_id` (lowercase-hyphenated string), `name` (display string), `camera_rtsp_sub` (RTSP URL string), `capacity` (int > 0), `threshold` (float 0.0–1.0), `rearm_threshold` (float 0.0–1.0), `vehicle_classes` (list from: car, truck, motorcycle, bus).

2. **Given** the `shared` package, **When** `from shared.models import ZoneConfig` is executed, **Then** a Pydantic v2 model exists that validates all zone fields and raises a descriptive `ValidationError` for any invalid entry. *(Already implemented in Story 1.1 — do not recreate.)*

3. **Given** the counter service starts with a valid `zones.yaml`, **When** startup completes, **Then** the service logs the count and zone IDs of loaded zones at INFO level, e.g. `Loaded 2 zones: ['lot-a', 'lot-b']`.

4. **Given** the counter service starts with an invalid `zones.yaml` (e.g. missing `capacity` field, or `zone_id` has uppercase chars), **When** startup runs, **Then** the service exits with a non-zero code and logs a clear error message identifying the invalid field and zone entry — it does NOT silently start with partial config.

5. **Given** `zones.yaml` is updated to add a new zone, **When** `docker compose restart counter` is run, **Then** the counter service reloads with the updated zone list, without modifying any source code (FR-009).

## Tasks / Subtasks

- [ ] Task 1: Create CounterSettings in counter service (AC: 3, 4, 5)
  - [ ] Create `services/counter/src/counter/config.py`
  - [ ] Define `CounterSettings(BaseServiceSettings)` that adds `zones_config_path: Path = Path("/config/zones.yaml")` and `yolo_confidence_threshold: float = 0.65`
  - [ ] Inherit from `shared.config.BaseServiceSettings` — do NOT duplicate MQTT/LOG_LEVEL fields
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 2: Create zone YAML loader (AC: 3, 4, 5)
  - [ ] Create `services/counter/src/counter/zone_loader.py`
  - [ ] Implement `load_zones(path: Path) -> list[ZoneConfig]` function
  - [ ] Read YAML with `yaml.safe_load` — never `yaml.load` (security requirement)
  - [ ] Wrap Pydantic ValidationError: log descriptive message at ERROR level, re-raise as `SystemExit(1)`
  - [ ] Handle `FileNotFoundError`: log clear error message, exit with `SystemExit(1)`
  - [ ] Handle empty zones list: log error, exit with `SystemExit(1)` — at least one zone required
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 3: Wire zone loading into counter main.py (AC: 3, 4)
  - [ ] Update `services/counter/src/counter/main.py`
  - [ ] Instantiate `CounterSettings()` at startup
  - [ ] Call `load_zones(settings.zones_config_path)` — any exception or SystemExit propagates (no silencing)
  - [ ] Log `f"Loaded {len(zones)} zones: {[z.zone_id for z in zones]}"` at INFO level
  - [ ] Keep the `await asyncio.sleep(float('inf'))` placeholder — full pipeline implemented in Stories 1.4–1.6
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 4: Write pytest tests (AC: 1, 2, 3, 4)
  - [ ] Create `services/counter/tests/test_zone_config.py`
  - [ ] Test: valid single zone YAML → returns `list[ZoneConfig]` with correct field values
  - [ ] Test: valid multi-zone YAML → all zones loaded in order
  - [ ] Test: missing required field (e.g. no `capacity`) → raises `SystemExit`
  - [ ] Test: invalid `zone_id` (uppercase, e.g. `"Lot-A"`) → raises `SystemExit`
  - [ ] Test: invalid `vehicle_classes` (e.g. `["bicycle"]`) → raises `SystemExit`
  - [ ] Test: `threshold` ≥ 1.0 → raises `SystemExit`
  - [ ] Test: file not found → raises `SystemExit`
  - [ ] Test: empty `zones` list in YAML → raises `SystemExit`
  - [ ] Use `tmp_path` pytest fixture for all temp YAML files — never hardcode paths
  - [ ] Validate syntax with `python3 -m py_compile`

- [ ] Task 5: Verify integration (AC: 3, 4, 5)
  - [ ] Confirm `zones.yaml` already has sample `lot-a` zone — no changes required (created in Story 1.1)
  - [ ] Run all tests: `python3 -m pytest services/counter/tests/test_zone_config.py -v` (or note if uv unavailable)
  - [ ] Confirm all 4 new/modified Python files pass `python3 -m py_compile`

## Dev Notes

### What Story 1.1 Already Created — DO NOT RECREATE

The following were fully implemented in Story 1.1 and must be imported, never redefined:

**`shared/src/shared/models.py` — `ZoneConfig` (complete, production-ready):**
```python
class ZoneConfig(BaseModel):
    zone_id: str           # validated: ^[a-z0-9-]+$
    name: str
    camera_rtsp_sub: str
    capacity: int          # validated: > 0
    threshold: float       # validated: 0.0 < v < 1.0
    rearm_threshold: float # validated: 0.0 < v < 1.0
    vehicle_classes: list[str]  # validated: subset of {"car","truck","motorcycle","bus"}, non-empty

    @field_validator("zone_id") ...
    @field_validator("capacity") ...
    @field_validator("threshold", "rearm_threshold") ...
    @field_validator("vehicle_classes") ...
```

**`shared/src/shared/config.py` — `BaseServiceSettings`:**
```python
class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    mqtt_host: str = "mosquitto"
    mqtt_port: int = 1883
    log_level: str = "INFO"
```

**`config/zones.yaml` — sample zone (already correct schema):**
```yaml
zones:
  - zone_id: "lot-a"
    name: "Lot A — Main Entrance"
    camera_rtsp_sub: "rtsp://admin:password@192.168.1.10:554/Streaming/Channels/101"
    capacity: 50
    threshold: 0.80
    rearm_threshold: 0.70
    vehicle_classes: ["car", "truck", "motorcycle", "bus"]
```

### New Files to Create

#### `services/counter/src/counter/config.py`
```python
"""Counter service settings.

Extends BaseServiceSettings with counter-specific configuration.
All values loaded from environment variables / .env file.
"""
from pathlib import Path
from shared.config import BaseServiceSettings
from pydantic_settings import SettingsConfigDict


class CounterSettings(BaseServiceSettings):
    """Settings for the counter service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    zones_config_path: Path = Path("/config/zones.yaml")
    yolo_confidence_threshold: float = 0.65
```

#### `services/counter/src/counter/zone_loader.py`
```python
"""Zone configuration loader for the counter service.

Reads config/zones.yaml, validates each zone entry via ZoneConfig Pydantic model,
and returns a list of validated ZoneConfig objects. Exits with code 1 on any error.
"""
import logging
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError
from shared.models import ZoneConfig

logger = logging.getLogger(__name__)


def load_zones(path: Path) -> list[ZoneConfig]:
    """Load and validate zone configuration from a YAML file.

    Args:
        path: Path to zones.yaml

    Returns:
        List of validated ZoneConfig objects (at least one).

    Raises:
        SystemExit(1): On file not found, YAML parse error, validation error, or empty zones list.
    """
    if not path.exists():
        logger.error("zones.yaml not found at %s — cannot start without zone configuration", path)
        sys.exit(1)

    try:
        with path.open() as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        logger.error("Failed to parse zones.yaml: %s", exc)
        sys.exit(1)

    raw_zones = (raw or {}).get("zones", [])

    if not raw_zones:
        logger.error("zones.yaml contains no zones — at least one zone must be configured")
        sys.exit(1)

    zones: list[ZoneConfig] = []
    for i, entry in enumerate(raw_zones):
        try:
            zones.append(ZoneConfig(**entry))
        except ValidationError as exc:
            zone_id = entry.get("zone_id", f"<entry #{i}>")
            logger.error(
                "Invalid zone configuration for zone_id=%r:\n%s",
                zone_id,
                exc,
            )
            sys.exit(1)

    return zones
```

#### Updated `services/counter/src/counter/main.py`
```python
"""Counter service entry point.

Startup sequence for this story:
1. Load CounterSettings from environment
2. Load and validate zones from zones.yaml (exits on error)
3. Log loaded zone IDs at INFO

Full pipeline (YOLOv8, MQTT, state machine) implemented in Stories 1.4–1.6.
"""

import asyncio
import logging
from counter.config import CounterSettings
from counter.zone_loader import load_zones

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='{"level": "%(levelname)s", "service": "counter", "message": "%(message)s"}',
    )

    settings = CounterSettings()
    zones = load_zones(settings.zones_config_path)
    logger.info("Loaded %d zones: %s", len(zones), [z.zone_id for z in zones])

    # TODO Stories 1.4–1.6: MQTT subscription, YOLOv8 pipeline, state machine
    await asyncio.sleep(float("inf"))


if __name__ == "__main__":
    asyncio.run(main())
```

#### `services/counter/tests/test_zone_config.py`
```python
"""Tests for zone configuration loading.

Uses tmp_path fixture to write temporary YAML files.
Tests cover valid loading and all failure modes.
"""
import sys
from pathlib import Path

import pytest
import yaml

from counter.zone_loader import load_zones


def write_zones_yaml(tmp_path: Path, zones: list[dict]) -> Path:
    """Helper: write a zones.yaml with given zone list and return its path."""
    p = tmp_path / "zones.yaml"
    p.write_text(yaml.dump({"zones": zones}))
    return p


VALID_ZONE = {
    "zone_id": "lot-a",
    "name": "Lot A",
    "camera_rtsp_sub": "rtsp://user:pass@192.168.1.10:554/Streaming/Channels/101",
    "capacity": 50,
    "threshold": 0.80,
    "rearm_threshold": 0.70,
    "vehicle_classes": ["car", "truck"],
}


def test_valid_single_zone(tmp_path):
    path = write_zones_yaml(tmp_path, [VALID_ZONE])
    zones = load_zones(path)
    assert len(zones) == 1
    assert zones[0].zone_id == "lot-a"
    assert zones[0].capacity == 50
    assert zones[0].threshold == 0.80
    assert zones[0].vehicle_classes == ["car", "truck"]


def test_valid_multi_zone(tmp_path):
    zone_b = {**VALID_ZONE, "zone_id": "lot-b", "name": "Lot B"}
    path = write_zones_yaml(tmp_path, [VALID_ZONE, zone_b])
    zones = load_zones(path)
    assert len(zones) == 2
    assert [z.zone_id for z in zones] == ["lot-a", "lot-b"]


def test_missing_required_field_exits(tmp_path):
    bad = {k: v for k, v in VALID_ZONE.items() if k != "capacity"}
    path = write_zones_yaml(tmp_path, [bad])
    with pytest.raises(SystemExit) as exc_info:
        load_zones(path)
    assert exc_info.value.code == 1


def test_invalid_zone_id_uppercase_exits(tmp_path):
    bad = {**VALID_ZONE, "zone_id": "Lot-A"}
    path = write_zones_yaml(tmp_path, [bad])
    with pytest.raises(SystemExit) as exc_info:
        load_zones(path)
    assert exc_info.value.code == 1


def test_invalid_vehicle_class_exits(tmp_path):
    bad = {**VALID_ZONE, "vehicle_classes": ["bicycle"]}
    path = write_zones_yaml(tmp_path, [bad])
    with pytest.raises(SystemExit) as exc_info:
        load_zones(path)
    assert exc_info.value.code == 1


def test_threshold_out_of_range_exits(tmp_path):
    bad = {**VALID_ZONE, "threshold": 1.5}
    path = write_zones_yaml(tmp_path, [bad])
    with pytest.raises(SystemExit) as exc_info:
        load_zones(path)
    assert exc_info.value.code == 1


def test_file_not_found_exits():
    with pytest.raises(SystemExit) as exc_info:
        load_zones(Path("/nonexistent/zones.yaml"))
    assert exc_info.value.code == 1


def test_empty_zones_list_exits(tmp_path):
    p = tmp_path / "zones.yaml"
    p.write_text(yaml.dump({"zones": []}))
    with pytest.raises(SystemExit) as exc_info:
        load_zones(p)
    assert exc_info.value.code == 1
```

### Architecture Compliance

- **Import from shared, never redefine:** `from shared.models import ZoneConfig` — ZoneConfig lives exclusively in `shared/src/shared/models.py`
- **Pydantic v2:** `ValidationError` from `pydantic` (not `pydantic.v1`) — already confirmed in Story 1.1
- **yaml.safe_load:** Never `yaml.load(f)` — `safe_load` prevents arbitrary Python object deserialization
- **sys.exit(1):** Counter must exit non-zero on config error. DO NOT use `raise RuntimeError` and catch it elsewhere. `SystemExit(1)` propagates through asyncio cleanly.
- **Logging format:** JSON-structured (matching Story 1.1 pattern): `'{"level": "%(levelname)s", "service": "counter", "message": "%(message)s"}'`
- **No print():** All output via `logger.*` — Docker captures stdout; print bypasses structured logging
- **Path type for ZONES_CONFIG_PATH:** Pydantic-settings auto-coerces string env var `ZONES_CONFIG_PATH=/config/zones.yaml` into a `Path` object

### CounterSettings Env Var Mapping

| Env Var | Field | Default |
|---------|-------|---------|
| `MQTT_HOST` | `mqtt_host` | `"mosquitto"` (inherited) |
| `MQTT_PORT` | `mqtt_port` | `1883` (inherited) |
| `LOG_LEVEL` | `log_level` | `"INFO"` (inherited) |
| `ZONES_CONFIG_PATH` | `zones_config_path` | `Path("/config/zones.yaml")` |
| `YOLO_CONFIDENCE_THRESHOLD` | `yolo_confidence_threshold` | `0.65` |

Operator overrides via `.env`: set `ZONES_CONFIG_PATH=/custom/path.yaml` to use a different location.

### YAML Loading — Implementation Notes

- `yaml.safe_load` returns `None` for empty files; guard with `(raw or {}).get("zones", [])`
- `enumerate(raw_zones)` allows fallback zone ID in error message when `zone_id` is missing
- Log the full Pydantic `ValidationError` object — it formats as human-readable multi-line text automatically
- Do NOT catch `Exception` broadly — only `ValidationError` and `yaml.YAMLError`; let other unexpected errors propagate as crashes

### Testing — Key Patterns

- `tmp_path` is a built-in pytest fixture providing a temporary directory unique per test — use it for all file writes
- `yaml.dump({"zones": [...]})` is the canonical way to write test YAML — avoids YAML syntax errors in test code
- `pytest.raises(SystemExit)` catches `sys.exit(1)` calls — check `.value.code == 1` to confirm non-zero exit
- Do NOT use `monkeypatch` to mock the file system — write real files via `tmp_path` for fidelity to production behavior

### Validation Approach (UV Not in Shell)

UV is not installed in the execution shell (discovered in Story 1.1). Use these alternatives:
1. Syntax check: `python3 -m py_compile <file>` — confirms no syntax errors
2. Tests: `python3 -m pytest services/counter/tests/test_zone_config.py -v` — requires PYTHONPATH set if not using uv
3. If pytest unavailable: document in Dev Agent Record; user runs `uv run pytest` manually

To run tests without UV installed:
```bash
PYTHONPATH=shared/src:services/counter/src python3 -m pytest services/counter/tests/test_zone_config.py -v
```

### Files Changed in Story 1.1 (Do Not Regress)

Story 1.1 created these files in the counter package — preserve their content:
- `services/counter/pyproject.toml` — `pyyaml>=6.0` already declared; no changes needed
- `services/counter/Dockerfile` — no changes needed
- `services/counter/src/counter/__init__.py` — no changes needed
- `services/counter/src/counter/main.py` — **REPLACE** with Story 1.2 version (adds zone loading)
- `services/counter/tests/.gitkeep` — keep; tests go alongside it as `test_zone_config.py`

### Dependency Notes

- `pyyaml>=6.0`: already in `services/counter/pyproject.toml` (Story 1.1) — no pyproject.toml changes needed
- `pydantic>=2.0`: in `shared/pyproject.toml` — counter inherits via workspace dependency
- `pydantic-settings>=2.0`: already in `services/counter/pyproject.toml`

### Story 1.1 Learnings Applied

1. **UV not in shell** — validate with `python3 -m py_compile` and run tests with explicit `PYTHONPATH` if needed
2. **Pydantic v2 syntax** — `model_config = SettingsConfigDict(...)` not `class Config`, `@field_validator` not `@validator`
3. **No internet access assumed** — all libraries already declared in pyproject.toml; no pip install during story
4. **JSON structured logging** — established in Story 1.1; all new log calls use `logger.*` not `print()`

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

_to be filled by dev agent_

### Completion Notes List

_to be filled by dev agent_

### File List

- `services/counter/src/counter/config.py` (new)
- `services/counter/src/counter/zone_loader.py` (new)
- `services/counter/src/counter/main.py` (modified — replaces stub)
- `services/counter/tests/test_zone_config.py` (new)
