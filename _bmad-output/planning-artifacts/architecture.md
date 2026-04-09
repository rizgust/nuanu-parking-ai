---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8]
status: 'complete'
completedAt: '2026-04-09'
inputDocuments:
  - "_bmad-output/planning-artifacts/prd.md"
  - "_bmad-output/planning-artifacts/product-brief-nuanu-parking-ai-distillate.md"
workflowType: 'architecture'
project_name: 'nuanu-parking-ai'
user_name: 'boss'
date: '2026-04-09'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Functional Requirements (17):**
The FRs define five runtime subsystems: alerting pipeline (FR-001–003), operator dashboard (FR-004–007), zone configuration (FR-008–010), vehicle detection engine (FR-011–013), and fault recovery (FR-014–015). Two post-MVP FRs (FR-016–017) add historical data and reporting, requiring a storage layer that is absent from MVP scope.

**Non-Functional Requirements (12):**
- Performance: alert latency ≤ 60s (NFR-001), watchdog alert ≤ 2 min (NFR-002)
- Accuracy: detection ≥ 90% on live Hikvision footage (NFR-003), false alert rate < 5% (NFR-004), configurable confidence threshold (NFR-005)
- Reliability: 7-day uninterrupted MVP operation (NFR-006), self-recovery without operator intervention (NFR-007), zone-isolated failure (NFR-008)
- Security: on-premises video only (NFR-009), authenticated dashboard (NFR-010), credentials out of version control (NFR-011)
- Scalability: 30+ locations via service stack replication (NFR-012)

**Scale & Complexity:**
- Primary domain: IoT/Edge AI + internal web application
- Complexity level: Medium-High
- Estimated architectural components: 6–8 containerized services
- MVP scope: 2–4 cameras, single location, Docker Compose

### Technical Constraints & Dependencies

- **Hardware**: Local GPU server (mid-range GPU, RTX 3060+ class assumed); 32 Hikvision cameras with RTSP streams (fixed-angle, static zones)
- **RTSP**: FFmpeg required over OpenCV for production reliability; known quirks: 3–5s buffering latency, connection drops after 5–10 min idle, frame corruption at high bitrates → use sub-stream for inference
- **Inference stack**: Frigate NVR (motion detection) → MQTT pub/sub (embedded Mosquitto) → Python counter service → YOLOv8 (Ultralytics)
- **Language**: Python primary; Docker Compose deployment
- **External dependency**: Telegram Bot API (HTTPS outbound only)
- **No cloud**: all inference, storage, and alerting on-premises (hard constraint)

### Cross-Cutting Concerns Identified

- RTSP connection lifecycle: exponential backoff reconnect per stream
- GPU resource management: motion-gating preserves inference budget at scale
- Graceful degradation: zone-level failure isolation (NFR-008)
- Observability: watchdog requires health signals from all services
- Configuration management: YAML zone config → service reload without code changes (FR-009)
- Dashboard real-time updates: live push (WebSocket or SSE) required for occupancy and health indicators

## Starter Template Evaluation

### Primary Technology Domain

IoT/Edge AI + Internal Web Application (Python-centric, on-premises, Docker Compose deployment). No single CLI starter covers this stack — project is custom-scaffolded following established patterns.

### Stack Decisions

**Project Structure: Python Monorepo with UV**

Rationale: All Python services (inference/counter, watchdog, dashboard backend) are small, tightly coupled via MQTT and shared config models, and deploy together on a single server. Monorepo simplifies shared dependencies, unified Docker Compose, and config management.

Pattern: `matanby/python-monorepo-template` structure with UV workspace.

```
nuanu-parking-ai/
├── services/
│   ├── counter/          # Inference + zone state machine
│   ├── watchdog/         # Health monitoring + alerts
│   └── dashboard/        # FastAPI + HTMX backend
├── shared/               # Config models, MQTT helpers, zone schema
├── config/
│   └── zones.yaml        # Zone definitions (FR-008)
├── docker-compose.yml
└── .env.example
```

**Dashboard: FastAPI + HTMX + Server-Sent Events**

Rationale: Internal ops tool with simple UI requirements (live counts, zone status badges, system health). HTMX with SSE delivers real-time push (FR-004, FR-006) without a client-side build step or state management complexity. Simpler to maintain on a local server with non-technical operators.

Reference: `maces/fastapi-htmx` + Jinja2 templates

**Python Runtime: 3.12+ with UV package manager**

UV (2025 standard) replaces Poetry for faster dependency resolution and lockfile management across monorepo workspaces.

**Initialization:**

```bash
uv init nuanu-parking-ai
uv workspace add services/counter services/watchdog services/dashboard shared
```

