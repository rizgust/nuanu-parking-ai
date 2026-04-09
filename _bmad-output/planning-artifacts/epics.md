---
stepsCompleted: [1, 2, 3, 4]
status: 'complete'
completedAt: '2026-04-09'
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

---

## Epic 1: Parking Zones Are Monitored and Vehicle Counts Are Accurate

The system is deployed, zones are configured, and vehicle counts flow through the detection pipeline. The infra team can validate counting accuracy by inspecting MQTT output — before any UI or alerts are built. This foundational epic is the prerequisite for all other epics.

### Story 1.1: Project Scaffold and Docker Compose Foundation

As an infrastructure administrator,
I want the nuanu-parking-ai project initialized as a Python UV monorepo with a complete Docker Compose stack,
So that all services can be developed, tested, and deployed in a consistent environment from day one.

**Acceptance Criteria:**

**Given** the project root directory,
**When** `uv sync` is run,
**Then** the UV workspace resolves successfully with four workspace packages: shared, counter, watchdog, dashboard.

**Given** a valid `.env` file (copied from `.env.example`),
**When** `docker compose up -d` is run,
**Then** all 6 containers start: frigate, mosquitto, counter, watchdog, dashboard, nginx — each with `restart: unless-stopped` policy.

**Given** the Docker Compose configuration,
**When** inspected,
**Then** two Docker networks exist: `camera-net` (frigate only) and `app-net` (all application services), with no cross-contamination.

**Given** `.env.example` in the project root,
**When** read,
**Then** it contains placeholder entries for all required environment variables: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DASHBOARD_USERNAME, DASHBOARD_PASSWORD, SECRET_KEY, MQTT_HOST, MQTT_PORT, YOLO_CONFIDENCE_THRESHOLD, HEARTBEAT_TIMEOUT_SECS — each with a comment describing its purpose.

**Given** the project root,
**When** `.gitignore` is inspected,
**Then** the following are excluded from version control: `.env`, `*.db`, `*.pt`, `__pycache__/`, `models/`, `.venv/`.

**Given** the monorepo structure,
**When** inspected,
**Then** it matches the canonical layout: `services/{counter,watchdog,dashboard}/`, `shared/`, `config/`, `nginx/`, `pyproject.toml` (UV workspace root), `docker-compose.yml`, `.env.example`.

---

### Story 1.2: Zone Configuration Schema and Loading (FR-008, FR-009)

As an infrastructure administrator,
I want to define parking zones in a YAML config file and have the system load them at startup,
So that I can add, rename, or reconfigure zones by editing one file and restarting the service — no code changes required.

**Acceptance Criteria:**

**Given** `config/zones.yaml` contains one or more zone entries,
**When** each entry is inspected,
**Then** each entry includes all required fields: `zone_id` (lowercase-hyphenated string), `name` (display string), `camera_rtsp_sub` (RTSP URL string), `capacity` (int > 0), `threshold` (float 0.0–1.0), `rearm_threshold` (float 0.0–1.0, less than threshold), `vehicle_classes` (list, values from: car, truck, motorcycle, bus).

**Given** the `shared` package,
**When** `from shared.models import ZoneConfig` is executed,
**Then** a Pydantic model exists that validates all zone fields and raises a descriptive `ValidationError` for any invalid entry.

**Given** the counter service starts with a valid `zones.yaml`,
**When** startup completes,
**Then** the service logs the count and zone IDs of loaded zones at INFO level, e.g. `"Loaded 2 zones: ['lot-a', 'lot-b']"`.

**Given** the counter service starts with an invalid `zones.yaml` (e.g. missing `capacity` field),
**When** startup runs,
**Then** the service exits with a non-zero code and logs a clear error message identifying the invalid field and zone_id — it does not silently start with partial config.

**Given** `zones.yaml` is updated to add a new zone,
**When** `docker compose restart counter` is run,
**Then** the counter service reloads with the updated zone list within 60 seconds, without modifying any source code (FR-009).

---

### Story 1.3: Frigate NVR Setup and Zone Masking (FR-010)

As an infrastructure administrator,
I want Frigate NVR configured to monitor each parking zone's camera feed and detect motion only within the designated parking area,
So that motion events are scoped to actual parking zones and irrelevant areas (roads, footpaths, trees) are masked out to reduce false triggers.

**Acceptance Criteria:**

**Given** `config/frigate/config.yml` with at least one RTSP camera source,
**When** Frigate starts,
**Then** it connects to the configured camera sub-stream without errors and the Frigate web UI (port 5000) shows the camera feed as active.

