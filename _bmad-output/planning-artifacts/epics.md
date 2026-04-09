---
stepsCompleted: [1, 2]
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/architecture.md"
---

# nuanu-parking-ai - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for nuanu-parking-ai, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

FR-001: Operators can receive a Telegram alert when a zone's occupancy reaches its configured threshold.
FR-002: The system re-arms a zone's alert after occupancy drops below the re-arm threshold (default: 70%), enabling future alerts without manual reset.
FR-003: Operators can receive a Telegram alert when a camera stream is lost, an inference process crashes, or a service container fails.
FR-004: Operators can view the current vehicle count and occupancy percentage per zone on a web dashboard.
FR-005: Operators can see a zone status indicator (OK / WARNING / FULL) for each zone on the dashboard.
FR-006: Operators can see a system health indicator on the dashboard reflecting the current stream and service status per zone, including a DEGRADED badge when a zone has lost stream connectivity.
FR-007: Operators can access the dashboard only after authenticating with valid credentials.
FR-008: Infrastructure administrators can configure each zone with a camera reference, zone name, total capacity, and occupancy alert threshold using a configuration file.
FR-009: Infrastructure administrators can apply zone configuration changes by restarting the service stack without modifying application code.
FR-010: Infrastructure administrators can define which region of each camera frame constitutes the monitored parking zone, excluding roads, footpaths, and other non-parking areas.
FR-011: The system counts vehicles per zone using a two-stage process: motion detection gates AI inference, which confirms vehicle presence before incrementing the zone counter.
FR-012: The system counts only vehicles in the configured classes (car, truck, motorcycle, bus); pedestrians, bicycles, and animals are excluded.
FR-013: The system applies debounce logic to zone counters to prevent alert re-triggering from transient vehicle movement within a zone.
FR-014: The system automatically attempts to reconnect a dropped camera stream without operator intervention.
FR-015: A zone with a lost or degraded stream displays a DEGRADED status on the dashboard; all other zones continue operating independently.
FR-016 (Post-MVP): Operations leadership can view historical occupancy data and peak-hour trend charts per zone.
FR-017 (Post-MVP): Operations leadership can export a per-zone occupancy report covering a specified time period.

### NonFunctional Requirements

NFR-001 (Performance): Telegram occupancy alert delivered within 60 seconds of threshold crossing, under normal operating conditions.
NFR-002 (Performance): Telegram system-failure alert delivered within 2 minutes of stream loss, process crash, or container failure.
NFR-003 (Accuracy): Vehicle detection accuracy ≥ 90% on live Hikvision footage under Nuanu conditions (tropical lighting, IR night mode, mixed vehicle types including motorcycles).
NFR-004 (Accuracy): False alert rate < 5% of total alerts triggered.
NFR-005 (Accuracy): Vehicle detection confidence threshold configurable per zone (default ≥ 0.65); only detections meeting the configured threshold are counted as vehicles.
NFR-006 (Reliability): System achieves ≥ 7 consecutive days of uninterrupted operation during MVP validation period.
NFR-007 (Reliability): System self-recovers from transient stream drops and process crashes without manual operator intervention.
NFR-008 (Reliability): Failure of any single camera stream or zone shall not degrade the operation of other active zones.
NFR-009 (Security): Video stream data shall not leave the local network; all AI inference and data storage on-premises.
NFR-010 (Security): Dashboard access requires authentication; unauthenticated requests rejected.
NFR-011 (Security): Camera credentials not stored in version-controlled source files.
NFR-012 (Scalability): Architecture supports expansion to 30+ locations by replicating service stack per site, without architectural redesign.

### Additional Requirements

Architecture technical requirements that directly affect implementation:

- **Project scaffold**: Python monorepo with UV workspaces — `uv init nuanu-parking-ai` + `uv workspace add services/counter services/watchdog services/dashboard shared`. This is the first implementation story (no starter template to clone; scaffold from scratch).
- **Docker Compose skeleton**: 6 services (frigate, mosquitto, counter, watchdog, dashboard, nginx), 2 networks (camera-net, app-net), defined volumes (frigate-data, db-data, zones.yaml mount). Must be created before any service can be tested end-to-end.
- **Shared package first**: `shared/src/shared/` package (models.py, mqtt.py, config.py, db/schema.sql) must exist before any service code is written — all services depend on it.
- **MQTT canonical payload**: Zone state payload is the single schema across all services. Fields: zone_id (str), vehicle_count (int), capacity (int), occupancy_pct (float 0–1), status ("ok"/"warning"/"full"/"degraded"), alert_armed (bool), stream_healthy (bool), timestamp (ISO 8601 UTC). No variations permitted.
- **Zone ID convention**: lowercase-hyphenated strings (e.g. `lot-a`). Used identically in MQTT topics, SQLite rows, HTML element IDs, SSE event names. Source of truth: config/zones.yaml.
- **Async discipline**: All I/O is async (aiomqtt, aiosqlite, httpx). YOLOv8 inference runs in asyncio.to_thread(). Never call sync blocking functions in async def. One asyncio.run() entry point per service.
- **RTSP via FFmpeg**: Use FFmpeg subprocess over OpenCV for production reliability. Exponential backoff reconnect (1s → 2s → 4s → max 60s) on all stream connections.
- **YOLOv8 weights**: Downloaded at Docker build time via `RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"` in counter Dockerfile. Model file gitignored.
- **SQLite schema**: Created by shared/db/schema.sql on first run. Tables: alert_events (zone_id, type, occupancy_pct, timestamp), system_events (service, event_type, message, timestamp). Owned by dashboard service.
- **Session auth**: itsdangerous URLSafeTimedSerializer. Single credential from env vars (DASHBOARD_USERNAME, DASHBOARD_PASSWORD). 8-hour session expiry. All dashboard routes protected by require_auth FastAPI dependency.
- **MQTT retained messages**: Zone state topics use retained=True; system health heartbeat uses retained=False.
- **Nginx reverse proxy**: Included from day 1. Exposes dashboard on host port 80; all other services internal only.
- **Structured JSON logging**: All services log JSON to stdout. No print() statements. Captured by Docker.
- **Graceful shutdown**: All services handle SIGTERM via asyncio signal handlers.
- **Environment variables**: All in .env (gitignored). .env.example committed with placeholder values. Key vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DASHBOARD_USERNAME, DASHBOARD_PASSWORD, SECRET_KEY, MQTT_HOST, YOLO_CONFIDENCE_THRESHOLD, HEARTBEAT_TIMEOUT_SECS (default 90).
- **HEARTBEAT_TIMEOUT_SECS = 90**: Counter publishes heartbeat every 60s. Watchdog alerts at 90s gap (1.5× interval), ensuring alert fires within NFR-002's 2-minute window worst-case.
- **Docker health checks**: Defined on counter, dashboard, frigate services.
- **Greenfield project**: No existing codebase to integrate with. First story must set up the full project scaffold.