**Note:** Project scaffolding and Docker Compose skeleton should be the first implementation story.

### Architectural Decisions Established by Stack Choice

- **Language**: Python 3.12+ throughout all services
- **API framework**: FastAPI (dashboard backend)
- **Frontend**: HTMX + Jinja2 templates (no build step)
- **Real-time push**: Server-Sent Events via FastAPI StreamingResponse
- **Package management**: UV workspaces
- **Containerization**: Docker Compose (one compose file, all services)
- **Code organization**: Monorepo, services share `shared/` package
- **Config**: Pydantic Settings for env vars, YAML for zone definitions

## Core Architectural Decisions

### Decision Priority Analysis

**Critical Decisions (Block Implementation):**
- Counter state storage: in-memory Python dict per zone
- Alert log storage: SQLite (local file, zero-config)
- Dashboard auth: session cookies + single env-var password
- Counter→Dashboard update path: MQTT → SSE (event-driven end-to-end)
- Docker Compose service topology: 6 services across 2 networks

**Important Decisions (Shape Architecture):**
- GPU assignment: NVIDIA device reservation on `counter` service only
- Restart policy: `unless-stopped` on all services
- Nginx as reverse proxy: included from day 1

**Deferred Decisions (Post-MVP):**
- PostgreSQL migration for multi-location historical data (post-MVP FR-016/017)
- Multi-user dashboard auth (add FastAPI-Users when team grows)
- Central aggregation layer for 30+ locations (NFR-012 architecture, not MVP scope)

### Data Architecture

**Counter State: In-Memory Python Dict**
- Zone occupancy state held in a per-zone Python dataclass/dict within the `counter` service process
- Fields per zone: `vehicle_count`, `capacity`, `occupancy_pct`, `status` (OK/WARNING/FULL), `alert_armed`, `last_updated`, `stream_healthy`
- State rebuilds automatically within seconds of service restart as MQTT events resume
- Rationale: zero latency on the hot path; no DB dependency during inference loop

**Alert & Event Log: SQLite**
- File: `/data/parking.db` (Docker volume mount)
- Tables: `alert_events` (zone, type, occupancy_pct, timestamp), `system_events` (stream_loss, recovery, etc.)
- Accessed by dashboard backend for recent alert history display
- Migration path: swap for PostgreSQL when expanding to multiple locations post-MVP
- Library: `aiosqlite` (async, compatible with FastAPI)

**Session Storage: Signed Cookies (itsdangerous)**
- Single credential: `DASHBOARD_USERNAME` + `DASHBOARD_PASSWORD` in `.env`
- Server signs session cookie with `SECRET_KEY` env var; no session DB required
- Session expiry: 8 hours (operator shift length)
- Logout invalidates cookie client-side

### Authentication & Security

**Dashboard Authentication**
- Method: Session cookie (itsdangerous `URLSafeTimedSerializer`)
- Single admin credential from environment variables
- Login form → POST → validate → set signed cookie → redirect to dashboard
- All dashboard routes protected by FastAPI dependency `require_auth`
- NFR-010 satisfied: unauthenticated requests receive 302 redirect to login

**Credential Management (NFR-011)**
- Camera RTSP credentials: `.env` file, injected as Docker environment variables
- `.env` excluded from version control via `.gitignore`; `.env.example` committed
- `SECRET_KEY` for cookie signing: generated once, stored in `.env`
- No credentials in `zones.yaml` (zone config references camera IDs, not URLs)

**Network Security (NFR-009)**
- `camera-net`: Frigate + camera RTSP streams only; isolated from app services
- `app-net`: all application services; no external exposure
- Dashboard exposed only on host `127.0.0.1:8080` (or local network via nginx)
- Only outbound external connection: Telegram Bot API (HTTPS port 443)

### API & Communication Patterns

**Primary Event Bus: MQTT (Mosquitto)**
- Broker: `eclipse-mosquitto` embedded in Docker Compose, `app-net` only
- Topic schema:
  - `frigate/events` → Frigate publishes motion detection events
  - `parking/{zone_id}/state` → `counter` publishes zone state on every change
  - `parking/system/health` → `watchdog` publishes heartbeat every 60s
  - `parking/system/alert` → `watchdog` publishes failure events
- QoS Level 1 (at-least-once) for state and alert topics; QoS 0 for heartbeat
- `counter` and `watchdog` use `aiomqtt` (async Python MQTT client)

