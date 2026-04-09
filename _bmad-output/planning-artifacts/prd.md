---
stepsCompleted: ["step-01-init", "step-02-discovery", "step-02b-vision", "step-02c-executive-summary", "step-03-success", "step-04-journeys", "step-05-domain", "step-06-innovation", "step-e-03-edit"]
classification:
  projectType: "iot_embedded+web_app"
  domain: "scientific/general"
  complexity: "medium-high"
  projectContext: "greenfield"
inputDocuments:
  - "_bmad-output/planning-artifacts/product-brief-nuanu-parking-ai.md"
  - "_bmad-output/planning-artifacts/product-brief-nuanu-parking-ai-distillate.md"
briefCount: 2
researchCount: 0
brainstormingCount: 0
projectDocsCount: 0
workflowType: 'prd'
lastEdited: '2026-04-09'
editHistory:
  - date: '2026-04-09'
    changes: 'Added Functional Requirements (FR-001–FR-017) and Non-Functional Requirements (NFR-001–NFR-012) sections'
---

# Product Requirements Document - nuanu-parking-ai

**Author:** boss
**Date:** 2026-04-08

## Executive Summary

Nuanu Parking AI is an on-premises AI-powered parking occupancy monitoring system for Nuanu creative township, Bali. It processes live RTSP streams from existing Hikvision CCTV infrastructure to deliver real-time vehicle counts per parking zone, alerting the security and infrastructure team via Telegram and a web dashboard when occupancy crosses a configurable threshold (default: 80%). No new hardware, no cloud dependency, no vendor subscription.

The system replaces a manual, radio-and-phone-based workflow in which field staff physically walk lots and call in status reports — a process that is slow, labor-intensive, and inherently reactive. By the time a report reaches the control room, the situation may have already changed. Nuanu Parking AI eliminates that lag, giving operators continuous situational awareness and a proactive intervention window before a zone reaches capacity.

Target users are the Nuanu security and infrastructure team — the daily operators responsible for managing parking flow across multiple zones. Secondary users are operations leadership, who gain dashboard access and trend data for infrastructure and event planning decisions. MVP targets a single parking area with 2–4 cameras; the architecture supports phased expansion to 30+ locations.

### What Makes This Special

- **Motion-triggered hybrid detection:** Frigate NVR handles motion detection to wake the AI; YOLOv8 confirms vehicle presence at high confidence before incrementing any counter. This eliminates false positives from shadows, animals, and pedestrians while consuming a fraction of the GPU resources required by continuous YOLO streaming.
- **Operationally honest:** The system surfaces its own failure states — stream loss, process crash, container down — via Telegram alert within 2 minutes. Operators never silently receive stale data.
- **Infrastructure-native:** Runs entirely on the existing local CCTV network and a GPU server Nuanu already operates. Zero external dependencies.
- **Built to scale without redesign:** Single-location Docker Compose deployment scales to 30 locations by replicating the same service stack per site, with a central aggregation layer added when needed.

## Project Classification

- **Project Type:** IoT/Edge AI (primary) + Web Application (secondary dashboard)
- **Domain:** AI/ML Systems — real-time computer vision on edge hardware
- **Complexity:** Medium-High (real-time streaming, AI accuracy requirements, 24/7 uptime, multi-phase rollout)
- **Project Context:** Greenfield

## Success Criteria

### User Success

- Security team checks the dashboard **before** making any field call — dashboard is the first source of truth, not field reports
- Operators receive a Telegram alert and can act on it (redirect guests, radio entrance team) **before** a parking zone reaches 100% capacity
- Zero silent failures — team is never looking at stale occupancy data without knowing it
- Field staff parking walks become exception-only, not routine

### Business Success

- **Month 1 (MVP):** System runs accurately for 7+ consecutive days including at least one peak-hour or event period, validated by security team sign-off
- **Month 2–3:** Full 32-camera rollout live; operations leadership can identify parking zone issues from the dashboard without field confirmation
- **Month 6:** Measurable reduction in reactive field responses to parking congestion — team notices and acts on issues faster than the old radio-call workflow
- **Year 1:** All 30 locations live; parking management no longer requires dedicated field monitoring staff during normal operations

