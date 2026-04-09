# Story 1.3: Frigate NVR Setup and Zone Masking

Status: ready-for-dev

## Story

As an infrastructure administrator,
I want Frigate NVR configured to monitor each parking zone's camera feed and detect motion only within the designated parking area,
So that motion events are scoped to actual parking zones and irrelevant areas (roads, footpaths, trees) are masked out to reduce false triggers.

## Acceptance Criteria

1. **Given** `config/frigate/config.yml` with at least one RTSP camera source, **When** Frigate starts, **Then** it connects to the configured camera sub-stream without errors and the Frigate web UI (port 5000) shows the camera feed as active.

2. **Given** a Frigate config with motion zones defined for a parking area, **When** a vehicle enters the defined zone boundary, **Then** Frigate publishes a motion event to the `frigate/events` MQTT topic on the Mosquitto broker.

3. **Given** a Frigate config with a motion mask applied to non-parking areas (e.g. road in frame foreground), **When** movement occurs exclusively within the masked area, **Then** no MQTT event is published for that motion — only parking-zone motion triggers events.

4. **Given** the Docker Compose network configuration, **When** Frigate is running, **Then** it is connected to both `camera-net` (for RTSP access) and `app-net` (for MQTT publishing).

5. **Given** a Docker restart of the Frigate container, **When** it comes back up, **Then** zone mask definitions are preserved via the `frigate-data` volume mount — no reconfiguration required.

## Tasks / Subtasks

- [ ] Task 1: Update `config/frigate/config.yml` with real camera and zone definition (AC: 1, 2, 4)
  - [ ] Replace the stub camera template with a real `lot-a` camera entry using `camera_rtsp_sub` from `config/zones.yaml`
  - [ ] Set camera name to match zone_id exactly (e.g. Frigate camera `"lot-a"` ↔ zone_id `"lot-a"`)
  - [ ] Configure `detect` role on sub-stream: width 1280, height 720, fps 5 (Hikvision sub-stream defaults)
  - [ ] Set `objects.track: [car, truck, motorcycle, bus]` to limit tracked classes

- [ ] Task 2: Define motion zones per camera (AC: 2)
  - [ ] Add `zones:` block under each camera using polygon coordinates (fraction of frame, 0.0–1.0)
  - [ ] Zone name must match zone_id exactly (e.g. `lot-a:` under camera `lot-a:`)
  - [ ] Set `min_area` to exclude small false-positive detections (recommend 5000 pixels)

- [ ] Task 3: Add motion masks to exclude non-parking areas (AC: 3)
  - [ ] Add `motion.mask:` polygons to exclude roads, footpaths, tree canopy from motion detection
  - [ ] Use normalized coordinates (0.0–1.0 fraction of frame width/height)
  - [ ] Provide at least one mask polygon for the `lot-a` camera (template for admin to adjust)

- [ ] Task 4: Verify MQTT event publication and Frigate web UI (AC: 1, 2, 4)
  - [ ] Confirm `config/frigate/config.yml` is valid YAML (syntax check with `python3 -c "import yaml; yaml.safe_load(open('config/frigate/config.yml'))"`)
  - [ ] Document verification steps: start stack, open Frigate UI at `http://localhost:5000`, check camera feed active
  - [ ] Document how to subscribe to MQTT to verify events: `docker exec mosquitto mosquitto_sub -t 'frigate/#' -v`

## Dev Notes

### Frigate Version and Image

- Image: `ghcr.io/blakeblackshear/frigate:stable` (as in docker-compose.yml)
- Frigate ≥ 0.14 config format applies. Do NOT use deprecated `detectors.coral` syntax.
- Frigate web UI: `http://localhost:5000` (host port 5000 mapped in docker-compose.yml)
- Frigate HTTP API: `http://frigate:5000` (internal Docker hostname on app-net)

### Critical Convention: Camera Name = Zone ID

The counter service routes Frigate events to zones using `event["after"]["camera"]` matched against `zone_id` from `zones.yaml`. The Frigate camera name MUST equal the zone_id exactly.

| zones.yaml zone_id | Frigate camera name |
|--------------------|---------------------|
| `lot-a` | `lot-a` |
| `lot-b` | `lot-b` |

This convention avoids a separate mapping table. Never use display names or uppercase in Frigate camera names.

### Complete `config/frigate/config.yml` Template

Replace the stub with this complete config, then edit RTSP URLs and polygon coordinates for the actual site:

