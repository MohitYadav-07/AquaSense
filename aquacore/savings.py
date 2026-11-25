"""Estimate water saved versus a conventional fixed-schedule baseline."""
from .planner import EFFICIENCY, WETTED_FRACTION

BASELINE_MM_PER_DAY = 4.0   # typical fixed drip schedule; adjust per region/crop
TANKER_LITRES = 10000


def baseline_litres(area_ha, days, mm_per_day=BASELINE_MM_PER_DAY):
    return float(area_ha) * 10000.0 * WETTED_FRACTION * mm_per_day * days / EFFICIENCY


def summarize(baseline_l, actual_l):
    saved = baseline_l - actual_l
    pct = (saved / baseline_l * 100.0) if baseline_l > 0 else 0.0
    return {"baseline_l": int(baseline_l), "actual_l": int(actual_l), "saved_l": int(saved),
            "saved_pct": round(pct, 1), "tankers": round(saved / TANKER_LITRES, 1)}