### UX Design Requirements

No UX Design document exists. Dashboard UI requirements are derived from PRD user journeys and FR-004–007.

Implied UI requirements for dashboard stories:
- UX-DR1: Dashboard displays zone tiles in a grid layout; each tile shows zone name, vehicle count (e.g. "23/50"), occupancy percentage, and a color-coded status badge (OK=green / WARNING=amber / FULL=red / DEGRADED=grey).
- UX-DR2: System health indicator (banner or sidebar) shows per-zone stream status; DEGRADED badge appears on affected zone tile when stream is lost.
- UX-DR3: Login page presents a simple username/password form; failed login shows an error message without revealing which credential was wrong.
- UX-DR4: Dashboard updates zone tile contents in-place (no full page reload) when zone state changes via SSE.
- UX-DR5: Dashboard is usable on a tablet/phone screen (security team uses phones) — responsive layout or minimum mobile-readable tile size.

### FR Coverage Map

FR-008: Epic 1 — Zone YAML config (camera ref, zone name, capacity, threshold)
FR-009: Epic 1 — Config reload via service restart (no code change required)
FR-010: Epic 1 — Frigate zone masking (per-camera region definition)
FR-011: Epic 1 — Two-stage detection (motion gate → YOLOv8 confirmation)
FR-012: Epic 1 — Vehicle class filter (car, truck, motorcycle, bus only)
FR-013: Epic 1 — Debounce logic (prevent counter jitter)
FR-014: Epic 1 — Auto-reconnect on stream drop (exponential backoff)
FR-015: Epic 1 (stream_healthy field published via MQTT) + Epic 3 (DEGRADED badge display on dashboard)
FR-001: Epic 2 — Threshold Telegram alert delivery
FR-002: Epic 2 — Alert re-arm logic (re-arms at 70% after threshold crossed)
FR-003: Epic 2 — System failure Telegram alert (stream loss, process crash, container down)
FR-004: Epic 3 — Live vehicle count and occupancy % per zone on dashboard
FR-005: Epic 3 — Zone status badge (OK / WARNING / FULL / DEGRADED)
FR-006: Epic 3 — System health indicator + DEGRADED badge on zone tile
FR-007: Epic 3 — Dashboard authentication (login required)
FR-016: Epic 4 — Post-MVP stub (history view endpoint + data model)
FR-017: Epic 4 — Post-MVP stub (report export endpoint)

## Epic List

### Epic 1: Parking Zones Are Monitored and Vehicle Counts Are Accurate
The system is deployed, zones are configured, and vehicle counts flow through the detection pipeline. The infra team can validate counting accuracy by inspecting MQTT output — before any UI or alerts are built. This is the foundational layer everything else builds on.
**FRs covered:** FR-008, FR-009, FR-010, FR-011, FR-012, FR-013, FR-014, FR-015

### Epic 2: Security Team Receives Proactive Capacity Alerts
Security operators receive a Telegram alert when any zone hits its occupancy threshold, and another alert if the system fails (stream loss, process crash, container down). Re-arm logic prevents alert spam. The security team can act on parking issues without checking anything — the system tells them.
**FRs covered:** FR-001, FR-002, FR-003

### Epic 3: Operators Can Monitor All Zones on the Live Dashboard
A password-protected web dashboard shows real-time vehicle counts, occupancy percentages, zone status badges (OK / WARNING / FULL / DEGRADED), and a system health indicator. Zone tiles update in-place via SSE — no page reload needed. Operators have full situational awareness from any device on the network.
**FRs covered:** FR-004, FR-005, FR-006, FR-007, FR-015 (DEGRADED badge display)

### Epic 4: Operations Leadership Can Access Historical Reports (Post-MVP Stub)
Stub routes and storage infrastructure for post-MVP delivery. Operations leadership will eventually view peak-hour trends and export weekly reports. MVP delivers the data model and placeholder endpoints — no functional UI yet.
**FRs covered:** FR-016 (stub), FR-017 (stub)