```yaml
mqtt:
  host: mosquitto
  port: 1883
  # topic_prefix: frigate  (default — events published to frigate/events)

# Detectors: cpu for dev; replace with tensorrt or openvino for GPU production
detectors:
  cpu1:
    type: cpu
    num_threads: 3

# Object tracking: only count vehicle classes; ignore people, animals, etc.
objects:
  track:
    - car
    - truck
    - motorcycle
    - bus
  filters:
    car:
      min_score: 0.5      # Frigate pre-filter; fine-grained threshold applied in counter (Story 1.4)
    truck:
      min_score: 0.5
    motorcycle:
      min_score: 0.4      # Motorcycles are smaller — slightly lower pre-filter
    bus:
      min_score: 0.5

cameras:
  lot-a:                  # MUST match zone_id in zones.yaml
    ffmpeg:
      inputs:
        - path: rtsp://admin:${FRIGATE_RTSP_PASSWORD}@192.168.1.10:554/Streaming/Channels/101
          roles:
            - detect
    detect:
      width: 1280
      height: 720
      fps: 5              # Sub-stream FPS; 5fps is sufficient for parking (slow movement)
      enabled: true

    # Motion zones: Frigate only triggers events when motion occurs inside these polygons.
    # Format: list of [x,y] pairs as fractions of frame (0.0–1.0).
    # Draw polygons using Frigate UI (Config > Cameras > lot-a > Mask & Zone creator)
    zones:
      lot-a:              # Zone name MUST match camera name (= zone_id)
        coordinates: 0.1,0.2,0.9,0.2,0.9,0.9,0.1,0.9
        # ^ Placeholder rectangle. Replace with actual parking area polygon from Frigate UI.
        objects:
          - car
          - truck
          - motorcycle
          - bus

    # Motion masks: Exclude non-parking areas (roads, footpaths, sky, trees).
    # Frigate does NOT publish events for motion in masked areas.
    motion:
      mask:
        # Example: exclude road at the bottom 15% of frame
        - 0,0.85,1,0.85,1,1,0,1
        # Example: exclude footpath on left edge
        - 0,0,0.08,0,0.08,1,0,1
        # Adjust or add more polygons based on actual camera view.
        # Use the Frigate UI mask editor for precision: Config > Cameras > lot-a > Mask & Zone creator
```

### Environment Variable for RTSP Credentials

The Frigate config uses `${FRIGATE_RTSP_PASSWORD}` for the camera password — this is read by Frigate from the environment. Set `FRIGATE_RTSP_PASSWORD` in `.env`. The username (`admin`) is typically hardcoded in Frigate config unless multiple cameras use different users.

`config/zones.yaml` field `camera_rtsp_sub` also stores the full RTSP URL — these must match.

### Frigate Motion Event MQTT Format

Frigate publishes to `frigate/events` with this JSON structure (relevant fields for counter):

```json
{
  "type": "new",
  "before": {},
  "after": {
    "id": "1234567890.123456-abc123",
    "camera": "lot-a",
    "label": "car",
    "top_score": 0.87,
    "frame_time": 1712669520.123,
    "snapshot": {
      "frame_time": 1712669520.123,
      "box": [352, 180, 640, 420]
    },
    "stationary": false,
    "entered_zones": ["lot-a"]
  }
}
```

Key fields the counter (Story 1.4) uses:
- `after.camera` → maps to `zone_id`
- `after.id` → used to fetch snapshot from Frigate API
- `after.label` → pre-filtered label (counter re-validates with YOLOv8)
- `type` → only process `"new"` events (ignore `"update"`, `"end"`)

### Fetching Snapshots from Frigate

After receiving a motion event, the counter fetches the frame snapshot via:
```
GET http://frigate:5000/api/events/{event_id}/snapshot.jpg
```
This returns JPEG bytes that can be passed directly to YOLOv8 (implemented in Story 1.4).

The Frigate API base URL is `http://frigate:5000` on `app-net` (internal Docker service name).

### Zone Polygon Coordinate Format

Frigate uses normalized coordinates as a flat comma-separated string:
```
x1,y1,x2,y2,x3,y3,...   # where 0.0=top-left, 1.0=bottom-right
```

Example: `0.1,0.2,0.9,0.2,0.9,0.9,0.1,0.9` defines a rectangle from (10%, 20%) to (90%, 90%) of the frame.

**Practical approach for production deployment:**
1. Start Frigate with a placeholder polygon
2. Open Frigate UI → Config → Cameras → `lot-a` → Mask & Zone Creator
3. Draw the actual parking zone boundary visually
4. Copy the generated coordinates back into `config/frigate/config.yml`

### GPU Detector (for Production)

For the RTX 3060 production host, replace `cpu1` detector with TensorRT:
```yaml
detectors:
  tensorrt:
    type: tensorrt
    device: 0
```
This reduces Frigate motion detection CPU load. The `counter` service still uses the NVIDIA GPU for YOLOv8. Both can share the GPU (Frigate uses it for detection model, counter for inference).

### Verification Steps (No Automated Tests — Config Story)

This story is config-only. Manual verification steps:

1. Start the stack: `docker compose up -d frigate mosquitto`
2. Open Frigate UI: `http://localhost:5000` → verify camera feed shows in UI
3. Subscribe to Frigate MQTT events:
   ```bash
   docker exec mosquitto mosquitto_sub -t 'frigate/events' -v
   ```
4. Wave hand in front of camera → observe MQTT event published
5. Move only in a masked area → confirm no MQTT event published

### Story 1.1 Files Not to Regress

- `config/frigate/config.yml` — **REPLACE** with Story 1.3 complete version
- `docker-compose.yml` — no changes; Frigate already has `camera-net` and `app-net`
- `config/mosquitto/mosquitto.conf` — no changes

## Dev Agent Record

### Agent Model Used

_to be filled by dev agent_

### Debug Log References

_to be filled by dev agent_

### Completion Notes List

_to be filled by dev agent_

### File List

- `config/frigate/config.yml` (modified — replace stub with full camera config)
