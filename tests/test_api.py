"""API behaviour tests. MySQL is replaced by an in-memory SQLite database (same SQL, ? placeholders)."""
import os, sqlite3, sys, unittest
from datetime import datetime, timedelta
from unittest import mock

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path[:0] = [ROOT, os.path.join(ROOT, "api"), os.path.join(ROOT, "ml")]
sqlite3.register_adapter(datetime, lambda d: d.isoformat(sep=" "))
for t in ("DATETIME", "TIMESTAMP"):
    sqlite3.register_converter(t, lambda b: datetime.fromisoformat(b.decode()))
sqlite3.register_converter("DATE", lambda b: datetime.fromisoformat(b.decode()).date())

import db  # noqa: E402
import app as api  # noqa: E402

DDL = """
CREATE TABLE fields (id INTEGER PRIMARY KEY AUTOINCREMENT, name, crop, location, latitude, longitude, boundary, owner_id,
  contact_phone, language, planted_on DATE, valve_mode, valve_state, valve_until DATETIME, max_run_min, area_ha, root_depth_mm,
  flow_lph, moisture_low, moisture_high);
CREATE TABLE sensors (id INTEGER PRIMARY KEY AUTOINCREMENT, field_id, device_code, device_key, cal_offset, cal_scale, last_seen DATETIME);
CREATE TABLE sensor_readings (id INTEGER PRIMARY KEY AUTOINCREMENT, field_id, recorded_at DATETIME, soil_moisture, soil_temp, air_temp,
  humidity, battery, predicted_6h);
CREATE TABLE irrigation_schedules (id INTEGER PRIMARY KEY AUTOINCREMENT, field_id, scheduled_for DATETIME, duration_min, volume_l,
  source, status DEFAULT 'pending', reason);
CREATE TABLE alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, field_id, level, message, is_read DEFAULT 0, created_at DATETIME);
CREATE TABLE valve_commands (id INTEGER PRIMARY KEY AUTOINCREMENT, field_id, action, duration_min, source, status DEFAULT 'pending',
  created_at DATETIME);
CREATE TABLE notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, field_id, phone, channel, message, status, created_at DATETIME);
"""


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)
        self.conn.row_factory = lambda cur, row: dict(zip([c[0] for c in cur.description], row))
        self.conn.executescript(DDL)
        self.conn.execute("""INSERT INTO fields (name, crop, location, latitude, longitude, contact_phone, language, valve_mode,
            valve_state, max_run_min, area_ha, root_depth_mm, flow_lph, moisture_low, moisture_high)
            VALUES ('North Terrace','Millet','Kutch',23.7,69.8,'+919999900000','hi','auto','closed',180,0.6,300,20000,26,38)""")
        self.conn.execute("INSERT INTO sensors (field_id, device_code, device_key, cal_offset, cal_scale) VALUES (1,'SM-1','secretkey',0,1)")

        def query(sql, args=None, one=False):
            cur = self.conn.execute(sql.replace("%s", "?"), args or ())
            return cur.fetchone() if one else cur.fetchall()

        def execute(sql, args=None):
            cur = self.conn.execute(sql.replace("%s", "?"), args or ())
            return cur.lastrowid

        self.patches = [mock.patch.object(db, "query", query), mock.patch.object(db, "execute", execute),
                        mock.patch.object(api.weather, "rain_next_hours", lambda *a, **k: self.rain)]
        for p in self.patches:
            p.start()
        self.rain = 0.0
        self.client = api.app.test_client()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def post(self, moisture, key="secretkey", **extra):
        body = dict({"device_code": "SM-1", "soil_moisture": moisture, "soil_temp": 25, "air_temp": 28, "humidity": 50, "battery": 90}, **extra)
        return self.client.post("/api/readings", json=body, headers={"X-API-Key": key})

    def rows(self, table, where="1"):
        return self.conn.execute("SELECT * FROM %s WHERE %s" % (table, where)).fetchall()

    # ---- auth
    def test_bad_key_rejected(self):
        self.assertEqual(self.post(30, key="nope").status_code, 401)

    def test_global_key_cannot_override_device_key(self):
        self.assertEqual(self.post(30, key=api.API_KEY).status_code, 401)

    def test_global_key_works_for_legacy_sensor_without_device_key(self):
        self.conn.execute("UPDATE sensors SET device_key=NULL")
        with mock.patch.object(api, "API_KEY", "global-secret"):
            self.assertEqual(self.post(30, key="global-secret").status_code, 201)

    def test_unknown_device(self):
        r = self.client.post("/api/readings", json={"device_code": "X", "soil_moisture": 30}, headers={"X-API-Key": api.API_KEY})
        self.assertEqual(r.status_code, 404)

    # ---- planning
    def test_dry_reading_schedules_and_notifies_in_hindi(self):
        r = self.post(18)
        self.assertEqual(r.status_code, 201)
        sched = self.rows("irrigation_schedules")
        self.assertEqual(len(sched), 1)
        self.assertEqual(sched[0]["status"], "pending")
        alerts = self.rows("alerts")
        self.assertTrue(any("सूखी" in a["message"] for a in alerts))     # critical dry alert in Hindi
        notes = self.rows("notifications")
        self.assertTrue(notes and all(n["status"] == "logged" and n["phone"] == "+919999900000" for n in notes))

    def test_no_duplicate_schedule(self):
        self.post(18); self.post(17)
        self.assertEqual(len(self.rows("irrigation_schedules")), 1)

    def test_rain_skips_watering(self):
        self.rain = 15.0
        self.post(27)
        self.assertEqual(self.rows("irrigation_schedules"), [])
        self.assertTrue(any(a["level"] == "info" for a in self.rows("alerts")))

    def test_rain_reduces_volume(self):
        self.post(18)
        dry = self.rows("irrigation_schedules")[0]["volume_l"]
        self.conn.execute("DELETE FROM irrigation_schedules")
        self.rain = 8.0
        self.post(18)
        self.assertLess(self.rows("irrigation_schedules")[0]["volume_l"], dry)

    def test_calibration_applied(self):
        self.conn.execute("UPDATE sensors SET cal_scale=1.1, cal_offset=-2")
        self.post(30)
        self.assertAlmostEqual(self.rows("sensor_readings")[0]["soil_moisture"], 31.0, places=2)

    def test_batch_upload(self):
        items = [{"soil_moisture": 30 - i, "air_temp": 28, "humidity": 50, "age_s": 1800 * (3 - i)} for i in range(3)] + [{"air_temp": 1}]
        r = self.client.post("/api/readings/batch", json={"device_code": "SM-1", "readings": items}, headers={"X-API-Key": "secretkey"})
        self.assertEqual((r.status_code, r.get_json()["stored"], r.get_json()["skipped"]), (201, 3, 1))
        times = [x["recorded_at"] for x in self.rows("sensor_readings")]
        self.assertEqual(times, sorted(times))

    def test_predict_endpoint(self):
        self.post(30)
        with mock.patch.object(api, "API_KEY", "global-secret"):
            denied = self.client.get("/api/predict/1")
            self.assertEqual(denied.status_code, 401)
            j = self.client.get("/api/predict/1", headers={"X-API-Key": "global-secret"}).get_json()
        self.assertIn("margin", j); self.assertIn("stage", j); self.assertEqual(j["low"], 26.0)

    # ---- valve
    def cmd(self):
        return self.client.get("/api/devices/SM-1/command", headers={"X-API-Key": "secretkey"}).get_json()

    def test_valve_opens_for_due_schedule_once(self):
        self.post(20)
        self.conn.execute("UPDATE irrigation_schedules SET scheduled_for=?", (datetime.now() - timedelta(minutes=1),))
        first = self.cmd()
        self.assertEqual(first["action"], "open"); self.assertGreater(first["minutes"], 0)
        self.assertEqual(self.rows("irrigation_schedules")[0]["status"], "running")
        self.assertEqual(self.rows("fields")[0]["valve_state"], "open")
        self.assertEqual(self.cmd()["action"], "idle")
        ack = self.client.post("/api/devices/SM-1/ack", json={"ref": first["ref"], "status": "done"}, headers={"X-API-Key": "secretkey"})
        self.assertEqual(ack.status_code, 200)
        self.assertEqual(self.rows("irrigation_schedules")[0]["status"], "done")
        self.assertEqual(self.rows("fields")[0]["valve_state"], "closed")

    def test_wet_soil_blocks_scheduled_run(self):
        self.conn.execute("INSERT INTO irrigation_schedules (field_id, scheduled_for, duration_min, volume_l, source) VALUES (1,?,30,10000,'ai')",
                          (datetime.now() - timedelta(minutes=5),))
        self.post(45)
        self.assertEqual(self.cmd()["action"], "idle")
        self.assertEqual(self.rows("irrigation_schedules")[0]["status"], "skipped")

    def test_manual_open_and_stop(self):
        self.conn.execute("INSERT INTO valve_commands (field_id, action, duration_min, source) VALUES (1,'open',999,'manual')")
        c = self.cmd()
        self.assertEqual((c["action"], c["minutes"]), ("open", 180))     # capped by max_run_min
        self.conn.execute("INSERT INTO valve_commands (field_id, action, source) VALUES (1,'close','manual')")
        self.assertEqual(self.cmd()["action"], "close")
        self.assertEqual(self.rows("fields")[0]["valve_state"], "closed")

    def test_off_mode_forces_close(self):
        self.conn.execute("UPDATE fields SET valve_mode='off'")
        self.assertEqual(self.cmd()["action"], "close")

    def test_failed_ack_raises_alert(self):
        self.conn.execute("INSERT INTO valve_commands (field_id, action, duration_min, source, status) VALUES (1,'open',30,'manual','sent')")
        response = self.client.post("/api/devices/SM-1/ack", json={"ref": "c1", "status": "failed"}, headers={"X-API-Key": "secretkey"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(a["level"] == "critical" for a in self.rows("alerts")))

    def test_ack_rejects_unknown_reference_without_closing_valve(self):
        self.conn.execute("UPDATE fields SET valve_state='open'")
        response = self.client.post("/api/devices/SM-1/ack", json={"ref": "c999", "status": "done"}, headers={"X-API-Key": "secretkey"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.rows("fields")[0]["valve_state"], "open")

    def test_batch_skips_non_object_and_bad_age_items(self):
        body = {"device_code": "SM-1", "readings": [None, {"soil_moisture": 30, "age_s": "bad"}, {"soil_moisture": 31, "age_s": 5}]}
        response = self.client.post("/api/readings/batch", json=body, headers={"X-API-Key": "secretkey"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["stored"], 2)
        self.assertEqual(response.get_json()["skipped"], 1)

    def test_stale_open_valve_is_closed(self):
        self.conn.execute("UPDATE fields SET valve_state='open', valve_until=?", (datetime.now() - timedelta(minutes=30),))
        self.conn.execute("INSERT INTO irrigation_schedules (field_id, scheduled_for, duration_min, volume_l, source, status) VALUES (1,?,30,1,'ai','running')", (datetime.now(),))
        self.cmd()
        self.assertEqual(self.rows("fields")[0]["valve_state"], "closed")
        self.assertEqual(self.rows("irrigation_schedules")[0]["status"], "done")


if __name__ == "__main__":
    unittest.main()
