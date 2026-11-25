"""Read-side calculations for the dashboard."""
from bisect import bisect_left
from datetime import datetime, timedelta

from aquacore import health, planner, savings
from django.conf import settings

from .models import IrrigationSchedule, SensorReading


def field_dict(f):
    """Plain dict view of a Field for the shared planner."""
    return {"crop": f.crop, "planted_on": f.planted_on, "moisture_low": f.moisture_low, "moisture_high": f.moisture_high,
            "root_depth_mm": f.root_depth_mm, "area_ha": f.area_ha, "flow_lph": f.flow_lph, "max_run_min": f.max_run_min}


def forecast_accuracy(field_id, days=7, now=None):
    """Compare each stored 6 h prediction with the reading that actually followed."""
    now = now or datetime.now()
    since = now - timedelta(days=days)
    rows = list(SensorReading.objects.filter(field_id=field_id, recorded_at__gte=since - timedelta(hours=1))
                .order_by("recorded_at").values_list("recorded_at", "soil_moisture", "predicted_6h"))
    times = [r[0] for r in rows]
    errs = []
    for t, _m, pred in rows:
        if pred is None or t < since:
            continue
        target = t + timedelta(hours=6)
        j = bisect_left(times, target)
        near = [k for k in (j - 1, j) if 0 <= k < len(rows) and abs((times[k] - target).total_seconds()) <= 1500]
        if near:
            k = min(near, key=lambda i: abs((times[i] - target).total_seconds()))
            errs.append(abs(float(pred) - float(rows[k][1])))
    if len(errs) < 3:
        return None
    return {"mae": round(sum(errs) / len(errs), 2), "n": len(errs)}


def field_health(field, now=None):
    rows = [{"recorded_at": r.recorded_at, "soil_moisture": r.soil_moisture, "battery": r.battery}
            for r in field.readings.all()[:12]]
    res = health.assess(rows, now)
    res["labels"] = [health.LABELS[i] for i in res["issues"]]
    return res


def field_savings(field, days=30, now=None):
    now = now or datetime.now()
    first = field.readings.order_by("recorded_at").values_list("recorded_at", flat=True).first()
    if first is None:
        return None
    active = max(1, min(days, (now - first).days + 1))
    since = now - timedelta(days=active)
    used = sum(s.volume_l for s in IrrigationSchedule.objects.filter(
        field=field, status__in=("done", "running"), scheduled_for__gte=since, scheduled_for__lte=now))
    out = savings.summarize(savings.baseline_litres(field.area_ha, active, settings.BASELINE_MM_PER_DAY), used)
    out.update(days=active, field=field)
    return out


def daily_savings_series(fields, days=30, now=None):
    """Cumulative litres per day across fields: conventional baseline vs. AquaSense."""
    now = now or datetime.now()
    today = now.date()
    labels = [(today - timedelta(days=days - 1 - i)) for i in range(days)]
    base_daily, used_daily = [0.0] * days, [0.0] * days
    for f in fields:
        first = f.readings.order_by("recorded_at").values_list("recorded_at", flat=True).first()
        if first is None:
            continue
        per_day = savings.baseline_litres(f.area_ha, 1, settings.BASELINE_MM_PER_DAY)
        for i, d in enumerate(labels):
            if d >= first.date():
                base_daily[i] += per_day
        for s in IrrigationSchedule.objects.filter(field=f, status__in=("done", "running"),
                                                   scheduled_for__date__gte=labels[0], scheduled_for__date__lte=today):
            used_daily[(s.scheduled_for.date() - labels[0]).days] += s.volume_l
    cb, cu, bsum, usum = [], [], 0.0, 0.0
    for b, u in zip(base_daily, used_daily):
        bsum += b; usum += u
        cb.append(int(bsum)); cu.append(int(usum))
    return {"labels": [d.strftime("%d %b") for d in labels], "baseline": cb, "actual": cu}
