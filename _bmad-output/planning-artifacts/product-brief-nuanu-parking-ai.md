---
title: "Product Brief: Nuanu Parking AI"
status: "complete"
created: "2026-04-08"
updated: "2026-04-08"
inputs: ["user-discovery-session", "web-research-frigate-yolo-hikvision"]
---

# Product Brief: Nuanu Parking AI

## Executive Summary

Nuanu is a growing creative township in Bali managing increasing vehicle traffic across multiple areas. Today, the security and infrastructure team has no automated visibility into parking occupancy — they rely on field staff walking lots and calling in reports over the phone or radio. By the time a report reaches the team, the situation may have already changed.

Nuanu Parking AI is a locally-deployed, AI-powered parking occupancy monitoring system that processes live CCTV feeds to count vehicles per area in real time. When any zone approaches capacity (default: 80%), it automatically alerts the monitoring team via a web dashboard and Telegram — enabling proactive, data-driven guest management instead of reactive crisis response.

The system is designed to run entirely on-premises on existing CCTV infrastructure, with no cloud dependency. It starts with 2–4 cameras, validates accuracy, then scales to 30+ locations. No new cameras. No subscriptions. No operational overhaul required.

## The Problem

The Nuanu security and infrastructure team manages parking flow across multiple zones with no real-time data. Current operations depend on:

- **Field staff physically walking parking areas** and reporting back via phone or radio
- **Manual eyeballing of CCTV feeds**, requiring staff to switch between views on a monitor
- **Reactive communication** — by the time a zone is reported full, queues and confusion have already built at the entrance

The consequences are felt daily: guests arrive to find full lots, congestion builds at decision points, and the operations team loses the window to redirect traffic before the situation degrades. During events and peak hours, the gap is acute. Beyond the guest experience cost, field staff spend significant time on parking walks that could be redirected to higher-value tasks the moment real-time data exists.

There is no threshold alert, no live count, and no single source of truth.

## The Solution

Nuanu Parking AI adds an AI processing layer on top of the existing 32-camera Hikvision CCTV network, requiring no hardware changes:

1. **Monitors RTSP streams** from fixed-angle cameras covering defined parking zones
2. **Uses motion detection (Frigate NVR)** to wake the AI only when activity is detected — conserving GPU resources on idle lots
3. **Confirms vehicle presence** using AI vision (YOLOv8) with high-confidence filtering — rejecting shadows, pedestrians, and animals
4. **Maintains a live counter** per zone: vehicles present vs. configured capacity
5. **Alerts the team** via Telegram and a live dashboard when a zone crosses the threshold (default 80%, configurable per zone)
6. **Self-monitors** with a health watchdog — if a stream drops or the AI process fails, the team is notified immediately rather than silently receiving stale data

## Technical Approach

| Layer | Technology |
|-------|-----------|
| Stream ingestion | FFmpeg + Hikvision RTSP with auto-reconnect |
| Motion trigger | Frigate NVR (Docker, local GPU) |
| Vehicle confirmation | YOLOv8 via Python — high-confidence vehicle class only |
| Counter logic | Per-zone state machine with hysteresis/debounce |
| Alert delivery | `python-telegram-bot` + web dashboard |
| Health monitoring | Watchdog process with Telegram alerts on stream loss or system failure |
| Language | Python (primary) |
| Deployment | Docker Compose, single GPU server |

## What Makes This Different

- **On-premise by design** — video stays on-site, no cloud subscription, no latency to a remote API
- **Accuracy-first trigger logic** — motion wakes the system, AI confirms. Dramatically reduces false positives vs. continuous streaming, at a fraction of the GPU cost
- **Built to scale** — architecture supports expansion from 4 cameras to 30+ locations without redesign
- **Proactive, not reactive** — alert arrives at 80% capacity, not 100%. The team has time to act before the lot is full
- **Operationally honest** — the system tells you when it's not seeing clearly (camera offline, stream degraded) rather than reporting false confidence

## Who This Serves

**Primary: Security & Infrastructure Team**
The daily operators currently managing parking by phone and radio. Success for them: know when a lot is filling up before it's full, get the alert on Telegram, redirect incoming guests without leaving the control room. Field parking walks become the exception, not the routine.

**Secondary: Nuanu Operations Leadership**
Access to occupancy dashboards and historical trends to inform decisions about parking infrastructure, event planning, and resource allocation.

## Success Criteria

| Metric | Target |
|--------|--------|
| Vehicle detection accuracy | ≥ 90% on production Hikvision footage (validated on live cameras, not benchmark datasets) |
| Alert latency | ≤ 60 seconds from threshold breach to Telegram delivery |
| False alert rate | < 5% of alerts triggered by non-vehicle events |
| System uptime | Watchdog-enforced auto-recovery; team alerted within 2 min of stream/process failure |
| MVP deployment | 2–4 cameras live, accurate, alerting — within 1 month |
| Team adoption | Security team using dashboard + Telegram as primary parking source within 2 weeks of launch |

## Scope

**MVP (Month 1):**
- 2–4 cameras, one parking area
- Zone definition (config-based: mark capacity per camera zone)
- Live vehicle counter per zone
- Telegram alert at configurable threshold (default 80%)
- Basic web dashboard: live count, capacity %, zone status, system health indicator

**Out of scope for MVP:**
- License plate recognition (ALPR)
- Guest booking system integration
- Dedicated mobile app (Telegram handles mobile alerts)
- Multi-location central management console
- Historical analytics and reporting
- Entrance signage control

## Roadmap

**Month 2–3:** Expand to full 32 cameras across Nuanu's primary parking zones. Multi-zone dashboard with cross-zone occupancy view.

**Month 4–6:** Roll out to additional locations (target: 10 of 30). Introduce occupancy history and peak-hour trend reports.

**Year 1:** All 30 locations live. Central management dashboard for operations leadership. Event-mode configuration with tighter thresholds and pre-event status briefing.

**Year 2+:** Integration with guest/booking systems for predictive capacity modeling. Cross-zone load balancing recommendations ("Lot B is at 40% — redirect from Lot A"). Potential for automated entrance signage triggers.
