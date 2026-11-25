"""Safety-first decision for the irrigation valve controller."""
from .planner import MAX_RUN_HARD


def decide(valve_mode, moisture, moisture_high, max_run_min, manual_cmd, due_schedule):
    """What should the valve do right now?

    manual_cmd / due_schedule are dicts or None. Returns
    {"action": "open"|"close"|"idle", "minutes", "source", "ref", "skip_reason"}.
    """
    cap = min(int(max_run_min or 180), MAX_RUN_HARD)
    idle = {"action": "idle", "minutes": 0, "source": None, "ref": None, "skip_reason": None}

    if manual_cmd and manual_cmd.get("action") == "close":
        return dict(idle, action="close", source="manual", ref="c%d" % manual_cmd["id"])
    if valve_mode == "off":
        return dict(idle, action="close", source="mode_off")
    if manual_cmd and manual_cmd.get("action") == "open":
        mins = max(1, min(int(manual_cmd.get("duration_min") or 30), cap))
        return dict(idle, action="open", minutes=mins, source="manual", ref="c%d" % manual_cmd["id"])
    if due_schedule:
        if moisture is not None and float(moisture) >= float(moisture_high):
            return dict(idle, skip_reason="Soil already at target (%.1f%%)" % float(moisture),
                        ref="s%d" % due_schedule["id"])
        mins = max(1, min(int(due_schedule["duration_min"]), cap))
        return dict(idle, action="open", minutes=mins, source="schedule", ref="s%d" % due_schedule["id"])
    return idle