**Given** a Frigate config with motion zones defined for a parking area,
**When** a vehicle enters the defined zone boundary,
**Then** Frigate publishes a motion event to the `frigate/events` MQTT topic on the Mosquitto broker.

**Given** a Frigate config with a motion mask applied to non-parking areas (e.g. road in frame foreground),
**When** movement occurs exclusively within the masked area,
**Then** no MQTT event is published for that motion — only parking-zone motion triggers events.

**Given** the Docker Compose network configuration,
**When** Frigate is running,
**Then** it is connected to both `camera-net` (for RTSP access) and `app-net` (for MQTT publishing), with no direct exposure to the host network beyond Frigate's own management port.

**Given** a Docker restart of the Frigate container,
**When** it comes back up,
**Then** zone mask definitions are preserved via the `frigate-data` volume mount — no reconfiguration required.

---

### Story 1.4: Counter Service — Vehicle Detection Pipeline (FR-011, FR-012)

As the system,
I want to run YOLOv8 vehicle detection when Frigate reports motion in a parking zone,
So that only confirmed vehicles (not shadows, animals, or pedestrians) increment the zone counter.

**Acceptance Criteria:**

**Given** a `frigate/events` MQTT message for a zone_id that exists in `zones.yaml`,
**When** the counter service receives it,
**Then** it captures the relevant camera frame for AI inference within 5 seconds of the event timestamp.

**Given** a captured frame passed to the inference module,
**When** YOLOv8 runs,
**Then** only detections with confidence ≥ `YOLO_CONFIDENCE_THRESHOLD` (default 0.65) are returned — lower-confidence detections are discarded.

**Given** YOLOv8 inference results for a zone whose `vehicle_classes` includes `"car"`,
**When** a car is detected above threshold,
**Then** it is counted; when a pedestrian or bicycle is detected — regardless of confidence — it is not counted.

**Given** YOLOv8 inference is running (CPU/GPU-bound work),
**When** called from the async service,
**Then** it executes inside `asyncio.to_thread()` so the service's async event loop is not blocked.

**Given** the counter Dockerfile,
**When** built,
**Then** YOLOv8n model weights (`yolov8n.pt`) are downloaded during the build step — the container does not require internet access at runtime to load the model.

**Given** a `frigate/events` message for a `zone_id` not present in `zones.yaml`,
**When** received by the counter,
**Then** the event is silently ignored with a DEBUG-level log entry — no error is raised.

---

### Story 1.5: Zone State Machine with Debounce and MQTT Publishing (FR-013)

As the system,
I want a per-zone state machine that tracks vehicle counts with debounce logic and publishes stable zone state to MQTT,
So that transient vehicle movements don't cause counter jitter and all consumers (dashboard, watchdog) always receive accurate, stable zone occupancy.

**Acceptance Criteria:**

**Given** a vehicle detection result for zone "lot-a",
**When** `ZoneStateMachine.update()` is called,
**Then** it recalculates `vehicle_count`, `occupancy_pct` (float 0.0–1.0), and `status` ("ok"/"warning"/"full") based on zone capacity and threshold.

**Given** rapid consecutive detection frames that disagree (e.g. vehicle appears then disappears in alternating frames),
**When** debounce logic is applied,
**Then** the counter only updates if N consecutive frames agree on the vehicle count (N configurable, default 3) — a single divergent frame does not change the count.

**Given** a zone state change after debounce,
**When** published to MQTT topic `parking/{zone_id}/state`,
**Then** the payload exactly matches the canonical schema: `{zone_id, vehicle_count, capacity, occupancy_pct, status, alert_armed, stream_healthy, timestamp}` — no extra or missing fields, no schema variants between services.

**Given** a zone state MQTT publish,
**When** sent to the broker,
**Then** `retain=True` is set — a new subscriber receives the current state immediately on connection without waiting for the next event.

**Given** the counter service starts fresh,
**When** it initializes `ZoneStateMachine` for zone "lot-a",
**Then** the initial state is: `vehicle_count=0`, `occupancy_pct=0.0`, `status="ok"`, `alert_armed=True`, `stream_healthy=True`.

**Given** zone occupancy crosses the threshold (e.g. occupancy_pct=0.82 with threshold=0.80),
**When** state is published,
**Then** `status="warning"` and `alert_armed=True` appear in the MQTT payload.

**And** all `timestamp` values in the payload use `datetime.now(timezone.utc)` — never `datetime.now()` (naive datetime is forbidden).

---

### Story 1.6: RTSP Stream Resilience and Graceful Degradation (FR-014, FR-015)

