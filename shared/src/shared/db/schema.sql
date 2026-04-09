-- nuanu-parking-ai SQLite schema
-- Owned by: dashboard service
-- Applied at: dashboard service startup via aiosqlite
-- All timestamps are ISO 8601 UTC (e.g. "2026-04-09T14:32:00Z")

CREATE TABLE IF NOT EXISTS alert_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zone_id       TEXT    NOT NULL,
    alert_type    TEXT    NOT NULL,  -- "threshold_breach", "stream_loss", "container_down"
    occupancy_pct REAL    NOT NULL,  -- 0.0–1.0
    vehicle_count INTEGER NOT NULL,
    created_at    TEXT    NOT NULL   -- ISO 8601 UTC
);

CREATE TABLE IF NOT EXISTS system_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    service    TEXT NOT NULL,        -- "counter", "watchdog", "dashboard", "frigate"
    event_type TEXT NOT NULL,        -- "startup", "shutdown", "stream_loss", "stream_recovery"
    message    TEXT,
    created_at TEXT NOT NULL         -- ISO 8601 UTC
);

-- Index for dashboard history queries
CREATE INDEX IF NOT EXISTS idx_alert_events_zone_id ON alert_events (zone_id);
CREATE INDEX IF NOT EXISTS idx_alert_events_created_at ON alert_events (created_at);