**Counter → Dashboard Update Path: MQTT → SSE**
- `counter` publishes zone state to `parking/{zone_id}/state` on every counter change
- `dashboard` backend maintains persistent async MQTT subscription to `parking/+/state`
- On message receipt, dashboard pushes SSE event to all connected browser clients
- Browser: HTMX `hx-sse` extension listens and swaps zone tiles in-place
- Latency: sub-second from zone state change to browser update
- Fallback: HTMX polling every 10s as SSE reconnect safety net

**Dashboard API (Internal)**
- FastAPI routes serve Jinja2 HTML templates (not a JSON API)
- SSE endpoint: `GET /stream` — yields zone state events
- Auth endpoints: `POST /login`, `GET /logout`
- No public REST API; no external API consumers

**Error Handling Standard**
- All MQTT message handlers: try/except with structured logging; failures do not crash the service
- RTSP reconnect: exponential backoff (1s → 2s → 4s → max 60s) per stream (FR-014)
- Telegram send failures: log and retry once; do not block the alert pipeline

### Frontend Architecture

**HTMX + Jinja2 + Server-Sent Events**
- Dashboard is server-rendered HTML; HTMX handles in-place DOM updates
- Zone tiles: individual `<div id="zone-{id}">` elements, swapped via SSE OOB updates
- System health indicator: separate SSE event stream target
- No JavaScript build step; no npm; no client-side state management
- HTMX version: loaded from CDN or vendored (no npm)
- Styling: Tailwind CSS (CDN play.tailwindcss.com for MVP; vendored for production)

**Real-Time Update Pattern**
```
Browser ←SSE── FastAPI /stream ←MQTT── counter service
         HTMX hx-sse swap            aiomqtt subscription
```

### Infrastructure & Deployment

**Docker Compose Service Topology**

| Service | Image | Network | GPU | Restart |
|---------|-------|---------|-----|---------|
| `frigate` | `ghcr.io/blakeblackshear/frigate:stable` | camera-net, app-net | No | unless-stopped |
| `mosquitto` | `eclipse-mosquitto:2` | app-net | No | unless-stopped |
| `counter` | custom (Python 3.12) | app-net | ✓ NVIDIA | unless-stopped |
| `watchdog` | custom (Python 3.12) | app-net | No | unless-stopped |
| `dashboard` | custom (Python 3.12) | app-net | No | unless-stopped |
| `nginx` | `nginx:alpine` | app-net | No | unless-stopped |

**Networks**
- `camera-net`: Frigate ↔ Hikvision cameras (RTSP); isolated
- `app-net`: all application services; internal communication only
- Host port exposure: nginx → `0.0.0.0:80` (dashboard); no other external ports

**Volumes**
- `frigate-data`: Frigate recordings and config
- `db-data`: SQLite database file
- `./config/zones.yaml:/config/zones.yaml:ro`: zone definitions (read-only mount)
- `./.env`: secrets injection (never committed)

**GPU Assignment**
- Only `counter` service requests NVIDIA GPU via Docker Compose `deploy.resources.reservations.devices`
- Requires `nvidia-container-toolkit` on host
- GPU memory: YOLOv8n/s on RTX 3060 (~6GB VRAM); motion-gating ensures GPU is idle between events

**Monitoring & Observability**
- Structured logging: all services log JSON to stdout; Docker captures via `docker logs`
- Watchdog monitors: Frigate process liveness, MQTT heartbeat gaps >2 min, container health checks
- Docker health checks on `counter`, `dashboard`, `frigate`
- No external APM in MVP; log-based debugging sufficient for single-location

### Decision Impact Analysis

**Implementation Sequence (drives story ordering):**
1. Docker Compose skeleton + Mosquitto + Frigate config
2. `shared/` package: ZoneConfig Pydantic model, MQTT helpers
3. `counter` service: MQTT consumer, YOLOv8 inference, zone state machine
4. `watchdog` service: health checks, Telegram alert delivery
5. `dashboard` service: FastAPI, auth, Jinja2 templates, SSE endpoint
6. Nginx config + end-to-end integration test

**Cross-Component Dependencies:**
- `counter` depends on: Frigate MQTT events, `shared/` zone config, YOLOv8 model weights
- `watchdog` depends on: MQTT heartbeat from `counter`, Docker socket (container health), Telegram Bot token
- `dashboard` depends on: MQTT zone state events from `counter`, SQLite alert log, `shared/` zone config
- All services depend on: Mosquitto broker being healthy first (Docker `depends_on`)

## Implementation Patterns & Consistency Rules

### Critical Conflict Points Identified

7 areas where AI agents could independently make incompatible choices. All agents MUST follow these patterns without deviation.

### Naming Patterns

