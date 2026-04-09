# Story 1.1: Project Scaffold and Docker Compose Foundation

Status: ready-for-dev

## Story

As an infrastructure administrator,
I want the nuanu-parking-ai project initialized as a Python UV monorepo with a complete Docker Compose stack,
so that all services can be developed, tested, and deployed in a consistent environment from day one.

## Acceptance Criteria

1. Given the project root, when `uv sync` is run, then the UV workspace resolves successfully with four workspace packages: shared, counter, watchdog, dashboard.
2. Given a valid `.env` file (copied from `.env.example`), when `docker compose up -d` is run, then all 6 containers start: frigate, mosquitto, counter, watchdog, dashboard, nginx — each with `restart: unless-stopped` policy.
3. Given the Docker Compose configuration, when inspected, then two Docker networks exist: `camera-net` (frigate only) and `app-net` (all application services), with no cross-contamination.
4. Given `.env.example` in the project root, when read, then it contains placeholder entries for all required environment variables: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DASHBOARD_USERNAME, DASHBOARD_PASSWORD, SECRET_KEY, MQTT_HOST, MQTT_PORT, YOLO_CONFIDENCE_THRESHOLD, HEARTBEAT_TIMEOUT_SECS — each with a comment describing its purpose.
5. Given the project root, when `.gitignore` is inspected, then the following are excluded from version control: `.env`, `*.db`, `*.pt`, `__pycache__/`, `models/`, `.venv/`.
6. Given the monorepo structure, when inspected, then it matches the canonical layout: `services/{counter,watchdog,dashboard}/`, `shared/`, `config/`, `nginx/`, `pyproject.toml` (UV workspace root), `docker-compose.yml`, `.env.example`.

## Tasks / Subtasks

- [ ] Task 1: Initialize UV workspace root (AC: 1, 6)
  - [ ] Create `pyproject.toml` at project root declaring UV workspace with members: `shared`, `services/counter`, `services/watchdog`, `services/dashboard`
  - [ ] Verify `uv sync` resolves all packages without error

- [ ] Task 2: Create shared package (AC: 1, 6)
  - [ ] `shared/pyproject.toml` — declares package `shared`, depends on pydantic>=2.0, aiomqtt>=2.0, aiosqlite>=0.21, pydantic-settings>=2.0
  - [ ] `shared/src/shared/__init__.py`
  - [ ] `shared/src/shared/models.py` — stub Pydantic v2 models: `ZoneConfig`, `ZoneState`, `AlertEvent`
  - [ ] `shared/src/shared/mqtt.py` — stub `MQTTClientManager` class
  - [ ] `shared/src/shared/config.py` — stub `BaseSettings` subclass for MQTT_HOST, MQTT_PORT, LOG_LEVEL
  - [ ] `shared/src/shared/db/__init__.py`
  - [ ] `shared/src/shared/db/schema.sql` — `alert_events` and `system_events` CREATE TABLE statements

- [ ] Task 3: Create service package skeletons (AC: 1, 2, 6)
  - [ ] `services/counter/pyproject.toml` — depends on workspace `shared`, ultralytics>=8.0, pydantic-settings>=2.0, aiomqtt>=2.0
  - [ ] `services/counter/Dockerfile` — FROM python:3.12-slim, install UV, copy source, `RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"` to pre-download weights
  - [ ] `services/counter/src/counter/__init__.py`
  - [ ] `services/counter/src/counter/main.py` — stub `async def main()` with `asyncio.run(main())`
  - [ ] `services/counter/tests/` — empty dir with `.gitkeep`
  - [ ] `services/watchdog/pyproject.toml` — depends on workspace `shared`, python-telegram-bot>=22.0, aiomqtt>=2.0, pydantic-settings>=2.0, docker>=7.0
  - [ ] `services/watchdog/Dockerfile` — FROM python:3.12-slim
  - [ ] `services/watchdog/src/watchdog/__init__.py`
  - [ ] `services/watchdog/src/watchdog/main.py` — stub
  - [ ] `services/watchdog/tests/` — empty dir with `.gitkeep`
  - [ ] `services/dashboard/pyproject.toml` — depends on workspace `shared`, fastapi>=0.115, uvicorn[standard]>=0.34, jinja2>=3.1, itsdangerous>=2.2, aiosqlite>=0.21, aiomqtt>=2.0, pydantic-settings>=2.0, python-multipart>=0.0.20
  - [ ] `services/dashboard/Dockerfile` — FROM python:3.12-slim
  - [ ] `services/dashboard/src/dashboard/__init__.py`
  - [ ] `services/dashboard/src/dashboard/main.py` — stub FastAPI app
  - [ ] `services/dashboard/tests/` — empty dir with `.gitkeep`

