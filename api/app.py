"""AquaSense API (Flask): ingestion, ML forecasts, rain-aware planning, valve control, alerts."""
import hmac
import math
import os
import sys
from datetime import date, datetime, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "ml"))
from aquacore import health, i18n, planner, valve  # noqa: E402
from features import clean_reading  # noqa: E402
import db  # noqa: E402
import notify  # noqa: E402
import weather  # noqa: E402
from config import API_KEY  # noqa: E402
from predictor import Predictor  # noqa: E402

app = Flask(__name__)
CORS(app)
predictor = Predictor()


# ---------- helpers ----------
def get_sensor(code):
    return db.query("SELECT * FROM sensors WHERE device_code=%s", (code,), one=True)


def authorized(sensor):
    """Authenticate a sensor with its own key; use the shared key only for legacy sensors.

    A configured per-device key must never be bypassed by the shared API key.
    """
    key = request.headers.get("X-API-Key", "")
    if not key:
        return False
    device_key = sensor.get("device_key") if sensor else None
    expected = device_key or API_KEY
    return bool(expected) and hmac.compare_digest(key, str(expected))


def get_field(fid):
    return db.query("SELECT * FROM fields WHERE id=%s", (fid,), one=True)


def forecast(field_id, reading, hour):
    prev = db.query("SELECT soil_moisture FROM sensor_readings WHERE field_id=%s ORDER BY recorded_at DESC LIMIT 1",
                    (field_id,), one=True)
    prev_m = float(prev["soil_moisture"]) if prev else None
    return predictor.predict_6h(reading["soil_moisture"], reading["soil_temp"], reading["air_temp"],
                                reading["humidity"], hour, prev_m)


def raise_alert(field, level, key, **kw):
    """Store an alert in the field's language and send it by SMS / WhatsApp. De-duplicated over 6 hours."""
    msg = i18n.alert_text(field.get("language") or "en", key, field=field["name"], **kw)
    dup = db.query("SELECT id FROM alerts WHERE field_id=%s AND message=%s AND created_at > %s",
                   (field["id"], msg, datetime.now() - timedelta(hours=6)), one=True)
    if dup:
        return False
    db.execute("INSERT INTO alerts (field_id, level, message, created_at) VALUES (%s,%s,%s,%s)",
               (field["id"], level, msg, datetime.now()))
    if level in ("warning", "critical"):
        notify.send(field, msg)
    return True


def decide_and_schedule(field, r, pred):
    """Rain-aware, growth-stage-aware irrigation planning. Returns a small status dict."""
    low, high, stage = planner.effective_thresholds(field, date.today())
    rain = weather.rain_next_hours(field.get("latitude"), field.get("longitude"), 12)
    plan = planner.plan_irrigation(field, pred, rain or 0.0, low, high)
    out = {"action": plan["action"], "rain_mm": rain, "stage": stage["name"], "low": low, "high": high}
    if plan["action"] == "skip_rain":
        raise_alert(field, "info", "rain_skip")
    elif plan["action"] == "irrigate":
        open_run = db.query("SELECT id FROM irrigation_schedules WHERE field_id=%s AND status IN ('pending','running')",
                            (field["id"],), one=True)
        if not open_run:
            when = datetime.now() + timedelta(hours=1)
            reason = "Forecast %.1f%% in 6h, below %.0f%% threshold (%s stage)" % (pred, low, stage["name"])
            if plan["rain_mm"]:
                reason += "; rain credit %.1f mm" % plan["rain_mm"]
            if plan["capped"]:
                reason += "; run time capped for safety"
            db.execute("""INSERT INTO irrigation_schedules (field_id, scheduled_for, duration_min, volume_l, source, reason)
                          VALUES (%s,%s,%s,%s,'ai',%s)""",
                       (field["id"], when, plan["minutes"], plan["volume_l"], reason))
            notify.send(field, i18n.alert_text(field.get("language") or "en", "water_planned", field=field["name"],
                                               time=when.strftime("%H:%M"), mins=plan["minutes"], litres=plan["volume_l"]))
            out["scheduled"] = True
    if r["soil_moisture"] < low - 6:
        raise_alert(field, "critical", "dry_critical", v="%.1f" % r["soil_moisture"])
    elif r["soil_moisture"] > high + 12:
        raise_alert(field, "warning", "over_wet", v="%.1f" % r["soil_moisture"])
    return out


