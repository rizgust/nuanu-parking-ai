---
title: "Product Brief Distillate: nuanu-parking-ai"
type: llm-distillate
source: "product-brief-nuanu-parking-ai.md"
created: "2026-04-08"
purpose: "Token-efficient context for downstream PRD creation"
---

# Nuanu Parking AI — Detail Pack

## Project Identity
- Project name: nuanu-parking-ai
- Location: Nuanu creative township, Bali, Indonesia
- Owner/contact: boss (security & infra team lead)
- Timeline: MVP in <1 month; full rollout across 30 locations ~Year 1

---

## Problem Context (Richer Than Brief)
- Current state: zero automated parking visibility. Field staff physically walk lots, call in via phone or radio to control room.
- No threshold alerting, no live count, no historical data.
- Pain is worst during events and peak hours — lot fills before ops team can act.
- Secondary cost: field staff time wasted on parking walks that automation should replace.
- Comms infra: phone calls + radio (direct or handheld). This is the integration baseline Telegram replaces.

---

## Solution Design Decisions

### Chosen Approach: Motion-Triggered Hybrid (Option 3)
- **Rejected: Option 1 — Continuous YOLO streaming.** High GPU cost, no benefit for mostly-idle lots. Would saturate GPU on 32 cameras.
- **Rejected: Option 2 — Pure interval snapshot.** Risk of missing transient vehicles between intervals. Less responsive. Lacks the accuracy boost of confirmation step.
- **Chosen: Option 3 — Motion detection wakes system → AI vision confirms vehicle.** Best accuracy/resource tradeoff. Frigate handles motion trigger; YOLOv8 confirms it's actually a vehicle (not dog, shadow, swaying tree). Only then increment counter.
- Confidence threshold: high-confidence vehicle class only (exact threshold TBD during calibration, likely ≥0.6–0.7)

### Counter Logic Requirements
- Per-zone state machine — each camera zone has independent count + capacity config
- **Hysteresis/debounce required:** prevent jitter from re-triggering alerts (e.g., car briefly moves then resettles). Suggest: only change state if N consecutive frames agree.
- Track: vehicles_present, zone_capacity, occupancy_pct, last_updated
- Alert fires when occupancy_pct crosses threshold (default 80%, configurable per zone)
- Alert should NOT re-fire every frame once threshold is crossed — fire once, then re-arm after occupancy drops below threshold minus a buffer (e.g., re-arm at 70%)

---

## Technical Constraints & Preferences

### Language
- **Primary: Python** — all AI, counter logic, alerting, dashboard backend
- **Optional: Go** — considered for high-concurrency stream management daemon; not required for MVP
- No Node.js preference stated

### Infrastructure
- **Local GPU server** — general-purpose, GPU-enabled. Not a Raspberry Pi. Spec not locked down but assume mid-range GPU (e.g., RTX 3060+ class).
- **No cloud dependency** — hard requirement. All inference, storage, and alerting on-prem. Reason: data privacy (CCTV footage), no subscription cost, latency control.
- **Docker Compose** — deployment method. Each service containerized.
- **Network:** CCTV and processing server on the same local network. Not internet-exposed by default.

### Cameras
- **32 Hikvision cameras**, RTSP streams
- **Fixed angle** — each camera covers a defined, static parking zone. No PTZ.
- RTSP URL format: `rtsp://username:password@<ip>:554/Streaming/Channels/1` (main stream) or `/Channels/101` (sub-stream)
- Known Hikvision RTSP quirks:
  - 3–5 second buffering latency with OpenCV — use FFmpeg with `-rtsp_transport tcp -fflags nobuffer`
  - Connection drops after 5–10 min idle — implement exponential backoff reconnect
  - Frame corruption at high bitrates on congested network — may need to use sub-stream (lower res) for inference
- **Use FFmpeg over OpenCV** for production reliability at scale

### Frigate NVR
- Open-source NVR, Docker-deployed, local inference
- Motion detection triggers → MQTT message → Python consumer triggers YOLOv8 inference
- Integration method: MQTT pub/sub (not REST API, for low-latency event handling)
- **Scaling note:** Frigate is designed for homelab. At 30 locations: deploy one Frigate instance per location, not one central instance. Central coordination layer handles aggregation.
- GPU acceleration: single Google Coral handles 8–16 cameras. For 32 cameras, need 2–3 Coral units OR use GPU (NVIDIA CUDA). Confirm hardware accelerator strategy before scaling beyond MVP.

