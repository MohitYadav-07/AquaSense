import json
from datetime import date, datetime, timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from .models import Alert, Field, IrrigationSchedule, Notification, Sensor, SensorReading, ValveCommand
from .services import forecast_accuracy

NOW = datetime.now().replace(microsecond=0)


def mk_field(owner, name, **kw):
    d = dict(name=name, crop="Millet", location="Test", area_ha=0.5, root_depth_mm=300, flow_lph=20000,
             moisture_low=26, moisture_high=38, owner_id=owner.id if owner else None)
    d.update(kw)
    f = Field.objects.create(**d)
    Sensor.objects.create(field=f, device_code="SM-%s-%03d" % (name[:2].upper(), f.id), device_key="k" + str(f.id))
    return f


def readings(field, values, step_min=30, pred=None, end=None):
    end = end or NOW
    rows = []
    for i, v in enumerate(values):
        rows.append(SensorReading(field=field, recorded_at=end - timedelta(minutes=step_min * (len(values) - 1 - i)),
                                  soil_moisture=v, soil_temp=25, air_temp=30, humidity=45, battery=90,
                                  predicted_6h=pred(i, v) if pred else None))
    SensorReading.objects.bulk_create(rows)


class Base(TestCase):
    def setUp(self):
        U = get_user_model()
        self.ann = U.objects.create_user("ann", password="x")
        self.bob = U.objects.create_user("bob", password="x")
        self.admin = U.objects.create_user("root", password="x", is_staff=True)
        self.fa = mk_field(self.ann, "AnnPlot")
        self.fb = mk_field(self.bob, "BobPlot")
        self.client.force_login(self.ann)