def store_reading(sensor, body, age_s=0):
    """Validate, calibrate, forecast and store one reading. Returns (field, reading, prediction)."""
    r = clean_reading(body)
    r["soil_moisture"] = max(0.0, min(100.0, r["soil_moisture"] * float(sensor["cal_scale"]) + float(sensor["cal_offset"])))
    field = get_field(sensor["field_id"])
    when = datetime.now() - timedelta(seconds=max(0, int(age_s)))
    pred = forecast(field["id"], r, when.hour)
    db.execute("""INSERT INTO sensor_readings (field_id, recorded_at, soil_moisture, soil_temp, air_temp, humidity, battery, predicted_6h)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
               (field["id"], when, r["soil_moisture"], r["soil_temp"], r["air_temp"], r["humidity"], r["battery"], round(pred, 2)))
    db.execute("UPDATE sensors SET last_seen=%s WHERE id=%s", (datetime.now(), sensor["id"]))
    return field, r, pred


def post_checks(field, r, pred):
    result = decide_and_schedule(field, r, pred)
    recent = db.query("SELECT recorded_at, soil_moisture, battery FROM sensor_readings WHERE field_id=%s ORDER BY recorded_at DESC LIMIT 12",
                      (field["id"],))
    issues = health.assess(recent)["issues"]
    if "stuck" in issues:
        raise_alert(field, "warning", "sensor_stuck")
    if "jump" in issues:
        raise_alert(field, "warning", "sensor_jump")
    if r["battery"] is not None and r["battery"] < 20:
        raise_alert(field, "warning", "battery_low", v="%.0f" % r["battery"])
    return result


# ---------- routes ----------
@app.get("/api/health")
def api_health():
    return jsonify(status="ok", model=predictor.name)


@app.post("/api/readings")
def ingest():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="JSON object required"), 400
    sensor = get_sensor(body.get("device_code"))
    if not sensor:
        return jsonify(error="unknown device_code"), 404
    if not authorized(sensor):
        return jsonify(error="invalid api key"), 401
    try:
        field, r, pred = store_reading(sensor, body)
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    res = post_checks(field, r, pred)
    return jsonify(field_id=field["id"], predicted_6h=round(pred, 2), irrigation_scheduled=bool(res.get("scheduled")),
                   action=res["action"]), 201


@app.post("/api/readings/batch")
def ingest_batch():
    """Upload readings buffered while offline. Each item may carry age_s (seconds ago)."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="JSON object required"), 400
    sensor = get_sensor(body.get("device_code"))
    if not sensor:
        return jsonify(error="unknown device_code"), 404
    if not authorized(sensor):
        return jsonify(error="invalid api key"), 401
    items = body.get("readings") or []
    if not isinstance(items, list) or not items or len(items) > 200:
        return jsonify(error="readings must be a list of 1 to 200 items"), 400
    # Validate ordering metadata before sorting; malformed entries are skipped below.
    def age(item):
        if not isinstance(item, dict):
            return 0
        try:
            value = float(item.get("age_s", 0) or 0)
            if not math.isfinite(value):
                return 0.0
            return max(0.0, min(value, 60 * 60 * 24 * 30))
        except (TypeError, ValueError):
            return 0
    items = sorted(items, key=age, reverse=True)  # oldest first
    stored, last = 0, None
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            last = store_reading(sensor, item, age(item))
            stored += 1
        except (ValueError, TypeError, AttributeError, KeyError):
            continue
    if last:
        post_checks(*last)
    return jsonify(stored=stored, skipped=len(items) - stored), 201


@app.get("/api/predict/<int:field_id>")
def predict(field_id):
    # Forecasts contain private farm telemetry; only trusted server-side callers may read them.
    if not API_KEY or not hmac.compare_digest(request.headers.get("X-API-Key", ""), API_KEY):
        return jsonify(error="invalid api key"), 401
    field = get_field(field_id)
    last = db.query("SELECT * FROM sensor_readings WHERE field_id=%s ORDER BY recorded_at DESC LIMIT 1", (field_id,), one=True)
    if not field or not last:
        return jsonify(error="no data"), 404
    r = {k: (float(last[k]) if last[k] is not None else None) for k in ("soil_moisture", "soil_temp", "air_temp", "humidity")}
    pred = forecast(field_id, r, datetime.now().hour)
    low, high, stage = planner.effective_thresholds(field, date.today())
    rain = weather.rain_next_hours(field.get("latitude"), field.get("longitude"), 12)
    plan = planner.plan_irrigation(field, pred, rain or 0.0, low, high)
    return jsonify(field_id=field_id, current=r["soil_moisture"], predicted_6h=round(pred, 1), margin=predictor.margin,
                   model=predictor.name, action=plan["action"], needs_irrigation=plan["action"] == "irrigate",
                   volume_l=plan.get("volume_l", 0), duration_min=plan.get("minutes", 0), rain_mm=rain,
                   stage=stage["name"], low=round(low, 1), high=round(high, 1))


@app.get("/api/devices/<code>/command")
def device_command(code):
    """Valve controller polls this. Returns {action: open|close|idle, minutes, ref}."""
    sensor = get_sensor(code)
    if not sensor:
        return jsonify(error="unknown device_code"), 404
    if not authorized(sensor):
        return jsonify(error="invalid api key"), 401
    field = get_field(sensor["field_id"])
    now = datetime.now()
    if field["valve_state"] == "open" and field["valve_until"] and now > field["valve_until"] + timedelta(minutes=10):
        db.execute("UPDATE fields SET valve_state='closed', valve_until=NULL WHERE id=%s", (field["id"],))
        db.execute("UPDATE irrigation_schedules SET status='done' WHERE field_id=%s AND status='running'", (field["id"],))
        field["valve_state"] = "closed"
    cmd = db.query("SELECT * FROM valve_commands WHERE field_id=%s AND status='pending' ORDER BY id LIMIT 1", (field["id"],), one=True)
    due = db.query("""SELECT * FROM irrigation_schedules WHERE field_id=%s AND status='pending' AND scheduled_for<=%s
                      ORDER BY scheduled_for LIMIT 1""", (field["id"], now), one=True)
    last = db.query("SELECT soil_moisture FROM sensor_readings WHERE field_id=%s ORDER BY recorded_at DESC LIMIT 1", (field["id"],), one=True)
    moisture = float(last["soil_moisture"]) if last else None
    _, high, _ = planner.effective_thresholds(field, date.today())
    d = valve.decide(field["valve_mode"], moisture, high, field["max_run_min"], cmd, due)

    if d["skip_reason"] and due:
        db.execute("UPDATE irrigation_schedules SET status='skipped', reason=%s WHERE id=%s", (d["skip_reason"], due["id"]))
    if d["action"] == "open":
        if d["source"] == "schedule":
            db.execute("UPDATE irrigation_schedules SET status='running' WHERE id=%s", (due["id"],))
        else:
            db.execute("UPDATE valve_commands SET status='sent' WHERE id=%s", (cmd["id"],))
        db.execute("UPDATE fields SET valve_state='open', valve_until=%s WHERE id=%s",
                   (now + timedelta(minutes=d["minutes"]), field["id"]))
    elif d["action"] == "close":
        if cmd:
            db.execute("UPDATE valve_commands SET status='done' WHERE id=%s", (cmd["id"],))
        db.execute("UPDATE fields SET valve_state='closed', valve_until=NULL WHERE id=%s", (field["id"],))
        db.execute("UPDATE irrigation_schedules SET status='done' WHERE field_id=%s AND status='running'", (field["id"],))
    return jsonify(action=d["action"], minutes=d["minutes"], ref=d["ref"])


@app.post("/api/devices/<code>/ack")
def device_ack(code):
    sensor = get_sensor(code)
    if not sensor:
        return jsonify(error="unknown device_code"), 404
    if not authorized(sensor):
        return jsonify(error="invalid api key"), 401
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="JSON object required"), 400
    ref = str(body.get("ref") or "")
    status = body.get("status")
    if status not in ("done", "failed") or len(ref) < 2 or ref[0] not in ("s", "c") or not ref[1:].isdigit():
        return jsonify(error="valid ref and status (done|failed) are required"), 400
    field = get_field(sensor["field_id"])
    command_id = int(ref[1:])
    ok = status == "done"
    if ref[0] == "s":
        existing = db.query("SELECT id FROM irrigation_schedules WHERE id=%s AND field_id=%s AND status='running'",
                            (command_id, field["id"]), one=True)
        if not existing:
            return jsonify(error="unknown or inactive schedule reference"), 404
        db.execute("UPDATE irrigation_schedules SET status=%s WHERE id=%s AND field_id=%s",
                   ("done" if ok else "skipped", command_id, field["id"]))
    else:
        existing = db.query("SELECT id FROM valve_commands WHERE id=%s AND field_id=%s AND status='sent'",
                            (command_id, field["id"]), one=True)
        if not existing:
            return jsonify(error="unknown or inactive command reference"), 404
        db.execute("UPDATE valve_commands SET status=%s WHERE id=%s AND field_id=%s",
                   ("done" if ok else "failed", command_id, field["id"]))
    db.execute("UPDATE fields SET valve_state='closed', valve_until=NULL WHERE id=%s", (field["id"],))
    if not ok:
        raise_alert(field, "critical", "valve_fault")
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