### Technical Success

- Vehicle detection accuracy ≥ 90% on live Hikvision footage in Nuanu conditions (tropical lighting, mixed vehicle types including motorcycles)
- Alert latency ≤ 60 seconds from threshold breach to Telegram delivery
- False alert rate < 5% of total alerts triggered
- System failure detection: watchdog alerts team within 2 minutes of stream loss, process crash, or container failure
- Counter debounce stable: no alert re-triggering from vehicle jitter within a zone; re-arms only after occupancy drops below 70%

### Measurable Outcomes

| Metric | MVP Target | 6-Month Target |
|--------|-----------|----------------|
| Detection accuracy | ≥ 90% | ≥ 92% (post-calibration) |
| Alert latency | ≤ 60s | ≤ 30s |
| False alert rate | < 5% | < 2% |
| Watchdog response | ≤ 2 min | ≤ 2 min |
| Consecutive uptime | 7 days | 30 days |
| Team adoption | Dashboard-first within 2 weeks | Field walks eliminated for routine ops |

## Product Scope

### MVP — Minimum Viable Product

- 2–4 cameras covering a single parking area
- Per-zone config: camera ID, zone name, total capacity, alert threshold (default 80%)
- Motion-triggered detection: Frigate NVR → YOLOv8 vehicle confirmation
- Live vehicle counter per zone with hysteresis/debounce
- Telegram alert on threshold breach; re-arms at 70%
- Web dashboard: live count, capacity %, zone status (OK / WARNING / FULL), system health indicator
- Watchdog process: Telegram alert on stream loss, process crash, or container down
- Docker Compose deployment on local GPU server

### Growth Features (Post-MVP)

- Expand to full 32 cameras across all Nuanu parking zones
- Multi-zone dashboard view with cross-zone occupancy summary
- Occupancy history and peak-hour trend charts
- Event mode: tighter thresholds, pre-event status briefing via Telegram
- Per-location deployment replication for additional sites (target: 10 of 30)
- Sub-stream RTSP support for lower-bandwidth inference

### Vision (Future)

- All 30 locations live with central management dashboard for operations leadership
- Cross-zone load balancing recommendations ("Lot B at 40% — redirect from Lot A")
- Integration with Nuanu guest/booking systems for predictive capacity modeling
- Automated entrance signage triggers based on occupancy state
- Fine-tuned YOLOv8 model on Nuanu-specific footage for accuracy beyond 95%

## User Journeys

### Journey 1: The Security Operator — Proactive Alert (Happy Path)

**Meet Wayan.** He's been on the Nuanu security team for two years. Before Parking AI, his mornings during events meant constant radio chatter: "Lot A getting full?" "Not sure, checking now." "Send someone to walk it." By the time the answer came back, the lot was already jammed and guests were circling.

Today, Wayan is monitoring the control room dashboard when his phone buzzes with a Telegram message: *"⚠️ Lot A — 82% capacity (41/50 spots). Threshold: 80%."* It's 10:47am, half an hour before the main event gates open.

He glances at the dashboard — the Lot A tile is yellow, count ticking up. He radios the entrance team immediately: "Start redirecting guests to Lot B, Lot A is nearly full." No walk needed. No guesswork. The alert landed 3 minutes before Lot A would have been gridlocked.

**New reality:** Wayan's job shifted from reactive fire-fighting to proactive traffic control. He checks the dashboard every 15 minutes instead of waiting for a radio call that may never come.

**Capabilities revealed:** Telegram alert delivery, threshold-triggered notification, real-time dashboard with zone status, configurable threshold per zone.

---

### Journey 2: The Security Operator — System Failure Recovery (Edge Case)

**It's 11:30pm.** Wayan's shift partner, Made, is on night duty. The dashboard shows Lot C at 60% — but he hasn't seen the counter move in 20 minutes, which is unusual for a Saturday night. Something feels off, but he can't tell if the lot is actually stable or if the AI stopped watching.

Then his phone buzzes: *"🔴 [SYSTEM] Camera stream lost: Lot C Camera 2. Last seen: 23:14. Investigating..."*

Made knows immediately: the system caught it before he did, and it's telling him not to trust Lot C's data. He switches to manual check for that zone only, calls the field team for a one-time report, and messages the infra team.

