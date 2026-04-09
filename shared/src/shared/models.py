"""Canonical Pydantic v2 models shared across all services.

IMPORTANT: These are the single source of truth for all data schemas.
Never redefine these models in individual services — always import from shared.
"""

from typing import Literal
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings


class ZoneConfig(BaseModel):
    """Configuration for a single parking zone, loaded from config/zones.yaml."""

    zone_id: str           # Lowercase-hyphenated, e.g. "lot-a". Used in MQTT topics, HTML IDs, DB.
    name: str              # Human-readable display name, e.g. "Lot A — Main Entrance"
    camera_rtsp_sub: str   # RTSP sub-stream URL for AI inference
    capacity: int          # Total vehicle capacity for this zone
    threshold: float       # Occupancy ratio to trigger alert, e.g. 0.80
    rearm_threshold: float # Occupancy ratio to re-arm alert after firing, e.g. 0.70
    vehicle_classes: list[str]  # Classes to count: any of ["car", "truck", "motorcycle", "bus"]

    @field_validator("zone_id")
    @classmethod
    def zone_id_must_be_lowercase_hyphenated(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-z0-9-]+$", v):
            raise ValueError(
                f"zone_id '{v}' must be lowercase alphanumeric with hyphens only "
                f"(e.g. 'lot-a', not 'Lot A' or 'lot_a')"
            )
        return v

    @field_validator("capacity")
    @classmethod
    def capacity_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError(f"capacity must be > 0, got {v}")
        return v

    @field_validator("threshold", "rearm_threshold")
    @classmethod
    def threshold_must_be_ratio(cls, v: float) -> float:
        if not 0.0 < v < 1.0:
            raise ValueError(f"threshold/rearm_threshold must be between 0 and 1, got {v}")
        return v

    @field_validator("vehicle_classes")
    @classmethod
    def vehicle_classes_must_be_valid(cls, v: list[str]) -> list[str]:
        valid = {"car", "truck", "motorcycle", "bus"}
        invalid = set(v) - valid
        if invalid:
            raise ValueError(f"Invalid vehicle classes: {invalid}. Must be subset of {valid}")
        if not v:
            raise ValueError("vehicle_classes cannot be empty")
        return v


class ZoneState(BaseModel):
    """Live state of a parking zone. Canonical MQTT payload schema.

    Published to: parking/{zone_id}/state (retained=True)
    This is the ONLY schema variant — no service-specific variations allowed.
    """

    zone_id: str
    vehicle_count: int
    capacity: int
    occupancy_pct: float           # 0.0–1.0 (NOT 0–100). E.g. 46% = 0.46
    status: Literal["ok", "warning", "full", "degraded"]  # Always lowercase
    alert_armed: bool
    stream_healthy: bool
    timestamp: str                 # ISO 8601 UTC with Z suffix, e.g. "2026-04-09T14:32:00Z"


class AlertEvent(BaseModel):
    """An alert event to be persisted in the alert_events SQLite table."""

    zone_id: str
    alert_type: str        # e.g. "threshold_breach", "stream_loss", "container_down"
    occupancy_pct: float
    vehicle_count: int
    created_at: str        # ISO 8601 UTC with Z suffix


class SystemHealthPayload(BaseModel):
    """Heartbeat payload published to parking/system/health (retained=False)."""

    service: str           # e.g. "counter", "watchdog"
    status: Literal["healthy", "degraded", "failed"]
    timestamp: str         # ISO 8601 UTC with Z suffix
