import csv
import json
import re
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import requests
from aquacore import planner
from aquacore.i18n import LANGS
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services
from .access import visible_fields
from .models import Alert, Field, IrrigationSchedule, Notification, Sensor, SensorReading, ValveCommand
from .pdfreport import build_pdf

CROPS = ["Millet", "Tomato", "Groundnut", "Wheat", "Maize", "Rice", "Cotton", "Sugarcane", "Other"]


# ---------- helpers ----------
def _forecast(field_id):
    """Ask the Flask ML service for a live forecast; fail soft so the page always loads."""
    try:
        r = requests.get("%s/api/predict/%d" % (settings.API_URL, field_id), headers={"X-API-Key": settings.API_KEY}, timeout=3)
        return r.json() if r.ok else None
    except (requests.RequestException, ValueError):
        return None


def _boundary(field):
    try:
        b = json.loads(field.boundary) if field.boundary else None
        return b if isinstance(b, list) and len(b) >= 3 else None
    except ValueError:
        return None


def _geo(field):
    if field.latitude is None or field.longitude is None:
        return None
    return {"lat": float(field.latitude), "lng": float(field.longitude), "boundary": _boundary(field)}


def parse_field_form(p):
    """Validate the add/edit field form. Raises ValueError on bad input."""
    try:
        d = {
            "name": p["name"].strip()[:80], "crop": p["crop"].strip()[:60],
            "moisture_low": Decimal(p["moisture_low"]), "moisture_high": Decimal(p["moisture_high"]),
            "root_depth_mm": int(p["root_depth_mm"]), "flow_lph": int(p["flow_lph"]),
            "max_run_min": int(p.get("max_run_min") or 180), "language": p.get("language", "en"),
            "contact_phone": (p.get("contact_phone") or "").strip() or None,
        }
        planted = (p.get("planted_on") or "").strip()
        d["planted_on"] = datetime.strptime(planted, "%Y-%m-%d").date() if planted else None
    except (KeyError, InvalidOperation, ValueError):
        raise ValueError("Check the field details and try again.")
    if not d["name"] or not d["crop"] or not (0 <= d["moisture_low"] < d["moisture_high"] <= 100) or d["root_depth_mm"] < 50 \
            or d["flow_lph"] < 100 or not (5 <= d["max_run_min"] <= 240) or d["language"] not in dict(LANGS) \
            or (d["contact_phone"] and not re.fullmatch(r"\+?[0-9]{8,15}", d["contact_phone"])):
        raise ValueError("Check the field details and try again.")
    return d


# ---------- pages ----------
def dashboard(request, field_id=None):
    fields = visible_fields(request)
    field = get_object_or_404(fields, pk=field_id) if field_id else fields.first()
    if field is None:
        return render(request, "farm/no_fields.html", {"page": "dashboard"})
    latest = field.readings.first()
    low, high, stage = planner.effective_thresholds(services.field_dict(field))
    status = None
    if latest:
        m = float(latest.soil_moisture)
        status = "dry" if m < low else ("wet" if m > high else "ok")
    ctx = {
        "field": field, "latest": latest, "forecast": _forecast(field.id), "low": round(low, 1), "high": round(high, 1),
        "stage": stage, "status": status, "accuracy": services.forecast_accuracy(field.id),
        "next_run": field.schedules.filter(status__in=("pending", "running")).first(),
        "alerts": field.alerts.filter(is_read=False)[:3], "sensor": field.sensors.first(), "geo": _geo(field),
        "health": services.field_health(field), "page": "dashboard",
    }
    return render(request, "farm/dashboard.html", ctx)


def series(request, field_id):
    field = get_object_or_404(visible_fields(request), pk=field_id)
    rows = list(SensorReading.objects.filter(field=field)[:96])[::-1]
    return JsonResponse({
        "labels": [r.recorded_at.strftime("%d %b %H:%M") for r in rows],
        "moisture": [float(r.soil_moisture) for r in rows],
        "predicted": [float(r.predicted_6h) if r.predicted_6h is not None else None for r in rows],
    })