The watchdog auto-restart kicks in within 3 minutes. The dashboard Lot C tile shows a red "DEGRADED" badge until the stream recovers — it never silently pretends to be healthy.

**Capabilities revealed:** Watchdog process, stream-loss Telegram alert, degraded state badge on dashboard, stream auto-recovery with reconnect.

---

### Journey 3: The Infra Admin — Zone Setup (Configuration)

**Putu is on the infra team.** A new parking area just opened — Lot D, covered by 2 cameras, capacity 30 cars. He needs to add it to the system.

He edits the zone config file (YAML), adds the two camera RTSP URLs, sets `zone_name: "Lot D"`, `capacity: 30`, `threshold: 0.80`. He runs `docker compose up -d` to reload. Within 60 seconds, Lot D appears on the dashboard as a new tile — live count 0, green status.

He opens Frigate's motion zone editor to define which pixels of each camera frame count as "the parking area" — masking out the road and footpath in front. Saves config, watches a test vehicle drive through, sees the counter increment to 1 and back to 0. Done.

**Capabilities revealed:** YAML zone config (camera ID, zone name, capacity, threshold), Docker Compose service reload, Frigate zone masking, live dashboard auto-discovery of new zones.

---

### Journey 4: Operations Leadership — Weekly Visibility

**Ketut is Nuanu's Operations Manager.** She doesn't operate the system day-to-day, but she's responsible for infrastructure planning. On Monday morning she opens the dashboard on her laptop.

She sees a summary view: all zones, their weekend peak occupancy, and how long each stayed above 80%. Lot A hit 95% twice on Saturday between 11am–1pm. Lot B never exceeded 60%. This tells her two things: Lot A needs either expansion or better pre-event routing, and Lot B has slack capacity that should be communicated to guests arriving for Saturday events.

She exports the week's peak occupancy report for the board meeting. No one had to compile it manually.

**Capabilities revealed:** Historical occupancy data, peak-hour trends, per-zone occupancy timeline, report export (post-MVP growth feature).

---

### Journey Requirements Summary

| Journey | Core Capabilities Required |
|---------|--------------------------|
| Security — Alert | Telegram bot, threshold alert, re-arm logic, real-time dashboard |
| Security — Recovery | Watchdog, stream-loss detection, degraded badge, auto-reconnect |
| Infra Admin — Setup | YAML zone config, Docker Compose reload, Frigate zone masking, dashboard auto-discovery |
| Ops Leadership — Visibility | Historical data storage, peak trend view, report export *(growth)* |

## Domain-Specific Requirements

### Privacy & Data Handling