class AccessTests(Base):
    def test_anonymous_redirected(self):
        self.client.logout()
        for url in ("/", "/explore/", "/savings/", "/reports/", "/field/%d/" % self.fa.id):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/login/", r["Location"])

    def test_public_pwa_and_login_pages(self):
        self.client.logout()
        for url in ("/login/", "/manifest.json", "/sw.js", "/offline/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertIn("serviceWorker", self.client.get("/login/").content.decode() + "serviceWorker")
        self.assertEqual(self.client.get("/sw.js")["Service-Worker-Allowed"], "/")
        self.assertEqual(self.client.get("/manifest.json").json()["display"], "standalone")

    def test_login_flow(self):
        self.client.logout()
        r = self.client.post("/login/", {"username": "ann", "password": "x"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_farmer_sees_only_own_fields(self):
        html = self.client.get("/").content.decode()
        self.assertIn("AnnPlot", html); self.assertNotIn("BobPlot", html)
        self.assertEqual(self.client.get("/field/%d/" % self.fb.id).status_code, 404)
        self.assertEqual(self.client.get("/field/%d/series.json" % self.fb.id).status_code, 404)
        self.assertEqual(self.client.get("/field/%d/settings/" % self.fb.id).status_code, 404)

    def test_staff_sees_everything(self):
        self.client.force_login(self.admin)
        html = self.client.get("/").content.decode()
        self.assertIn("AnnPlot", html); self.assertIn("BobPlot", html)

    def test_cannot_act_on_other_farmers_data(self):
        s = IrrigationSchedule.objects.create(field=self.fb, scheduled_for=NOW, duration_min=30, volume_l=100, status="pending")
        self.client.post("/schedule/", {"action": "done", "id": s.id})
        s.refresh_from_db(); self.assertEqual(s.status, "pending")
        self.assertEqual(self.client.post("/field/%d/valve/" % self.fb.id, {"action": "stop"}).status_code, 404)
        self.assertEqual(ValveCommand.objects.count(), 0)
        sensor = self.fb.sensors.first()
        self.assertEqual(self.client.post("/health/%d/calibrate/" % sensor.id, {"offset": "1", "scale": "1"}).status_code, 404)

    def test_coop_staff_only(self):
        self.assertEqual(self.client.get("/coop/").status_code, 403)
        self.client.force_login(self.admin)
        r = self.client.get("/coop/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("ann", r.content.decode()); self.assertIn("BobPlot", r.content.decode())


class FieldTests(Base):
    POST = dict(name="New Plot", crop="Tomato", location="Anantapur", latitude="14.681900", longitude="77.600600",
                boundary="[[14.68,77.6],[14.68,77.61],[14.69,77.61]]", area_ha="0.85", moisture_low="30", moisture_high="42",
                root_depth_mm="400", flow_lph="20000", planted_on="2026-10-01", contact_phone="+919876543210", language="te")

    def test_create_sets_owner_key_and_contact(self):
        r = self.client.post("/fields/new/", self.POST)
        self.assertEqual(r.status_code, 302)
        f = Field.objects.get(name="New Plot")
        self.assertEqual((f.owner_id, f.language, f.contact_phone, f.planted_on), (self.ann.id, "te", "+919876543210", date(2026, 10, 1)))
        s = f.sensors.get()
        self.assertTrue(s.device_code.startswith("SM-NP-")); self.assertGreaterEqual(len(s.device_key), 16)

    def test_create_validation(self):
        for bad in ({"contact_phone": "abc"}, {"language": "fr"}, {"moisture_low": "50"}, {"area_ha": "x"}, {"max_run_min": "999"}):
            self.assertEqual(self.client.post("/fields/new/", dict(self.POST, **bad)).status_code, 400, bad)
        self.assertFalse(Field.objects.filter(name="New Plot").exists())
        self.assertEqual(self.client.get("/fields/new/").status_code, 405)

    def test_settings_update(self):
        r = self.client.post("/field/%d/settings/" % self.fa.id, dict(self.POST, name="Renamed", max_run_min="90"))
        self.assertEqual(r.status_code, 302)
        self.fa.refresh_from_db()
        self.assertEqual((self.fa.name, self.fa.max_run_min, self.fa.language), ("Renamed", 90, "te"))
        self.client.post("/field/%d/settings/" % self.fa.id, dict(self.POST, moisture_low="90"))
        self.fa.refresh_from_db(); self.assertEqual(self.fa.name, "Renamed")

    def test_explore_pins_scoped(self):
        Field.objects.filter(pk__in=(self.fa.id, self.fb.id)).update(latitude=10, longitude=20)
        html = self.client.get("/explore/").content.decode()
        self.assertIn("AnnPlot", html); self.assertNotIn("BobPlot", html)


class DashboardTests(Base):
    def setUp(self):
        super().setUp()
        readings(self.fa, [30 - i * 0.05 for i in range(40)], pred=lambda i, v: v - 2)

    def test_renders_with_forecast_offline(self):
        with mock.patch("farm.views._forecast", return_value=None):
            html = self.client.get("/field/%d/" % self.fa.id).content.decode()
        self.assertIn("Live forecast is offline", html); self.assertIn("Irrigation valve", html)

    def test_rain_and_irrigate_ledes(self):
        fc = {"action": "irrigate", "predicted_6h": 24.5, "duration_min": 90, "volume_l": 30000, "margin": 1.6, "rain_mm": 2.5}
        with mock.patch("farm.views._forecast", return_value=fc):
            html = self.client.get("/field/%d/" % self.fa.id).content.decode()
        self.assertIn("Water for 90 minutes", html); self.assertIn("Rain expected in the next 12 hours: 2.5 mm", html)
        with mock.patch("farm.views._forecast", return_value=dict(fc, action="skip_rain")):
            self.assertIn("watering is on hold", self.client.get("/field/%d/" % self.fa.id).content.decode())

    def test_hindi_and_telugu(self):
        fc = {"action": "none", "predicted_6h": 31, "margin": 1.6}
        with mock.patch("farm.views._forecast", return_value=fc):
            self.client.get("/lang/hi/")
            self.assertIn("सिंचाई वाल्व", self.client.get("/field/%d/" % self.fa.id).content.decode())
            self.client.get("/lang/te/")
            self.assertIn("నీటి వాల్వ్", self.client.get("/field/%d/" % self.fa.id).content.decode())

    def test_status_badge_and_stage(self):
        with mock.patch("farm.views._forecast", return_value=None):
            html = self.client.get("/field/%d/" % self.fa.id).content.decode()
        self.assertIn('class="status ok"', html)
        Field.objects.filter(pk=self.fa.id).update(planted_on=date.today() - timedelta(days=5))
        with mock.patch("farm.views._forecast", return_value=None):
            html = self.client.get("/field/%d/" % self.fa.id).content.decode()
        self.assertIn("Establishment", html)

    def test_language_switch_is_safe(self):
        r = self.client.get("/lang/hi/", HTTP_REFERER="https://evil.example/x")
        self.assertEqual(r["Location"], "/")
        self.client.get("/lang/xx/"); self.assertEqual(self.client.session["lang"], "hi")


class ValveTests(Base):
    def url(self):
        return "/field/%d/valve/" % self.fa.id

    def test_water_now_is_capped(self):
        Field.objects.filter(pk=self.fa.id).update(max_run_min=45)
        self.client.post(self.url(), {"action": "water_now", "minutes": "200"})
        c = ValveCommand.objects.get()
        self.assertEqual((c.action, c.duration_min, c.status), ("open", 45, "pending"))

    def test_off_blocks_manual_watering(self):
        self.client.post(self.url(), {"action": "off"})
        self.fa.refresh_from_db(); self.assertEqual(self.fa.valve_mode, "off")
        self.client.post(self.url(), {"action": "water_now", "minutes": "30"})
        self.assertEqual(ValveCommand.objects.count(), 0)
        self.client.post(self.url(), {"action": "auto"})
        self.fa.refresh_from_db(); self.assertEqual(self.fa.valve_mode, "auto")

    def test_stop_and_bad_minutes(self):
        self.client.post(self.url(), {"action": "stop"})
        self.assertEqual(ValveCommand.objects.get().action, "close")
        self.client.post(self.url(), {"action": "water_now", "minutes": "abc"})
        self.assertEqual(ValveCommand.objects.filter(action="open").get().duration_min, 30)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url()).status_code, 405)


class SavingsAndReportTests(Base):
    def setUp(self):
        super().setUp()
        readings(self.fa, [30] * 5, end=NOW)
        SensorReading.objects.filter(field=self.fa).update(recorded_at=NOW - timedelta(days=10))
        readings(self.fa, [31, 30.5, 30], end=NOW)
        IrrigationSchedule.objects.create(field=self.fa, scheduled_for=NOW - timedelta(days=2), duration_min=60, volume_l=20000, status="done")
        IrrigationSchedule.objects.create(field=self.fa, scheduled_for=NOW - timedelta(days=1), duration_min=60, volume_l=5000, status="skipped")
        IrrigationSchedule.objects.create(field=self.fb, scheduled_for=NOW - timedelta(days=1), duration_min=60, volume_l=99999, status="done")
        Alert.objects.create(field=self.fa, level="warning", message="dry")
        Notification.objects.create(field=self.fa, phone="+911", channel="sms", message="hello", status="logged")

    def test_savings_page_counts_only_done_and_own(self):
        html = self.client.get("/savings/?days=30").content.decode()
        self.assertIn("Water saved", html)
        rows = self.client.get("/savings/").context["rows"]
        self.assertEqual([r["actual_l"] for r in rows], [20000])
        self.assertGreater(rows[0]["saved_l"], 0)

    def test_savings_json_cumulative(self):
        j = self.client.get("/savings.json?days=30").json()
        self.assertEqual(len(j["labels"]), 30)
        self.assertEqual(j["actual"][-1], 20000)
        self.assertEqual(j["baseline"], sorted(j["baseline"]))

    def test_csv_exports(self):
        r = self.client.get("/reports/readings.csv?days=30")
        self.assertEqual(r["Content-Type"], "text/csv")
        body = r.content.decode()
        self.assertIn("AnnPlot", body); self.assertNotIn("BobPlot", body)
        self.assertEqual(len(body.strip().splitlines()), 1 + 8)           # 5 readings from 10 days ago + 3 recent
        week = self.client.get("/reports/readings.csv?days=7").content.decode()
        self.assertEqual(len(week.strip().splitlines()), 1 + 3)           # the 7-day window drops the old ones
        self.assertIn("20000", self.client.get("/reports/waterings.csv?days=30").content.decode())
        self.assertNotIn("99999", self.client.get("/reports/waterings.csv?days=30").content.decode())
        self.assertIn("dry", self.client.get("/reports/alerts.csv").content.decode())
        self.assertEqual(self.client.get("/reports/bogus.csv").status_code, 400)

    def test_pdf_export(self):
        r = self.client.get("/reports/summary.pdf?days=30&field=%d" % self.fa.id)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        self.assertTrue(self.client.get("/reports/summary.pdf?field=all").content.startswith(b"%PDF"))
        other = self.client.get("/reports/readings.csv?field=%d" % self.fb.id).content.decode()
        self.assertEqual(len(other.strip().splitlines()), 1)              # header only: not their field

    def test_alert_page_and_mark_read(self):
        html = self.client.get("/alerts/").content.decode()
        self.assertIn("hello", html)
        self.client.post("/alerts/")
        self.assertFalse(Alert.objects.filter(field=self.fa, is_read=False).exists())


class HealthTests(Base):
    def test_stuck_sensor_flagged_and_calibration(self):
        readings(self.fa, [31.2] * 12)
        html = self.client.get("/health/").content.decode()
        self.assertIn("not changing", html)
        s = self.fa.sensors.get()
        self.client.post("/health/%d/calibrate/" % s.id, {"offset": "-2.5", "scale": "1.1"})
        s.refresh_from_db(); self.assertEqual((float(s.cal_offset), float(s.cal_scale)), (-2.5, 1.1))
        self.client.post("/health/%d/calibrate/" % s.id, {"offset": "99", "scale": "1"})
        s.refresh_from_db(); self.assertEqual(float(s.cal_offset), -2.5)

    def test_no_data_is_offline(self):
        self.assertIn("No readings received yet", self.client.get("/health/").content.decode())


class ServiceTests(Base):
    def test_forecast_accuracy(self):
        # predictions are always 2 points under; the actual series is flat at 30 => error 2 (except where no later reading exists)
        readings(self.fa, [30.0] * 40, pred=lambda i, v: 28.0)
        acc = forecast_accuracy(self.fa.id)
        self.assertEqual(acc["mae"], 2.0); self.assertGreaterEqual(acc["n"], 20)

    def test_forecast_accuracy_needs_data(self):
        self.assertIsNone(forecast_accuracy(self.fa.id))


class CommandTests(TestCase):
    def test_create_demo_users_assigns_fields(self):
        f = Field.objects.create(name="Loose", crop="Rice", location="x", area_ha=1, root_depth_mm=300, flow_lph=1000, moisture_low=20, moisture_high=30)
        out = StringIO(); call_command("create_demo_users", stdout=out)
        farmer = get_user_model().objects.get(username="farmer")
        f.refresh_from_db(); self.assertEqual(f.owner_id, farmer.id)
        self.assertTrue(get_user_model().objects.get(username="admin").is_staff)
        self.assertIn("farmer /", out.getvalue())
        out2 = StringIO(); call_command("create_demo_users", stdout=out2); self.assertIn("already exist", out2.getvalue())