**Zone ID Convention**
- Format: lowercase alphanumeric + hyphens, e.g. `lot-a`, `lot-b`, `entrance-north`
- Defined once in `config/zones.yaml` under `zone_id` key
- Used identically in: MQTT topics, SQLite rows, HTML element IDs, SSE event names
- Never use spaces, underscores, or uppercase in zone IDs
- Example: zone `lot-a` → MQTT topic `parking/lot-a/state` → HTML `id="zone-lot-a"` → DB `zone_id = 'lot-a'`

**Python Code Naming**
- All Python: `snake_case` for variables, functions, modules, files
- Classes: `PascalCase` (e.g. `ZoneState`, `ZoneConfig`)
- Constants: `UPPER_SNAKE_CASE` (e.g. `DEFAULT_THRESHOLD = 0.80`)
- No abbreviations except established ones: `mqtt`, `rtsp`, `yolo`, `cfg`

**Environment Variables**
- Format: `UPPER_SNAKE_CASE` with service prefix where ambiguous
- Examples: `TELEGRAM_BOT_TOKEN`, `DASHBOARD_PASSWORD`, `MQTT_HOST`, `YOLO_CONFIDENCE_THRESHOLD`
- All declared in `.env.example` with placeholder values and comments

**Docker Service & Volume Names**
- Services: `lowercase-hyphenated` (e.g. `counter`, `watchdog`, `dashboard`)
- Volumes: `noun-data` pattern (e.g. `frigate-data`, `db-data`)
- Networks: `noun-net` pattern (e.g. `camera-net`, `app-net`)

**SQLite Naming**
- Tables: `snake_case` plural nouns (e.g. `alert_events`, `system_events`)
- Columns: `snake_case` (e.g. `zone_id`, `occupancy_pct`, `created_at`)
- No ORM — use `aiosqlite` with raw SQL; schema defined in `shared/db/schema.sql`

### Structure Patterns

**Monorepo Layout (Canonical)**
```
nuanu-parking-ai/
├── services/
│   ├── counter/
│   │   ├── src/counter/          # package source
│   │   ├── tests/                # service-level tests
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   ├── watchdog/                 # same structure
│   └── dashboard/                # same structure
├── shared/
│   ├── src/shared/
│   │   ├── models.py             # ZoneConfig, ZoneState Pydantic models
│   │   ├── mqtt.py               # MQTT client helpers
│   │   ├── db/
│   │   │   └── schema.sql
│   │   └── config.py             # Pydantic Settings base
│   └── pyproject.toml
├── config/
│   └── zones.yaml
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
└── pyproject.toml                # UV workspace root
```

**Test Location**: `tests/` directory within each service root (not co-located with source).

**Shared Package Rule**: Any model, helper, or constant used by 2+ services goes in `shared/`. Never duplicate across services.

### Format Patterns

**MQTT Zone State Payload (canonical schema)**
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
- `status` values: exactly `"ok"` | `"warning"` | `"full"` | `"degraded"` (lowercase strings)
- `occupancy_pct`: float 0.0–1.0 (not 0–100)
- `timestamp`: ISO 8601 UTC, always `Z` suffix (never naive datetime)
- Payload is the **only** schema; no variations between services

**MQTT System Health Payload**
```json
{
  "service": "counter",
  "status": "healthy",
  "timestamp": "2026-04-09T14:32:00Z"
}
```

**SSE Event Format (dashboard → browser)**
```
event: zone-update
data: {"zone_id": "lot-a", "vehicle_count": 23, "occupancy_pct": 0.46, "status": "ok", "stream_healthy": true}

event: system-alert
data: {"type": "stream_loss", "zone_id": "lot-a", "message": "Camera stream lost", "timestamp": "..."}
```
- HTMX `hx-swap-oob="true"` targets `id="zone-lot-a"` for zone tile replacement

**Datetime Rule**: All datetimes are UTC. Use `datetime.now(timezone.utc)` — never `datetime.now()` (naive). Store as ISO 8601 strings in SQLite and MQTT payloads.

### Communication Patterns

**MQTT Retained Messages**
- Zone state topics (`parking/{zone_id}/state`): **retained = True** — dashboard backend gets current state immediately on (re)connect
- System health topics: **retained = False** — stale heartbeat must not appear as current health

**Async Discipline**
- All I/O is async: `aiomqtt`, `aiosqlite`, `httpx` (async), FastAPI async routes
- Never call sync blocking functions inside `async def` — use `asyncio.to_thread()` if unavoidable
- YOLOv8 inference (CPU/GPU-bound): run in `asyncio.to_thread()` to avoid blocking the event loop
- One `asyncio.run()` entry point per service (`main.py`)

