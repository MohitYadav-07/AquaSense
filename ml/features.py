"""Shared feature engineering so training and serving never drift apart."""
import math
import numpy as np

FEATURES = ["moisture", "soil_temp", "air_temp", "humidity",
            "hour_sin", "hour_cos", "moisture_delta"]


def build_row(moisture, soil_temp, air_temp, humidity, hour, prev_moisture=None):
    delta = 0.0 if prev_moisture is None else moisture - prev_moisture
    return [moisture, soil_temp, air_temp, humidity,
            math.sin(2 * math.pi * hour / 24), math.cos(2 * math.pi * hour / 24), delta]


def clean_reading(r):
    """Preprocess one raw sensor payload. Returns a dict or raises ValueError."""
    ranges = {"soil_moisture": (0, 100), "soil_temp": (-5, 70),
              "air_temp": (-10, 60), "humidity": (0, 100)}
    out = {}
    for key, (lo, hi) in ranges.items():
        v = r.get(key)
        if v is None:
            if key == "soil_moisture":
                raise ValueError("soil_moisture is required")
            out[key] = None
            continue
        v = float(v)
        if not math.isfinite(v):
            raise ValueError(key + " must be a finite number")
        out[key] = float(np.clip(v, lo, hi))
    if r.get("battery") is None:
        out["battery"] = None
    else:
        battery = float(r["battery"])
        if not math.isfinite(battery):
            raise ValueError("battery must be a finite number")
        out["battery"] = float(np.clip(battery, 0, 100))
    return out