- [ ] Task 4: Create config files (AC: 2, 6)
  - [ ] `config/zones.yaml` — sample zone entry (see Dev Notes for exact schema)
  - [ ] `config/frigate/config.yml` — minimal Frigate stub (MQTT broker address, placeholder camera)
  - [ ] `config/mosquitto/mosquitto.conf` — listener 1883, allow_anonymous true (local network only), persistence true
  - [ ] `config/nginx/nginx.conf` — stub reverse proxy to dashboard:8000

- [ ] Task 5: Create `docker-compose.yml` (AC: 2, 3)
  - [ ] Define all 6 services: frigate, mosquitto, counter, watchdog, dashboard, nginx
  - [ ] Assign `camera-net` to frigate only; `app-net` to all services
  - [ ] Add GPU reservation on counter (see Dev Notes)
  - [ ] Add `restart: unless-stopped` to all services
  - [ ] Add Docker health checks on counter, dashboard, frigate
  - [ ] Mount `./config/zones.yaml:/config/zones.yaml:ro` on counter and dashboard
  - [ ] Declare named volumes: `frigate-data`, `db-data`
  - [ ] Use `env_file: .env` on services that need secrets

- [ ] Task 6: Create `.env.example` and `.gitignore` (AC: 4, 5)
  - [ ] `.env.example` with all env vars (see Dev Notes for full list)
  - [ ] `.gitignore` excluding all sensitive/generated files

- [ ] Task 7: Verify end-to-end scaffold (AC: 1, 2)
  - [ ] Run `uv sync` — confirm zero errors
  - [ ] Run `docker compose build` — confirm all images build
  - [ ] Run `docker compose up -d mosquitto` — confirm Mosquitto starts on app-net

## Dev Notes

### Technical Stack (exact versions)
- **Python**: 3.12+ (use `python:3.12-slim` as Docker base)
- **UV**: 0.5.x — workspace package manager, replaces Poetry
- **Pydantic**: v2.x (`pydantic>=2.0`) — NOTE: Pydantic v2 has breaking API changes from v1; use `model_validator`, `field_validator`, `model_config = ConfigDict(...)` — NOT `@validator` or `class Config`
- **FastAPI**: 0.115+ with `uvicorn[standard]` for async support
- **aiomqtt**: 2.x — async MQTT client; API differs from paho-mqtt
- **aiosqlite**: 0.21+ — async SQLite
- **python-telegram-bot**: 22.x (async) — PTBv22 requires `Application.builder()`, not `Updater`
- **ultralytics**: 8.x — YOLOv8; model download via `YOLO('yolov8n.pt')` fetches from Ultralytics hub
- **itsdangerous**: 2.2+ — `URLSafeTimedSerializer` for signed cookies
- **Jinja2**: 3.1+
- **HTMX**: 2.x (loaded via CDN in base.html — no npm needed)

### UV Workspace Root pyproject.toml
```toml
[tool.uv.workspace]
members = ["shared", "services/counter", "services/watchdog", "services/dashboard"]

[tool.uv]
dev-dependencies = ["pytest>=8.0", "pytest-asyncio>=0.24"]
```