As an infrastructure administrator,
I want the system to automatically recover from dropped camera streams and flag degraded zones without affecting others,
So that transient network issues never require manual restarts and operators always know which zones they can trust.

**Acceptance Criteria:**

**Given** an RTSP stream drop (camera unreachable or network interruption),
**When** the counter detects the connection failure,
**Then** it automatically attempts reconnection using exponential backoff: 1s → 2s → 4s → 8s → … → max 60s between retries.

**Given** a stream has been lost for zone "lot-a",
**When** the counter publishes the next zone state to MQTT,
**Then** `stream_healthy=False` appears in the payload for "lot-a".

**Given** `stream_healthy=False` for zone "lot-a" and zone "lot-b" is operating normally,
**When** the system is running,
**Then** "lot-b" continues publishing accurate zone state to MQTT without interruption or error.

**Given** a previously dropped stream that successfully reconnects,
**When** the RTSP connection re-establishes,
**Then** `stream_healthy=True` is restored in subsequent MQTT publishes — no service restart required.

**Given** a stream reconnect is in progress (backoff timer active),
**When** Docker checks the counter container health,
**Then** the health check returns healthy — the container is NOT restarted during the reconnect backoff period.

---

## Epic 2: Security Team Receives Proactive Capacity Alerts

Security operators receive a Telegram alert when any zone hits its occupancy threshold, and another alert if the system fails. Re-arm logic prevents alert spam. The security team can act on parking issues without checking anything — the system tells them.

### Story 2.1: Telegram Threshold Alerts and Re-Arm Logic (FR-001, FR-002)

As a security operator,
I want to receive a Telegram alert when a parking zone reaches its capacity threshold — and stop receiving repeated alerts until the zone clears,
So that I can act proactively before a zone fills, without being spammed while it stays above threshold.

**Acceptance Criteria:**

**Given** zone "lot-a" with `threshold=0.80` and `alert_armed=True`,
**When** `occupancy_pct` first crosses 0.80,
**Then** a Telegram message is delivered to the configured chat ID within 60 seconds (NFR-001).

**Given** the Telegram threshold alert is sent,
**When** the message is received,
**Then** it includes: zone name, current occupancy percentage (e.g. "82%"), absolute count and capacity (e.g. "41/50"), and a UTC timestamp.

**Given** the threshold alert has fired (`alert_armed` set to False),
**When** occupancy remains above threshold in subsequent state updates,
**Then** no additional Telegram alerts are sent for that zone — duplicate suppression is active.

**Given** `alert_armed=False` for a zone,
**When** occupancy drops below `rearm_threshold` (default 0.70),
**Then** `alert_armed` is set back to True — the alert re-arms for the next threshold crossing.

**Given** the Telegram Bot API is temporarily unreachable,
**When** a send attempt fails,
**Then** the system retries once after 5 seconds; if the retry also fails, it logs an ERROR and continues — the alert pipeline is never blocked by a Telegram failure.

**Given** multiple zones cross their thresholds within seconds of each other,
**When** alerts are sent,
**Then** each zone sends its own distinct Telegram message — alerts are not silently merged or dropped.

---

### Story 2.2: Watchdog Service — System Failure Detection and Telegram Alerts (FR-003)

As a security operator,
I want to receive a Telegram alert within 2 minutes when a camera stream is lost, an inference process crashes, or a service container fails,
So that I know not to trust the data for affected zones and can contact the infra team without delay.

**Acceptance Criteria:**

**Given** the watchdog service is running and monitoring heartbeats,
**When** no heartbeat is received from the counter service for more than `HEARTBEAT_TIMEOUT_SECS` (default 90s),
**Then** a Telegram alert is sent within 2 minutes of the last valid heartbeat (NFR-002).

**Given** a watchdog Telegram alert for service failure,
**When** the message is received,
**Then** it includes: a `[SYSTEM]` prefix, failure type (e.g. "Heartbeat timeout", "Container unhealthy"), affected service name, and last-seen timestamp.

**Given** the watchdog monitors Docker container health via the Docker socket,
**When** any monitored container (counter, dashboard, frigate) enters an "unhealthy" state,
**Then** a Telegram alert is sent within 2 minutes identifying the container and failure state.

**Given** `stream_healthy=False` appears in a zone's MQTT state,
**When** the watchdog receives this event,
**Then** a Telegram alert is sent identifying the affected zone and that its camera stream has been lost.

**Given** a system failure alert has been sent for a specific condition (e.g. counter heartbeat timeout),
**When** that same condition persists across multiple watchdog poll cycles,
**Then** the alert does not re-fire on every cycle — it fires once per failure onset and re-arms when the condition clears.