- **CCTV footage stays on-prem** — video streams are never transmitted off the local network or stored in cloud services. Hard architectural constraint.
- **No PII captured** — the system counts vehicles, not people. No face detection, no license plates (ALPR excluded from scope). This keeps the system outside personal data regulation scope (GDPR, Indonesia's PDP Law).
- **Footage retention policy** — system does not record video by default (Frigate records are optional). Only occupancy counts and alert logs are stored. Retention policy for logs: TBD by Nuanu infra team.

### AI/ML Accuracy Constraints

- **Production validation required** — YOLOv8 pre-trained weights must be validated on live Nuanu footage before any zone goes live. Benchmark accuracy ≠ field accuracy (tropical lighting, IR night mode, small motorcycle bounding boxes).
- **Confidence threshold gate** — only detections with confidence ≥ 0.65 (adjustable) are counted as vehicles. Lower threshold increases false positives; higher threshold risks missed vehicles.
- **Vehicle class scope** — car, truck, motorcycle, bus are counted. Pedestrians, bicycles, and animals are explicitly excluded. Per-zone class config supported (motorbike-only lots may need different class weights).
- **Model update path** — if production accuracy falls below 90%, the path is: collect Nuanu-specific training images → fine-tune YOLOv8 → validate on held-out set → hot-swap model weights via Docker volume mount.

### Security & Network

- **Local network only** — processing server and cameras are on the same LAN. Dashboard is not internet-exposed by default; access via local network or VPN only.
- **RTSP credential management** — camera passwords stored in `.env` file, injected into Docker containers via environment variables. `.env` excluded from version control. Rotation procedure documented for infra team.
- **Dashboard authentication** — login required (username/password). Dashboard not open to unauthenticated local network access.
- **No remote code execution surface** — system has no public API. Only outbound connections: Telegram bot API (HTTPS).

### Reliability & Operational Constraints

- **24/7 unattended operation** — system must self-recover from transient failures (stream drop, process crash) without manual intervention. Docker restart policies + watchdog handle this.
- **Graceful degradation** — if a single camera stream fails, only that zone is marked DEGRADED. Other zones continue operating normally.
- **Non-engineer operators** — the security team is not technical. Recovery procedures must be documented in plain language with no CLI required for day-to-day operations.
- **Tropical environment** — server room conditions in Bali (heat, humidity, occasional power fluctuations). Recommend UPS on the processing server and temperature monitoring as operational baseline.

### Integration Constraints

- **Telegram Bot API** — only external dependency. Requires outbound internet access from the server for alert delivery. Behavior on internet loss: TBD (queue and flush vs. silent fail).
- **Frigate MQTT** — internal message bus between Frigate and the Python counter service. Embedded Mosquitto broker in Docker Compose; no external broker required.
- **No ERP/booking system integration in MVP** — explicitly deferred to Year 2+.

## Innovation & Novel Patterns

### Detected Innovation Areas

**1. Motion-Gated AI Inference Pipeline**
The core architecture — Frigate NVR motion detection as a compute-efficient gate for YOLOv8 vehicle confirmation — is a novel combination in the parking occupancy monitoring space. Existing solutions split into two camps: continuous YOLO streaming (high GPU cost, suitable for real-time dashboards) or interval snapshots (low cost, risks missing transient events). The hybrid approach achieves the accuracy profile of continuous streaming at a fraction of the compute cost by only running inference when motion warrants it. This is particularly valuable at scale: 32 cameras with continuous YOLO would saturate a mid-range GPU; the same cameras with motion-gating can run comfortably with GPU headroom to spare.

**2. Operationally Honest Edge AI Design**
Most edge AI deployments fail silently — a crashed process or dropped stream continues to serve stale readings until a human notices. This system inverts that assumption: the watchdog process is a first-class component, not an afterthought. Stream loss, inference failure, and container crashes all surface immediately as Telegram alerts and dashboard DEGRADED badges. For a security team that trusts live data to make operational decisions, this is a meaningful safety property. It is rare in edge AI deployments of this scale.

**3. Gap in Open-Source Tooling**
No existing open-source project combines: Frigate NVR + YOLOv8 vehicle counting + per-zone state machine + Telegram alert delivery + multi-location scaling architecture. Each component exists in isolation; the integration layer is original work.

### Market Context & Competitive Landscape

- Commercial parking management systems (ParkWhiz, Genetec, Axis) require proprietary hardware, cloud subscriptions, or dedicated cameras — none fit Nuanu's constraint of reusing existing Hikvision infrastructure with zero external dependencies.
- Academic parking detection projects (PKSpace, Roboflow models) are single-lot, CPU-only, and unmaintained.
- Frigate community deployments focus on home security, not occupancy counting at commercial scale.
- The addressable gap: on-prem, multi-camera, multi-location parking occupancy with open-source components — no maintained solution exists.

### Validation Approach

- **MVP accuracy gate:** Run YOLOv8 on live Nuanu footage for 7 days; compare counter output against manual ground truth counts during peak periods. Target ≥ 90%.
- **Hybrid vs. continuous comparison:** Log motion-trigger events vs. vehicle-confirmed events during MVP. Measure false positive suppression rate — validates that the motion gate is actually doing work.
- **Watchdog validation:** Simulate stream loss (unplug camera or block RTSP) and measure time-to-Telegram-alert. Target ≤ 2 minutes.

### Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Frigate motion detection over-triggers (too many wakes) | Tune Frigate motion sensitivity and mask regions (roads, trees) during zone setup |
| YOLOv8 accuracy below 90% on Nuanu footage | Fine-tune on Nuanu-collected images; lower confidence threshold as fallback |
| GPU saturates at 32 cameras | Use sub-stream RTSP (lower resolution) for inference; reserve main stream for recording |
| Frigate not designed for 30-location scale | Deploy one Frigate instance per location; central coordination layer aggregates counts |

## Functional Requirements

### Alerting

**FR-001:** Operators can receive a Telegram alert when a zone's occupancy reaches its configured threshold.

**FR-002:** The system re-arms a zone's alert after occupancy drops below the re-arm threshold (default: 70%), enabling future alerts without manual reset.

**FR-003:** Operators can receive a Telegram alert when a camera stream is lost, an inference process crashes, or a service container fails.

### Dashboard

**FR-004:** Operators can view the current vehicle count and occupancy percentage per zone on a web dashboard.

**FR-005:** Operators can see a zone status indicator (OK / WARNING / FULL) for each zone on the dashboard.

**FR-006:** Operators can see a system health indicator on the dashboard reflecting the current stream and service status per zone, including a DEGRADED badge when a zone has lost stream connectivity.

**FR-007:** Operators can access the dashboard only after authenticating with valid credentials.

### Configuration

**FR-008:** Infrastructure administrators can configure each zone with a camera reference, zone name, total capacity, and occupancy alert threshold using a configuration file.

**FR-009:** Infrastructure administrators can apply zone configuration changes by restarting the service stack without modifying application code.

**FR-010:** Infrastructure administrators can define which region of each camera frame constitutes the monitored parking zone, excluding roads, footpaths, and other non-parking areas.

### Detection

**FR-011:** The system counts vehicles per zone using a two-stage process: motion detection gates AI inference, which confirms vehicle presence before incrementing the zone counter.

**FR-012:** The system counts only vehicles in the configured classes (car, truck, motorcycle, bus); pedestrians, bicycles, and animals are excluded.

**FR-013:** The system applies debounce logic to zone counters to prevent alert re-triggering from transient vehicle movement within a zone.

### Recovery

**FR-014:** The system automatically attempts to reconnect a dropped camera stream without operator intervention.

**FR-015:** A zone with a lost or degraded stream displays a DEGRADED status on the dashboard; all other zones continue operating independently.

### Growth (Post-MVP)

**FR-016:** *(Post-MVP)* Operations leadership can view historical occupancy data and peak-hour trend charts per zone.

**FR-017:** *(Post-MVP)* Operations leadership can export a per-zone occupancy report covering a specified time period.

## Non-Functional Requirements

### Performance

**NFR-001:** The system shall deliver a Telegram occupancy alert within 60 seconds of a zone crossing its configured threshold, measured from the threshold-crossing event to confirmed Telegram message receipt, under normal operating conditions.

**NFR-002:** The system shall deliver a Telegram system-failure alert within 2 minutes of a stream loss, process crash, or container failure, measured from the failure event to confirmed Telegram message receipt.

### Accuracy

**NFR-003:** Vehicle detection accuracy shall be ≥ 90% on live Hikvision footage under Nuanu conditions (tropical lighting, IR night mode, mixed vehicle types including motorcycles), validated by comparison against manual ground-truth counts during the 7-day MVP validation period.

**NFR-004:** The false alert rate shall be < 5% of total alerts triggered, measured over the MVP validation period.

**NFR-005:** The vehicle detection confidence threshold shall be configurable per zone (default: ≥ 0.65); only detections meeting the configured threshold are counted as vehicles.

### Reliability

**NFR-006:** The system shall achieve ≥ 7 consecutive days of uninterrupted operation during the MVP validation period, as confirmed by continuous uptime monitoring.

**NFR-007:** The system shall self-recover from transient stream drops and process crashes without manual operator intervention.

**NFR-008:** Failure of any single camera stream or zone shall not degrade the operation of other active zones.

### Security

**NFR-009:** Video stream data shall not leave the local network; all AI inference and data storage shall occur on-premises.

**NFR-010:** Dashboard access shall require authentication; unauthenticated requests shall be rejected.

**NFR-011:** Camera credentials shall not be stored in version-controlled source files.

### Scalability

**NFR-012:** The system architecture shall support expansion to 30+ locations by replicating the service stack per site, without architectural redesign required for individual single-location deployments.
