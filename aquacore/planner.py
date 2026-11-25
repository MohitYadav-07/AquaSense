"""Irrigation planning: growth stages, rain-aware watering decisions."""
from datetime import date, datetime

WETTED_FRACTION = 0.15   # share of the plot wetted by drip emitters
EFFICIENCY = 0.9         # drip application efficiency
RAIN_EFFECTIVE = 0.8     # share of rainfall that enters the root zone (rest is runoff)
MIN_RUN_MIN = 10
MAX_RUN_HARD = 240       # absolute safety cap for any single run, minutes

# Days after planting at which: establishment ends, vegetative ends, flowering ends.
# Agronomic starting points; validate against local advice.
STAGE_ENDS = {
    "Millet": (15, 45, 70), "Tomato": (20, 50, 90), "Groundnut": (20, 50, 90), "Wheat": (25, 70, 100),
    "Maize": (20, 55, 85), "Rice": (20, 60, 90), "Cotton": (30, 80, 130), "Sugarcane": (60, 180, 300),
    "Other": (20, 50, 80),
}
# (name, change to watering threshold, change to refill target) in moisture %-points
STAGES = [("Establishment", 3.0, 2.0), ("Vegetative", 0.0, 0.0), ("Flowering / fruiting", 2.0, 2.0), ("Maturity", -4.0, -3.0)]


def _as_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()


def stage_for(crop, planted_on, today=None):
    today = today or date.today()
    p = _as_date(planted_on)
    if p is None:
        return {"name": "Not set", "low_adj": 0.0, "high_adj": 0.0, "day": None}
    day = (today - p).days
    if day < 0:
        return {"name": "Not planted yet", "low_adj": 0.0, "high_adj": 0.0, "day": day}
    ends = STAGE_ENDS.get(crop, STAGE_ENDS["Other"])
    idx = 3
    for i, e in enumerate(ends):
        if day < e:
            idx = i
            break
    name, lo, hi = STAGES[idx]
    return {"name": name, "low_adj": lo, "high_adj": hi, "day": day}


def effective_thresholds(field, today=None):
    """Field thresholds adjusted for the crop's current growth stage -> (low, high, stage)."""
    stage = stage_for(field.get("crop"), field.get("planted_on"), today)
    low = min(90.0, max(5.0, float(field["moisture_low"]) + stage["low_adj"]))
    high = min(100.0, max(low + 3.0, float(field["moisture_high"]) + stage["high_adj"]))
    return low, high, stage


def plan_irrigation(field, predicted, rain_mm=0.0, low=None, high=None):
    """Decide what to do given a 6 h moisture forecast and expected rain (mm over the same window).

    Returns a dict with action in {"none", "skip_rain", "irrigate"}.
    """
    low = float(field["moisture_low"]) if low is None else low
    high = float(field["moisture_high"]) if high is None else high
    root = float(field["root_depth_mm"])
    rain_mm = float(rain_mm or 0.0)
    if predicted >= low:
        return {"action": "none", "rain_mm": rain_mm}
    adjusted = predicted + rain_mm * RAIN_EFFECTIVE / root * 100.0
    if adjusted >= low:
        return {"action": "skip_rain", "rain_mm": rain_mm, "adjusted": adjusted}
    deficit_mm = (high - adjusted) / 100.0 * root
    wetted_m2 = float(field["area_ha"]) * 10000.0 * WETTED_FRACTION
    volume = deficit_mm * wetted_m2 / EFFICIENCY          # 1 mm over 1 m2 = 1 L
    flow = float(field["flow_lph"])
    minutes = max(MIN_RUN_MIN, int(round(volume / flow * 60.0)))
    cap = min(int(field.get("max_run_min") or 180), MAX_RUN_HARD)
    capped = minutes > cap
    if capped:
        minutes = cap
        volume = minutes * flow / 60.0
    return {"action": "irrigate", "volume_l": int(volume), "minutes": minutes, "capped": capped,
            "rain_mm": rain_mm, "adjusted": adjusted}