**RTSP Reconnect Pattern**
```python
async def connect_with_backoff(url: str, max_delay: int = 60):
    delay = 1
    while True:
        try:
            return await attempt_connection(url)
        except Exception:
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)
```
All stream connections use this pattern. No custom reconnect logic per stream.

### Process Patterns

**Error Handling**
- MQTT message handlers: wrapped in `try/except Exception`; log error, continue loop — never crash on a bad message
- RTSP failure: reconnect with backoff; publish `stream_healthy: false` to zone state topic
- Telegram send failure: log `ERROR`, retry once after 5s, then drop — never block the alert pipeline
- Startup validation: validate `zones.yaml` with Pydantic on service start; exit with clear error if invalid (fail fast)

**Structured Logging**
```python
# All services use JSON formatter
{"level": "INFO", "service": "counter", "message": "Zone lot-a: 23/50 (46%)", "timestamp": "2026-04-09T14:32:00Z"}
```
- Log levels: `DEBUG` for MQTT receipt, `INFO` for state changes/alerts, `WARNING` for recoverable errors, `ERROR` for failures
- No `print()` statements in production code

**Graceful Shutdown**
- All services handle `SIGTERM`: cancel background tasks, flush pending MQTT publishes, close DB connection
- Use `asyncio` signal handlers, not `signal.signal()`

### Enforcement Guidelines

**All AI Agents MUST:**
- Use `zone_id` from `zones.yaml` as the single source of truth — never hardcode zone names
- Use `ZoneState` and `ZoneConfig` Pydantic models from `shared/` — never redefine locally
- Follow the canonical MQTT payload schema — no added/removed fields without updating `shared/models.py`
- Use UTC datetimes with `timezone.utc` — never naive datetimes
- Use `"ok"/"warning"/"full"/"degraded"` status strings — never uppercase or numeric equivalents

**Anti-Patterns (Forbidden):**
- ❌ `datetime.now()` → use `datetime.now(timezone.utc)`
- ❌ `occupancy_pct = 46` (integer %) → use `occupancy_pct = 0.46` (float ratio)
- ❌ `status = "WARNING"` → use `status = "warning"`
- ❌ Duplicating `ZoneConfig` in a service → import from `shared.models`
- ❌ Sync `requests` in async services → use `httpx` async client
- ❌ `zone_id = "Lot A"` → use `"lot-a"`

## Project Structure & Boundaries

### Complete Project Directory Structure

