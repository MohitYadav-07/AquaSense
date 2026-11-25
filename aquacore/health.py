"""Sensor health assessment from recent readings."""
from datetime import datetime, timedelta

LABELS = {
    "no_data": "No readings received yet",
    "offline": "No reading for over 3 hours",
    "stuck": "Reading is not changing, probe may be stuck or disconnected",
    "jump": "Reading jumped suddenly, check the probe and wiring",
    "low_battery": "Battery below 20%",
}


def assess(readings, now=None, offline_hours=3):
    """readings: newest first, dicts with recorded_at, soil_moisture, battery."""
    now = now or datetime.now()
    if not readings:
        return {"status": "offline", "issues": ["no_data"], "last_seen": None}
    issues = []
    last = readings[0]["recorded_at"]
    if now - last > timedelta(hours=offline_hours):
        issues.append("offline")
    recent = [float(r["soil_moisture"]) for r in readings[:12]]
    if len(recent) >= 8 and max(recent) - min(recent) < 0.05:
        issues.append("stuck")
    for a, b in zip(recent, recent[1:]):
        if abs(a - b) > 25:
            issues.append("jump")
            break
    bat = readings[0].get("battery")
    if bat is not None and float(bat) < 20:
        issues.append("low_battery")
    status = "offline" if "offline" in issues else ("warning" if issues else "ok")
    return {"status": status, "issues": issues, "last_seen": last}