**Given** the watchdog service itself is running,
**When** operating normally,
**Then** it publishes its own heartbeat to `parking/system/health` every 60 seconds — so the absence of watchdog heartbeats would itself indicate a failure.

---

## Epic 3: Operators Can Monitor All Zones on the Live Dashboard

A password-protected web dashboard shows real-time vehicle counts, occupancy percentages, zone status badges (OK / WARNING / FULL / DEGRADED), and a system health indicator. Zone tiles update in-place via SSE — no page reload. Operators have full situational awareness from any device on the network.

### Story 3.1: Dashboard Authentication (FR-007, UX-DR3)

As a security operator,
I want to log in to the parking dashboard with a username and password,
So that occupancy data is not accessible to anyone on the local network who opens a browser.

**Acceptance Criteria:**

**Given** an unauthenticated request to any dashboard route (e.g. `GET /`),
**When** received by the server,
**Then** the response is a 302 redirect to `/login` — no dashboard content is served to unauthenticated users.

**Given** the `/login` page loads,
**When** rendered,
**Then** a form with username and password fields is shown — no other fields, no "remember me" checkbox in MVP.

**Given** valid credentials matching `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD` env vars,
**When** the login form is submitted,
**Then** the user is redirected to `/` and a signed session cookie is set with an 8-hour expiry.

**Given** invalid credentials (wrong username or wrong password),
**When** the login form is submitted,
**Then** the user remains on `/login` and an error message is displayed — the message must not reveal which credential was wrong (e.g. "Invalid username or password").

**Given** a valid session cookie that has expired (> 8 hours old),
**When** the next request is made,
**Then** the user is redirected to `/login`.

**Given** an authenticated user,
**When** `GET /logout` is requested,
**Then** the session cookie is cleared and the user is redirected to `/login`.

**Given** the session cookie,
**When** inspected,
**Then** it is signed using `itsdangerous` `URLSafeTimedSerializer` with `SECRET_KEY` — the password is never stored in the cookie payload.

---

### Story 3.2: Live Zone Occupancy Dashboard with SSE (FR-004, FR-005, UX-DR1, UX-DR4, UX-DR5)

As a security operator,
I want to see all parking zones on a single page with live vehicle counts, occupancy percentages, and color-coded status badges that update automatically,
So that I always have an up-to-date picture of parking occupancy across all zones without refreshing the page.

**Acceptance Criteria:**

**Given** the dashboard loads (authenticated user),
**When** rendered,
**Then** each configured zone appears as a tile displaying: zone name, vehicle count (e.g. "23"), total capacity (e.g. "/50"), occupancy percentage (e.g. "46%"), and a status badge.

**Given** a zone with `status="ok"` (occupancy below threshold),
**When** its tile is displayed,
**Then** the status badge is styled green and shows "OK".

**Given** a zone with `status="warning"` (occupancy ≥ threshold, < 100%),
**When** its tile is displayed,
**Then** the status badge is styled amber/yellow and shows "WARNING".

**Given** a zone with `status="full"` (occupancy at 100%),
**When** its tile is displayed,
**Then** the status badge is styled red and shows "FULL".

**Given** the SSE endpoint `GET /stream` is connected,
**When** a zone state changes (new MQTT message received by the dashboard backend),
**Then** the corresponding zone tile updates in-place via HTMX OOB swap — no full page reload occurs.

**Given** the SSE connection drops (network interruption),
**When** HTMX SSE reconnects to `/stream`,
**Then** zone tiles are refreshed to current state (MQTT retained messages serve current state to new subscribers immediately).

**Given** the dashboard is viewed on a mobile phone screen (min 375px wide),
**When** rendered,
**Then** zone tiles are readable without horizontal scrolling — layout adapts to a single-column or 2-column grid at narrow widths (UX-DR5).

**Given** no zones are configured in `zones.yaml`,
**When** the dashboard loads,
**Then** an empty state message is shown (e.g. "No zones configured. Add zones to config/zones.yaml and restart.").

---

### Story 3.3: System Health Indicator and DEGRADED Zone Display (FR-006, FR-015 display, UX-DR2)

As a security operator,
I want to see a system health indicator on the dashboard and a DEGRADED badge on any zone with a lost camera stream,
So that I immediately know when I cannot trust a zone's data and can distinguish live data from stale data.

**Acceptance Criteria:**

**Given** all zones have `stream_healthy=True`,
**When** the dashboard is viewed,
**Then** a system health banner or indicator shows a healthy status (e.g. green "All Systems Operational").