```
nuanu-parking-ai/
│
├── pyproject.toml                    # UV workspace root
├── docker-compose.yml                # All services
├── .env.example                      # All env vars documented
├── .gitignore                        # .env, __pycache__, *.db, model weights
├── README.md
│
├── config/
│   ├── zones.yaml                    # Zone definitions (FR-008): zone_id, camera_rtsp,
│   │                                 #   capacity, threshold, vehicle_classes
│   ├── frigate/
│   │   └── config.yml                # Frigate NVR config: RTSP sources, motion zones (FR-010)
│   ├── mosquitto/
│   │   └── mosquitto.conf            # MQTT broker config: listeners, persistence
│   └── nginx/
│       └── nginx.conf                # Reverse proxy: dashboard port, auth headers
│
├── models/
│   └── yolov8n.pt                    # YOLOv8 weights (gitignored, downloaded on first run)
│
├── shared/
│   ├── pyproject.toml
│   └── src/
│       └── shared/
│           ├── __init__.py
│           ├── models.py             # ZoneConfig, ZoneState, AlertEvent Pydantic models
│           │                         # MQTT payload schemas (canonical source of truth)
│           ├── mqtt.py               # MQTTClientManager: connect, publish, subscribe helpers
│           ├── config.py             # BaseSettings: MQTT_HOST, MQTT_PORT, LOG_LEVEL
│           └── db/
│               └── schema.sql        # alert_events, system_events table definitions
│
├── services/
│   │
│   ├── counter/                      # FR-011–015: Detection, state machine, reconnect
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   └── counter/
│   │   │       ├── __init__.py
│   │   │       ├── main.py           # asyncio.run() entry point; loads zones, starts tasks
│   │   │       ├── config.py         # Settings: YOLO_MODEL_PATH, YOLO_CONFIDENCE_THRESHOLD,
│   │   │       │                     #   MQTT_*, ZONES_CONFIG_PATH
│   │   │       ├── zone_state.py     # ZoneStateMachine: count, debounce, alert arm/rearm (FR-013)
│   │   │       ├── inference.py      # YOLOv8 vehicle detection; asyncio.to_thread() wrapper
│   │   │       │                     #   FR-011 (two-stage), FR-012 (class filter)
│   │   │       ├── stream.py         # RTSP stream consumer (FFmpeg subprocess);
│   │   │       │                     #   exponential backoff reconnect (FR-014)
│   │   │       ├── mqtt_handler.py   # Frigate event subscriber; routes motion events to inference
│   │   │       └── publisher.py      # Publishes ZoneState to parking/{zone_id}/state (retained)
│   │   └── tests/
│   │       ├── test_zone_state.py    # Unit: state machine transitions, debounce, hysteresis
│   │       ├── test_inference.py     # Unit: class filtering, confidence threshold
│   │       └── test_stream.py        # Unit: backoff logic
│   │
│   ├── watchdog/                     # FR-003, FR-006, FR-015: Health monitoring, Telegram alerts
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   └── watchdog/
│   │   │       ├── __init__.py
│   │   │       ├── main.py           # Entry point; starts health monitor + Telegram bot
│   │   │       ├── config.py         # Settings: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
│   │   │       │                     #   HEARTBEAT_TIMEOUT_SECS, DOCKER_SOCKET
│   │   │       ├── health_monitor.py # Tracks heartbeats per service; detects gaps > threshold
│   │   │       │                     #   (NFR-002: alert within 2 min of failure)
│   │   │       ├── docker_monitor.py # Checks container health via Docker socket (FR-003)
│   │   │       ├── telegram.py       # Telegram alert delivery; retry-once pattern
│   │   │       └── mqtt_handler.py   # Subscribes to parking/system/health heartbeats
│   │   └── tests/
│   │       ├── test_health_monitor.py
│   │       └── test_telegram.py
│   │
│   └── dashboard/                    # FR-004–007, FR-016–017: Web UI, auth, SSE, history
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── src/
│       │   └── dashboard/
│       │       ├── __init__.py
│       │       ├── main.py           # FastAPI app factory; mounts routes, starts MQTT subscriber
│       │       ├── config.py         # Settings: DASHBOARD_USERNAME, DASHBOARD_PASSWORD,
│       │       │                     #   SECRET_KEY, DB_PATH
│       │       ├── auth.py           # Session cookie auth; require_auth dependency (FR-007)
│       │       ├── sse.py            # SSE endpoint /stream; broadcasts zone-update events
│       │       ├── mqtt_subscriber.py# Async MQTT listener → feeds SSE broadcaster
│       │       ├── db.py             # aiosqlite helpers: log alert, fetch recent events
│       │       ├── routes/
│       │       │   ├── dashboard.py  # GET / → renders dashboard.html
│       │       │   ├── auth.py       # POST /login, GET /logout
│       │       │   ├── stream.py     # GET /stream → SSE endpoint
│       │       │   └── history.py    # GET /history → post-MVP stub (FR-016–017)
│       │       └── templates/
│       │           ├── base.html     # Layout: nav, SSE connection script
│       │           ├── dashboard.html# Zone tiles grid; hx-sse OOB swap targets
│       │           ├── login.html    # Login form
│       │           └── partials/
│       │               ├── zone_tile.html     # id="zone-{zone_id}"; status badge, count, %
│       │               └── health_banner.html # System health indicator
│       └── tests/
│           ├── test_auth.py
│           ├── test_sse.py
│           └── test_routes.py
```

### Architectural Boundaries

**Service Ownership**

| Service | Owns | Does NOT touch |
|---------|------|----------------|
| `counter` | Zone state machine, YOLOv8 inference, RTSP stream lifecycle, occupancy thresholds | Telegram, dashboard HTML, SQLite |
| `watchdog` | Health monitoring, Telegram message delivery, container status | Vehicle counting, inference, dashboard rendering |
| `dashboard` | HTML rendering, SSE delivery, auth, SQLite reads | Inference, Telegram, RTSP streams |
| `shared` | Pydantic models, MQTT helpers, DB schema | Business logic, service-specific config |

**MQTT Topic Ownership**

| Topic | Publisher | Subscribers |
|-------|-----------|-------------|
| `frigate/events` | Frigate NVR | `counter` |
| `parking/{zone_id}/state` | `counter` | `dashboard`, `watchdog` |
| `parking/system/health` | `counter`, `watchdog` | `watchdog` |

**Data Boundaries**
- SQLite (`/data/parking.db`): owned by `dashboard`; alert events written on receipt of MQTT alert messages
- Zone config (`config/zones.yaml`): read-only mount in `counter` and `dashboard`; single source of truth
- YOLOv8 weights (`models/`): volume mount into `counter` only

### Requirements to Structure Mapping