def schedule(request):
    fields = visible_fields(request)
    if request.method == "POST":
        act = request.POST.get("action")
        if act == "add":
            try:
                when = datetime.strptime(request.POST["when"], "%Y-%m-%dT%H:%M")
                mins = max(5, min(int(request.POST["minutes"]), 240))
            except (KeyError, ValueError):
                return HttpResponseBadRequest("Check the date and minutes.")
            f = get_object_or_404(fields, pk=request.POST.get("field"))
            IrrigationSchedule.objects.create(
                field=f, scheduled_for=when, duration_min=mins, volume_l=int(mins / 60 * f.flow_lph),
                source="manual", status="pending", reason="Added by farmer")
        elif act in ("done", "skipped"):
            IrrigationSchedule.objects.filter(pk=request.POST.get("id"), field__in=fields).update(status=act)
        return redirect("schedule")
    mine = IrrigationSchedule.objects.filter(field__in=fields).select_related("field")
    return render(request, "farm/schedule.html", {
        "pending": mine.filter(status__in=("pending", "running")),
        "history": mine.exclude(status__in=("pending", "running")).order_by("-scheduled_for")[:15],
        "fields": fields, "default_when": (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"), "page": "schedule",
    })


def alerts(request):
    fields = visible_fields(request)
    if request.method == "POST":
        Alert.objects.filter(field__in=fields, is_read=False).update(is_read=True)
        return redirect("alerts")
    return render(request, "farm/alerts.html", {
        "items": Alert.objects.filter(field__in=fields).select_related("field")[:50],
        "messages_sent": Notification.objects.filter(field__in=fields).select_related("field")[:10], "page": "alerts"})


# ---------- explore / add field ----------
def explore(request):
    pins = [{"id": f.id, "name": f.name, "crop": f.crop, "location": f.location,
             "lat": float(f.latitude), "lng": float(f.longitude), "url": "/field/%d/" % f.id, "boundary": _boundary(f)}
            for f in visible_fields(request).exclude(latitude__isnull=True).exclude(longitude__isnull=True)]
    return render(request, "farm/explore.html", {"pins": pins, "today": date.today().isoformat(), "page": "explore"})


@require_POST
def field_create(request):
    """Create a field (plus its sensor code and device key) from the area selected on the Explore map."""
    p = request.POST
    try:
        d = parse_field_form(p)
        area = Decimal(p["area_ha"]).quantize(Decimal("0.01"))
        lat, lng = Decimal(p["latitude"]).quantize(Decimal("0.000001")), Decimal(p["longitude"]).quantize(Decimal("0.000001"))
        if not (Decimal("0.01") <= area <= Decimal("9999")) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError
    except (KeyError, InvalidOperation, ValueError):
        return HttpResponseBadRequest("Check the field details and try again.")
    try:
        boundary = json.dumps(json.loads(p.get("boundary", "")))
    except ValueError:
        boundary = None
    f = Field.objects.create(location=p.get("location", "")[:120] or "Selected area", latitude=lat, longitude=lng, boundary=boundary,
                             area_ha=area, owner_id=request.user.id, **d)
    initials = (re.sub(r"[^A-Z0-9]", "", "".join(w[0] for w in d["name"].upper().split() if w)) or "FLD")[:3]
    Sensor.objects.create(field=f, device_code="SM-%s-%03d" % (initials, f.id), device_key=secrets.token_urlsafe(16))
    return redirect("field", field_id=f.id)


def field_settings(request, field_id):
    field = get_object_or_404(visible_fields(request), pk=field_id)
    if request.method == "POST":
        try:
            d = parse_field_form(request.POST)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("field_settings", field_id=field.id)
        Field.objects.filter(pk=field.id).update(**d)
        messages.success(request, "Field settings saved.")
        return redirect("field", field_id=field.id)
    return render(request, "farm/settings.html", {"field": field, "crops": CROPS, "page": "dashboard"})


@require_POST
def valve_control(request, field_id):
    field = get_object_or_404(visible_fields(request), pk=field_id)
    act = request.POST.get("action")
    if act in ("auto", "off"):
        Field.objects.filter(pk=field.id).update(valve_mode=act)
        messages.success(request, "Valve mode set to %s." % act)
    elif act == "stop":
        ValveCommand.objects.create(field=field, action="close", source="manual")
        messages.success(request, "Stop command sent. The valve closes the next time the controller checks in.")
    elif act == "water_now":
        if field.valve_mode == "off":
            messages.error(request, "The valve is switched off. Set it to Automatic first.")
        else:
            try:
                mins = int(request.POST.get("minutes", 30))
            except ValueError:
                mins = 30
            mins = max(5, min(mins, field.max_run_min, planner.MAX_RUN_HARD))
            ValveCommand.objects.create(field=field, action="open", duration_min=mins, source="manual")
            messages.success(request, "Watering for %d minutes requested. The valve opens when the controller checks in." % mins)
    return redirect("field", field_id=field.id)


# ---------- savings ----------
def savings(request):
    fields = list(visible_fields(request))
    days = 30 if request.GET.get("days") not in ("7", "90") else int(request.GET["days"])
    rows = [s for s in (services.field_savings(f, days) for f in fields) if s]
    base, used = sum(r["baseline_l"] for r in rows), sum(r["actual_l"] for r in rows)
    from aquacore.savings import summarize
    return render(request, "farm/savings.html", {"rows": rows, "total": summarize(base, used), "days": days,
                                                 "baseline_mm": settings.BASELINE_MM_PER_DAY, "page": "savings"})


def savings_json(request):
    days = 30 if request.GET.get("days") not in ("7", "90") else int(request.GET["days"])
    return JsonResponse(services.daily_savings_series(list(visible_fields(request)), days))


# ---------- sensor health ----------
def sensor_health(request):
    rows = []
    for f in visible_fields(request):
        rows.append({"field": f, "sensor": f.sensors.first(), "health": services.field_health(f),
                     "latest": f.readings.first()})
    return render(request, "farm/health.html", {"rows": rows, "page": "health"})


@require_POST
def calibrate(request, sensor_id):
    s = get_object_or_404(Sensor, pk=sensor_id, field__in=visible_fields(request))
    try:
        off, scale = Decimal(request.POST["offset"]), Decimal(request.POST["scale"])
        if not (-30 <= off <= 30 and Decimal("0.5") <= scale <= 2):
            raise ValueError
    except (KeyError, InvalidOperation, ValueError):
        messages.error(request, "Offset must be between -30 and 30, scale between 0.5 and 2.")
        return redirect("health")
    Sensor.objects.filter(pk=s.pk).update(cal_offset=off, cal_scale=scale)
    messages.success(request, "Calibration saved. It applies to new readings.")
    return redirect("health")


# ---------- reports ----------
def _report_scope(request):
    fields = visible_fields(request)
    fid = request.GET.get("field", "all")
    if fid != "all":
        fields = fields.filter(pk=fid) if fid.isdigit() else fields.none()
    days = int(request.GET["days"]) if request.GET.get("days") in ("7", "30", "90") else 30
    return list(fields), days


def reports(request):
    return render(request, "farm/reports.html", {"fields": visible_fields(request), "page": "reports"})


def report_csv(request, kind):
    fields, days = _report_scope(request)
    since = datetime.now() - timedelta(days=days)
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = 'attachment; filename="aquasense-%s-%dd.csv"' % (kind, days)
    w = csv.writer(resp)
    if kind == "readings":
        w.writerow(["field", "recorded_at", "soil_moisture_pct", "soil_temp_c", "air_temp_c", "humidity_pct", "battery_pct", "forecast_6h_pct"])
        for r in SensorReading.objects.filter(field__in=fields, recorded_at__gte=since).select_related("field").order_by("field_id", "recorded_at"):
            w.writerow([r.field.name, r.recorded_at.isoformat(sep=" "), r.soil_moisture, r.soil_temp, r.air_temp, r.humidity, r.battery, r.predicted_6h])
    elif kind == "waterings":
        w.writerow(["field", "scheduled_for", "duration_min", "volume_l", "source", "status", "reason"])
        for s in IrrigationSchedule.objects.filter(field__in=fields, scheduled_for__gte=since).select_related("field").order_by("field_id", "scheduled_for"):
            w.writerow([s.field.name, s.scheduled_for.isoformat(sep=" "), s.duration_min, s.volume_l, s.source, s.status, s.reason or ""])
    elif kind == "alerts":
        w.writerow(["field", "created_at", "level", "message", "read"])
        for a in Alert.objects.filter(field__in=fields, created_at__gte=since).select_related("field").order_by("field_id", "created_at"):
            w.writerow([a.field.name, a.created_at.isoformat(sep=" "), a.level, a.message, int(a.is_read)])
    else:
        return HttpResponseBadRequest("Unknown report")
    return resp


def report_pdf(request):
    fields, days = _report_scope(request)
    resp = HttpResponse(build_pdf(fields, days), content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="aquasense-report-%dd.pdf"' % days
    return resp


# ---------- cooperative view (staff) ----------
def coop(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Cooperative view is for staff accounts.")
    owners = {u.id: u.username for u in get_user_model().objects.all()}
    rows = []
    for f in Field.objects.all().order_by("id"):
        latest = f.readings.first()
        low, high, _ = planner.effective_thresholds(services.field_dict(f))
        sv = services.field_savings(f, 30)
        rows.append({"field": f, "owner": owners.get(f.owner_id, "unassigned"), "latest": latest,
                     "status": None if not latest else ("dry" if float(latest.soil_moisture) < low else ("wet" if float(latest.soil_moisture) > high else "ok")),
                     "health": services.field_health(f), "used": sv["actual_l"] if sv else 0, "saved_pct": sv["saved_pct"] if sv else None,
                     "unread": f.alerts.filter(is_read=False).count()})
    return render(request, "farm/coop.html", {"rows": rows, "page": "coop"})


# ---------- language, PWA ----------
def set_language(request, code):
    if code in dict(LANGS):
        request.session["lang"] = code
    nxt = request.META.get("HTTP_REFERER", "/")
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = "/"
    return redirect(nxt)


def manifest(request):
    from django.templatetags.static import static
    return JsonResponse({
        "name": "AquaSense", "short_name": "AquaSense", "description": "Precision irrigation for smallholder farmers",
        "start_url": "/", "scope": "/", "display": "standalone", "background_color": "#E7EFEC", "theme_color": "#0C3B40",
        "icons": [{"src": static("farm/icons/icon-192.png"), "sizes": "192x192", "type": "image/png"},
                  {"src": static("farm/icons/icon-512.png"), "sizes": "512x512", "type": "image/png"},
                  {"src": static("farm/icons/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }, content_type="application/manifest+json")


def service_worker(request):
    resp = render(request, "farm/sw.js", content_type="application/javascript")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"
    return resp


def offline(request):
    return render(request, "farm/offline.html")