### Canonical Directory Structure
Exact layout to create — do not deviate:
```
nuanu-parking-ai/
├── pyproject.toml                    # UV workspace root
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md                         # brief project overview
├── config/
│   ├── zones.yaml
│   ├── frigate/
│   │   └── config.yml
│   ├── mosquitto/
│   │   └── mosquitto.conf
│   └── nginx/
│       └── nginx.conf
├── models/                           # gitignored; YOLOv8 weights land here
├── shared/
│   ├── pyproject.toml
│   └── src/
│       └── shared/
│           ├── __init__.py
│           ├── models.py
│           ├── mqtt.py
│           ├── config.py
│           └── db/
│               ├── __init__.py
│               └── schema.sql
└── services/
    ├── counter/
    │   ├── pyproject.toml
    │   ├── Dockerfile
    │   ├── src/counter/
    │   │   ├── __init__.py
    │   │   └── main.py
    │   └── tests/
    │       └── .gitkeep
    ├── watchdog/
    │   ├── pyproject.toml
    │   ├── Dockerfile
    │   ├── src/watchdog/
    │   │   ├── __init__.py
    │   │   └── main.py
    │   └── tests/
    │       └── .gitkeep
    └── dashboard/
        ├── pyproject.toml
        ├── Dockerfile
        ├── src/dashboard/
        │   ├── __init__.py
        │   └── main.py
        └── tests/
            └── .gitkeep
```

### Shared Package Stubs (models.py)
Create these as stubs with correct Pydantic v2 syntax — they will be completed in later stories:
```python
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings
from typing import Literal
from datetime import datetime

class ZoneConfig(BaseModel):
    zone_id: str        # lowercase-hyphenated, e.g. "lot-a"
    name: str
    camera_rtsp_sub: str
    capacity: int
    threshold: float    # 0.0–1.0
    rearm_threshold: float
    vehicle_classes: list[str]  # ["car", "truck", "motorcycle", "bus"]

class ZoneState(BaseModel):
    zone_id: str
    vehicle_count: int
    capacity: int
    occupancy_pct: float    # 0.0–1.0, NOT 0–100
    status: Literal["ok", "warning", "full", "degraded"]
    alert_armed: bool
    stream_healthy: bool
    timestamp: str          # ISO 8601 UTC, always "Z" suffix

class AlertEvent(BaseModel):
    zone_id: str
    alert_type: str
    occupancy_pct: float
    vehicle_count: int
    created_at: str
```

### Canonical zones.yaml Sample
```yaml
zones:
  - zone_id: "lot-a"
    name: "Lot A — Main Entrance"
    camera_rtsp_sub: "rtsp://user:pass@192.168.1.10:554/Streaming/Channels/101"
    capacity: 50
    threshold: 0.80
    rearm_threshold: 0.70
    vehicle_classes: ["car", "truck", "motorcycle", "bus"]
```

### Docker Compose — GPU Reservation (counter service only)
```yaml
services:
  counter:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```
Requires `nvidia-container-toolkit` on the host. If GPU unavailable at dev time, comment this block out.

### Docker Compose — Network Isolation
```yaml
networks:
  camera-net:
    driver: bridge
  app-net:
    driver: bridge

services:
  frigate:
    networks: [camera-net, app-net]   # frigate bridges both: reads RTSP, publishes MQTT
  mosquitto:
    networks: [app-net]
  counter:
    networks: [app-net]
  watchdog:
    networks: [app-net]
  dashboard:
    networks: [app-net]
  nginx:
    networks: [app-net]
```

### Docker Compose — Health Checks
```yaml
services:
  counter:
    healthcheck:
      test: ["CMD", "python", "-c", "import counter; print('ok')"]
      interval: 30s
      timeout: 10s
      retries: 3
  dashboard:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
  frigate:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/version"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### .env.example — Complete List
```bash
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here      # From @BotFather
TELEGRAM_CHAT_ID=your_chat_id_here          # Group or channel ID (negative for groups)

# Dashboard Auth
DASHBOARD_USERNAME=admin                     # Login username
DASHBOARD_PASSWORD=changeme                  # Login password (change in production!)
SECRET_KEY=generate-a-random-32-char-string  # Cookie signing key: python -c "import secrets; print(secrets.token_hex(32))"