| FR | Primary File(s) |
|----|-----------------|
| FR-001 (threshold alert) | `counter/zone_state.py`, `watchdog/telegram.py` |
| FR-002 (re-arm logic) | `counter/zone_state.py` |
| FR-003 (system failure alert) | `watchdog/health_monitor.py`, `watchdog/docker_monitor.py`, `watchdog/telegram.py` |
| FR-004 (live count/% view) | `dashboard/routes/dashboard.py`, `dashboard/templates/zone_tile.html` |
| FR-005 (zone status badge) | `dashboard/templates/zone_tile.html`, `shared/models.py` |
| FR-006 (health indicator) | `dashboard/sse.py`, `dashboard/templates/health_banner.html` |
| FR-007 (dashboard auth) | `dashboard/auth.py`, `dashboard/routes/auth.py` |
| FR-008 (zone config) | `config/zones.yaml`, `shared/models.py` (ZoneConfig) |
| FR-009 (config reload) | `counter/main.py` (loads on start), `docker-compose.yml` (restart) |
| FR-010 (zone masking) | `config/frigate/config.yml` (motion zones) |
| FR-011 (two-stage detection) | `counter/mqtt_handler.py`, `counter/inference.py` |
| FR-012 (class filter) | `counter/inference.py`, `config/zones.yaml` (vehicle_classes) |
| FR-013 (debounce) | `counter/zone_state.py` |
| FR-014 (auto-reconnect) | `counter/stream.py` |
| FR-015 (DEGRADED badge) | `counter/publisher.py` (stream_healthy=false), `dashboard/templates/zone_tile.html` |
| FR-016–017 (history — post-MVP) | `dashboard/routes/history.py` (stub), `dashboard/db.py` |

### Integration Points

**End-to-End Data Flow**
```
Hikvision Camera (RTSP)
  → Frigate NVR (motion detection)
    → MQTT: frigate/events
      → counter/mqtt_handler.py
        → counter/inference.py (YOLOv8 via asyncio.to_thread)
          → counter/zone_state.py (state machine + debounce)
            → counter/publisher.py
              → MQTT: parking/{zone_id}/state (retained=True)
                ├── dashboard/mqtt_subscriber.py → SSE /stream → Browser (HTMX OOB swap)
                └── watchdog/mqtt_handler.py (heartbeat tracking)
```

**Telegram Alert Flow**
```
watchdog/health_monitor.py (heartbeat gap) ──→ watchdog/telegram.py → Telegram Bot API
counter/zone_state.py (threshold crossed)  ──→ MQTT alert topic → watchdog → telegram.py
```

**External Integration**
- Telegram Bot API (`https://api.telegram.org`): outbound HTTPS from `watchdog` only; no inbound
- Hikvision cameras: RTSP inbound to `frigate` on `camera-net` only; never crosses to `app-net`

### Development Workflow

```bash
# Start infrastructure services first
docker compose up -d mosquitto frigate

# Run services locally with hot reload
uv run --package counter python -m counter.main
uv run --package dashboard fastapi dev src/dashboard/main.py

# Full stack
docker compose up --build

# Add a new zone
# 1. Edit config/zones.yaml
# 2. docker compose restart counter dashboard
```

## Architecture Validation Results

### Coherence Validation ✅

**Decision Compatibility:** All technology choices are compatible. Python 3.12, FastAPI, aiomqtt, aiosqlite, and HTMX form a coherent async Python stack with no version conflicts. Docker Compose GPU reservation follows the standard nvidia-container-toolkit pattern.

**Pattern Consistency:** Naming conventions (snake_case Python, lowercase-hyphenated zone IDs, UPPER_SNAKE_CASE env vars) are consistent across all services. MQTT retained/non-retained decisions align with subscriber reconnect behavior. Async discipline (aiomqtt, aiosqlite, httpx) is enforced uniformly.

**Structure Alignment:** Monorepo with UV workspaces correctly supports the `shared/` package pattern. Service boundaries are clean with no circular dependencies. All integration points are MQTT-mediated — no direct service-to-service HTTP.

### Requirements Coverage Validation ✅

**Functional Requirements:** 15/15 MVP FRs fully mapped to specific files. 2/2 post-MVP FRs (FR-016, FR-017) have stub implementations in `dashboard/routes/history.py`.

**Non-Functional Requirements:** All 12 NFRs architecturally addressed:
- Latency (NFR-001, 002): event-driven MQTT pipeline eliminates polling latency
- Accuracy (NFR-003–005): configurable confidence threshold + motion gating + debounce
- Reliability (NFR-006–008): Docker restart policies + exponential backoff + per-zone isolation
- Security (NFR-009–011): camera-net isolation + session auth + .env credential management
- Scalability (NFR-012): per-location Docker Compose stack replication