**Given** zone "lot-a" has `stream_healthy=False` and the SSE update is received by the dashboard,
**When** the zone tile is rendered,
**Then** the status badge changes to "DEGRADED" styled in grey — overriding the occupancy-based status color.

**Given** a zone tile showing "DEGRADED",
**When** displayed,
**Then** the vehicle count and occupancy % values are visually indicated as potentially stale (e.g. greyed out text or a stale indicator icon).

**Given** zone "lot-a" is DEGRADED,
**When** the dashboard is viewed,
**Then** all other zones (e.g. "lot-b") continue to show their live occupancy data with normal status colors — DEGRADED state does not propagate.

**Given** zone "lot-a" recovers (stream_healthy returns to True) and the SSE update is received,
**When** the zone tile updates,
**Then** it reverts to its current occupancy-based status (OK/WARNING/FULL) without a page reload.

**Given** one or more zones are in DEGRADED state,
**When** the system health indicator is displayed,
**Then** it reflects the degraded state (e.g. amber "1 zone degraded") — operators can see at a glance that the system is not fully healthy.

---

### Story 3.4: Nginx Reverse Proxy and End-to-End Integration (FR-009, NFRs)

As an infrastructure administrator,
I want the dashboard accessible on the local network via standard HTTP through nginx, and all services to compose and restart cleanly after zone config changes,
So that operators can access the dashboard from any device on the network and configuration updates take effect without downtime.

**Acceptance Criteria:**

**Given** nginx is running and the full Docker Compose stack is up,
**When** a browser on the local network navigates to `http://<server-ip>/`,
**Then** the request is proxied to the dashboard service and the login page renders correctly — no nginx errors in logs.

**Given** all 6 Docker Compose services have started,
**When** `docker compose ps` is run,
**Then** all containers show status "Up" or "Up (healthy)" — no containers in "Exit" or "Restarting" state.

**Given** `zones.yaml` is modified to add a new zone,
**When** `docker compose restart counter dashboard` is run,
**Then** the new zone appears as a tile on the dashboard within 60 seconds — no source code modification required (FR-009).

**Given** nginx proxies the dashboard,
**When** an unauthenticated request is made via nginx,
**Then** the 302 redirect to `/login` is correctly forwarded to the client — nginx does not strip redirect headers or swallow Set-Cookie headers.

**Given** the complete stack is torn down and restarted (`docker compose down && docker compose up -d`),
**When** all containers are healthy,
**Then** the dashboard is accessible, zone tiles load with retained MQTT state, and no manual re-initialization is required — all within 60 seconds of the last container reaching healthy state.

---

## Epic 4: Operations Leadership Can Access Historical Reports (Post-MVP Stub)

Stub routes and storage infrastructure for post-MVP analytics delivery. Operations leadership will eventually view peak-hour trends and export weekly reports. This epic creates the data model and placeholder endpoints so no migration is needed when analytics are built.

### Story 4.1: Historical Data Schema and Stub Routes (FR-016, FR-017)

As an infrastructure administrator,
I want the SQLite schema and stub API routes for historical occupancy data to be in place from day one,
So that alert events are being recorded now and the reporting feature can be activated post-MVP without a database migration.

**Acceptance Criteria:**

**Given** `shared/db/schema.sql` is applied,
**When** the SQLite database initializes,
**Then** the following tables exist: `alert_events` (columns: id INTEGER PRIMARY KEY, zone_id TEXT, alert_type TEXT, occupancy_pct REAL, vehicle_count INTEGER, created_at TEXT) and `system_events` (columns: id INTEGER PRIMARY KEY, service TEXT, event_type TEXT, message TEXT, created_at TEXT).

**Given** a threshold alert fires (from Epic 2),
**When** the event is processed,
**Then** a row is written to `alert_events` with the correct `zone_id`, `alert_type`, `occupancy_pct`, `vehicle_count`, and `created_at` in ISO 8601 UTC format.

**Given** an authenticated user requests `GET /history`,
**When** the route is called,
**Then** a 200 response returns a page that displays "Historical reporting coming soon" — the route exists, is auth-protected, and returns a valid HTML response.

**Given** an authenticated user requests `GET /history/export`,
**When** the route is called,
**Then** a 501 Not Implemented response is returned with JSON body: `{"detail": "Report export not yet implemented"}`.

**Given** the SQLite database file at `/data/parking.db` on the `db-data` volume,
**When** the dashboard container is restarted,
**Then** existing `alert_events` rows are preserved — data persists across container restarts.