# MQTT Broker (internal Docker service name)
MQTT_HOST=mosquitto
MQTT_PORT=1883

# YOLOv8 Inference
YOLO_CONFIDENCE_THRESHOLD=0.65              # Minimum detection confidence (0.0–1.0)

# Watchdog
HEARTBEAT_TIMEOUT_SECS=90                   # Alert if no heartbeat for this many seconds
```

### Mosquitto Config
```
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_type all
```
Note: `allow_anonymous true` is acceptable for a local network only (camera-net/app-net isolation ensures no external access).

### Frigate Config Stub
```yaml
mqtt:
  host: mosquitto
  port: 1883

cameras: {}   # populated in Story 1.3

detectors:
  cpu1:
    type: cpu
    num_threads: 3
```

### Nginx Stub
```nginx
server {
    listen 80;
    location / {
        proxy_pass http://dashboard:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        # Required for SSE (Server-Sent Events)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }
}
```
**Critical:** `proxy_buffering off` is required for SSE to work through nginx — without it, SSE events are buffered and never reach the browser in real-time.

### Naming Conventions (Enforce from Day 1)
- **Python code**: `snake_case` variables/functions/files, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- **Zone IDs**: lowercase-hyphenated (e.g. `lot-a`) — never spaces, underscores, or uppercase
- **Docker services/networks/volumes**: lowercase-hyphenated (e.g. `camera-net`, `app-net`, `db-data`)
- **Env vars**: `UPPER_SNAKE_CASE` (e.g. `MQTT_HOST`, `TELEGRAM_BOT_TOKEN`)

### Anti-Patterns — FORBIDDEN from Day 1
- ❌ `datetime.now()` → always use `datetime.now(timezone.utc)`
- ❌ `occupancy_pct = 46` (integer %) → use `occupancy_pct = 0.46` (float ratio)
- ❌ `status = "WARNING"` → use `status = "warning"` (lowercase)
- ❌ `zone_id = "Lot A"` → use `"lot-a"` (lowercase-hyphenated)
- ❌ `import requests` in async services → use `httpx` async client
- ❌ Pydantic v1 `@validator` decorator → use Pydantic v2 `@field_validator`

### SQLite Schema (shared/db/schema.sql)
```sql
CREATE TABLE IF NOT EXISTS alert_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    occupancy_pct REAL NOT NULL,
    vehicle_count INTEGER NOT NULL,
    created_at TEXT NOT NULL  -- ISO 8601 UTC
);

CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL  -- ISO 8601 UTC
);
```

### Service Dockerfile Pattern
All three service Dockerfiles follow this pattern:
```dockerfile
FROM python:3.12-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy workspace files needed for this service
COPY pyproject.toml .
COPY shared/ ./shared/
COPY services/{service}/ ./services/{service}/

# Install dependencies
RUN uv sync --package {service} --no-dev

# For counter only: pre-download YOLOv8 weights
# RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

CMD ["uv", "run", "--package", "{service}", "python", "-m", "{service}.main"]
```

### Project Structure Notes
- All services use `src` layout (e.g. `services/counter/src/counter/`) — this is required for UV workspaces with proper package isolation
- Tests go in `tests/` directory within each service root, NOT co-located with source
- The `shared` package is referenced as a workspace dependency in each service's `pyproject.toml` using `shared = {workspace = true}`
- No `requirements.txt` files — UV lockfile only (`uv.lock` at project root)

### References
- UV workspaces: [Source: architecture.md#Starter Template Evaluation]
- Docker Compose topology: [Source: architecture.md#Infrastructure & Deployment]
- Canonical directory structure: [Source: architecture.md#Complete Project Directory Structure]
- MQTT canonical payload schema: [Source: architecture.md#MQTT Zone State Payload]
- Naming conventions and anti-patterns: [Source: architecture.md#Implementation Patterns & Consistency Rules]
- zones.yaml sample: [Source: architecture.md#Minor Gaps & Resolutions]
- Story ACs: [Source: epics.md#Story 1.1]

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

### Completion Notes List

### File List