### Implementation Readiness Validation ✅

**Decision Completeness:** All critical decisions documented with rationale. Technology stack fully specified. Integration patterns (MQTT topics, SSE events, session auth) are concrete and implementable.

**Structure Completeness:** Complete directory tree with all files specified. All 17 FRs mapped to specific source files. Service ownership table prevents agents from touching the wrong service.

**Pattern Completeness:** 7 conflict point categories addressed with concrete examples and anti-patterns. MQTT payload schema fully specified with field types and value constraints.

### Minor Gaps & Resolutions

**1. zones.yaml schema — sample added to config/**
```yaml
# config/zones.yaml
zones:
  - zone_id: "lot-a"
    name: "Lot A — Main Entrance"
    camera_rtsp_sub: "rtsp://user:pass@192.168.1.10:554/Streaming/Channels/101"
    capacity: 50
    threshold: 0.80
    rearm_threshold: 0.70
    vehicle_classes: ["car", "truck", "motorcycle", "bus"]
```

**2. HEARTBEAT_TIMEOUT_SECS default = 90**
Counter publishes heartbeat every 60s. Timeout at 90s (1.5× interval) ensures alert fires within 150s worst-case — within the NFR-002 2-minute target.

**3. YOLOv8 model weights — download at build time**
```dockerfile
# services/counter/Dockerfile
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```
Alternative: pre-download and mount `models/` volume. Document in README.

**4. Frigate dual-stream — no conflict**
Frigate uses main stream (`/Channels/1`) for recording. `zones.yaml` `camera_rtsp_sub` references sub-stream (`/Channels/101`) for inference. Separate RTSP connections; no interference.

**5. Telegram alert format — standardized**
```
# Occupancy alert
⚠️ {zone_name} — {count}/{capacity} ({pct}%)
Threshold: {threshold*100:.0f}% | {timestamp}

# System alert
🔴 [SYSTEM] {service}: {event_description}
Last seen: {last_seen_timestamp}
```

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed (17 FRs, 12 NFRs)
- [x] Scale and complexity assessed (Medium-High, 6 services)
- [x] Technical constraints identified (RTSP quirks, GPU, MQTT)
- [x] Cross-cutting concerns mapped

**✅ Architectural Decisions**
- [x] Data architecture (in-memory state, SQLite, session cookies)
- [x] Authentication & security (session auth, network isolation)
- [x] API & communication patterns (MQTT → SSE end-to-end)
- [x] Infrastructure & deployment (Docker Compose, 6-service topology)

**✅ Implementation Patterns**
- [x] Naming conventions (zone IDs, Python, env vars, Docker)
- [x] MQTT payload schema (canonical, versioned in shared/)
- [x] Async discipline (asyncio.to_thread for YOLOv8)
- [x] Error handling, logging, graceful shutdown

**✅ Project Structure**
- [x] Complete directory tree with all files
- [x] Service ownership table
- [x] FR-to-file mapping (all 17 FRs)
- [x] End-to-end data flow diagram

### Architecture Readiness Assessment

**Overall Status: READY FOR IMPLEMENTATION**

**Confidence Level: High**

**Key Strengths:**
- Event-driven MQTT pipeline naturally meets latency NFRs without polling
- Motion-gating preserves GPU budget at 32-camera scale
- Per-zone state machine isolation guarantees NFR-008 (zone failure containment)
- `shared/` package as single source of truth prevents agent model drift
- All 5 minor gaps resolved with concrete examples above

**Areas for Future Enhancement (Post-MVP):**
- PostgreSQL migration for multi-location historical data (FR-016/017)
- Central aggregation service for 30+ location dashboard (NFR-012)
- Fine-tuned YOLOv8 model on Nuanu-specific footage (NFR-003 stretch)
- Multi-user dashboard auth (FastAPI-Users)

### Implementation Handoff

**AI Agent Guidelines:**
- Follow all patterns in "Implementation Patterns & Consistency Rules" exactly
- Start from `shared/models.py` — define ZoneConfig, ZoneState, AlertEvent first
- Never create service-local versions of models already in `shared/`
- Refer to FR-to-file mapping for every story to identify which files to touch

**First Implementation Story:**
```bash
uv init nuanu-parking-ai
uv workspace add services/counter services/watchdog services/dashboard shared
# 1. Create shared/src/shared/models.py — ZoneConfig, ZoneState, AlertEvent
# 2. Create config/zones.yaml — sample zone definition
# 3. Create docker-compose.yml skeleton — all 6 services, networks, volumes
```
