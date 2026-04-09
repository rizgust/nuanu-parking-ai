# nuanu-parking-ai

On-premises AI-powered parking occupancy monitoring for Nuanu creative township, Bali.

**Stack:** Python 3.12 · UV monorepo · FastAPI · HTMX · YOLOv8 · Frigate NVR · MQTT · Docker Compose

## Quick Start

```bash
cp .env.example .env
# Edit .env with your Telegram token, dashboard credentials, and camera RTSP URLs

docker compose up -d
```

Dashboard: http://localhost (login with credentials from .env)

## Architecture

```
Hikvision Camera (RTSP)
  → Frigate NVR (motion detection)
    → MQTT: frigate/events
      → counter service (YOLOv8 inference + zone state machine)
        → MQTT: parking/{zone_id}/state (retained)
          ├── dashboard (SSE → browser HTMX)
          └── watchdog (health monitoring → Telegram alerts)
```

## Services

| Service | Purpose |
|---------|---------|
| `frigate` | Motion detection from RTSP camera streams |
| `mosquitto` | MQTT message broker (internal) |
| `counter` | YOLOv8 vehicle detection + zone state machine |
| `watchdog` | Health monitoring + Telegram alerts |
| `dashboard` | FastAPI + HTMX web dashboard |
| `nginx` | Reverse proxy on port 80 |

## Zone Configuration

Edit `config/zones.yaml` to define parking zones. Restart counter and dashboard after changes:

```bash
docker compose restart counter dashboard
```

## Development

```bash
# Install dependencies
uv sync

# Start infrastructure only
docker compose up -d mosquitto frigate

# Run a service locally
uv run --package counter python -m counter.main
uv run --package dashboard fastapi dev services/dashboard/src/dashboard/main.py
```
