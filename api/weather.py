"""Short-range rain forecast from Open-Meteo (no API key), cached to stay polite."""
import time
from datetime import datetime, timedelta
import requests

_cache = {}


def rain_next_hours(lat, lng, hours=12):
    """Expected rainfall in mm over the next `hours`, or None if the forecast is unavailable."""
    if lat is None or lng is None:
        return None
    key = (round(float(lat), 2), round(float(lng), 2), hours)
    hit = _cache.get(key)
    if hit and time.time() < hit[0]:
        return hit[1]
    total, ttl = None, 300
    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=4, params={
            "latitude": float(lat), "longitude": float(lng), "hourly": "precipitation",
            "forecast_days": 2, "timezone": "auto"})
        j = r.json()
        times, prec = j["hourly"]["time"], j["hourly"]["precipitation"]
        local_now = datetime.utcnow() + timedelta(seconds=j.get("utc_offset_seconds", 0))
        start = local_now.replace(minute=0, second=0, microsecond=0)
        idx = next(i for i, t in enumerate(times) if datetime.fromisoformat(t) >= start)
        total, ttl = round(sum((p or 0.0) for p in prec[idx:idx + hours]), 1), 1800
    except Exception:
        pass
    _cache[key] = (time.time() + ttl, total)
    return total