### YOLOv8
- Model: YOLOv8 (Ultralytics). YOLOv8n or YOLOv8s for edge speed; YOLOv8m if GPU can handle it.
- Vehicle classes to count: car, truck, motorcycle, bus (configurable per zone — a motorbike lot has different capacity math than a car lot)
- Known accuracy challenges in this environment:
  - Partial occlusion (cars behind pillars/trees)
  - Tropical lighting extremes (midday glare, night shadows)
  - Wide-angle fixed cameras may show small vehicle bounding boxes — may need fine-tuning on Nuanu footage
- Pre-trained weights sufficient for MVP; consider fine-tuning on Nuanu-specific footage if accuracy < 90% in production

### Alert Delivery
- **Telegram:** `python-telegram-bot` v22+ (async). Rich formatting: zone name, occupancy %, timestamp, link to dashboard.
- **Rate limiting:** Telegram allows ~30 messages/sec per bot. With debounce logic, this is not a concern for MVP. Implement message batching for multi-zone events.
- **Dashboard webapp:** Web-based, live updates. Stack not locked — suggest FastAPI + simple frontend (HTMX or React) for MVP. Must show: per-zone count, capacity %, status badge (OK / WARNING / FULL), system health indicator.
- Alert channels: Telegram group/channel for security team. Dashboard on monitoring screen at security desk.

### System Health / Watchdog (MVP-critical)
- System must detect and alert on: stream loss, Frigate process crash, YOLOv8 inference failure, Docker container down
- Alert method: Telegram (same bot, separate admin channel or same channel with [SYSTEM] prefix)
- Heartbeat: publish status every N minutes. If heartbeat stops, watchdog fires alert.
- Dashboard must show system health indicator alongside occupancy data — team should never trust stale data silently

---

## Scope Signals

### In for MVP
- 2–4 cameras, single parking area (phased: validate accuracy first, then expand)
- Zone definition: config file specifying camera ID, zone name, total capacity, threshold %
- Live vehicle counter per zone
- Telegram alert at threshold (default 80%)
- Basic web dashboard (live count, %, status, health)
- Watchdog / health monitoring with Telegram alert
- Counter debounce/hysteresis

### Explicitly Out of MVP Scope (with rationale)
- **ALPR / license plate recognition** — not needed for occupancy counting; adds complexity and cost
- **Cloud deployment** — data privacy + cost; on-prem only
- **Mobile app** — Telegram covers mobile alerting adequately for MVP
- **Multi-location central console** — out for MVP; single location first
- **Historical analytics / reporting** — out for MVP; add after data pipeline stable
- **Entrance signage control** — future automation; not manual-ops-replacing for now
- **Guest booking system integration** — Year 2+ roadmap

### Maybe / Post-MVP
- Go-based stream management daemon (if Python concurrency proves problematic at 32 cameras)
- Fine-tuned YOLOv8 model on Nuanu footage (if baseline accuracy < 90%)
- Sub-stream RTSP for inference + main stream for recording

---

## Rollout Plan
- **Phase 1 (MVP, Month 1):** 2–4 cameras, 1 area, validate accuracy
- **Phase 2 (Month 2–3):** Full 32 cameras, all primary Nuanu parking zones
- **Phase 3 (Month 4–6):** Expand to 10 of 30 locations
- **Phase 4 (Year 1):** All 30 locations live
- **Phase 5 (Year 2+):** Booking integration, predictive modeling, automated signage

---

## Open Questions / Risks for PRD
1. **80% threshold validation** — needs calibration on live Nuanu footage during peak hours. May need per-zone tuning.
2. **GPU capacity planning** — need to confirm server GPU model before specifying inference batch size and camera count limits.
3. **Motorcycle vs car counting** — Nuanu is in Bali; motorbike density is high. Do motorcycle lots have separate capacity config? Does a motorbike count the same as a car for occupancy %?
4. **Night/low-light performance** — Hikvision cameras likely have IR night mode. YOLOv8 performance on IR footage needs validation.
5. **Who maintains the system?** — Infra team. Document restart/recovery procedures for non-engineers.
6. **RTSP credentials security** — how are camera passwords managed in Docker env? Needs secrets management strategy (env file, Docker secrets, or vault).
7. **Dashboard authentication** — should the dashboard be open on the local network or require login? Security team context = probably login-protected.
