import os, sys, unittest
from datetime import date, datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ml"))
from aquacore import health, i18n, planner, savings, valve
from features import clean_reading

FIELD = {"crop": "Millet", "planted_on": None, "moisture_low": 26, "moisture_high": 38,
         "root_depth_mm": 300, "area_ha": 0.6, "flow_lph": 20000, "max_run_min": 180}


class PlannerTests(unittest.TestCase):
    def test_no_action_when_forecast_ok(self):
        self.assertEqual(planner.plan_irrigation(FIELD, 30)["action"], "none")

    def test_irrigates_when_dry(self):
        p = planner.plan_irrigation(FIELD, 22)
        self.assertEqual(p["action"], "irrigate")
        self.assertGreater(p["volume_l"], 0)
        self.assertLessEqual(p["minutes"], 180)

    def test_rain_skips_small_deficit(self):
        p = planner.plan_irrigation(FIELD, 24, rain_mm=12)   # 12 mm * 0.8 / 300 = +3.2 pts
        self.assertEqual(p["action"], "skip_rain")

    def test_rain_reduces_volume(self):
        dry = planner.plan_irrigation(FIELD, 18)
        wet = planner.plan_irrigation(FIELD, 18, rain_mm=10)
        self.assertEqual(wet["action"], "irrigate")
        self.assertLess(wet["volume_l"], dry["volume_l"])

    def test_run_time_is_capped(self):
        f = dict(FIELD, flow_lph=2000, max_run_min=60)
        p = planner.plan_irrigation(f, 15)
        self.assertEqual(p["minutes"], 60)
        self.assertTrue(p["capped"])
        self.assertEqual(p["volume_l"], 2000)

    def test_hard_cap(self):
        f = dict(FIELD, flow_lph=500, max_run_min=9999)
        self.assertEqual(planner.plan_irrigation(f, 10)["minutes"], planner.MAX_RUN_HARD)

    def test_stage_thresholds(self):
        today = date(2026, 11, 19)
        young = planner.effective_thresholds(dict(FIELD, planted_on="2026-11-10"), today)
        self.assertEqual(young[2]["name"], "Establishment")
        self.assertEqual(young[0], 29.0)
        flower = planner.effective_thresholds(dict(FIELD, planted_on=today - timedelta(days=60)), today)
        self.assertEqual(flower[2]["name"], "Flowering / fruiting")
        old = planner.effective_thresholds(dict(FIELD, planted_on=today - timedelta(days=200)), today)
        self.assertEqual(old[2]["name"], "Maturity")
        self.assertEqual(old[0], 22.0)
        self.assertEqual(planner.effective_thresholds(FIELD, today)[2]["name"], "Not set")

    def test_thresholds_stay_ordered(self):
        low, high, _ = planner.effective_thresholds(dict(FIELD, moisture_low=88, moisture_high=89, planted_on="2026-11-18"), date(2026, 11, 19))
        self.assertGreater(high, low)


class ValveTests(unittest.TestCase):
    SCHED = {"id": 7, "duration_min": 45}

    def test_schedule_opens(self):
        d = valve.decide("auto", 24, 38, 180, None, self.SCHED)
        self.assertEqual((d["action"], d["minutes"], d["ref"]), ("open", 45, "s7"))

    def test_off_mode_closes(self):
        self.assertEqual(valve.decide("off", 24, 38, 180, None, self.SCHED)["action"], "close")

    def test_off_mode_ignores_manual_open(self):
        self.assertEqual(valve.decide("off", 24, 38, 180, {"id": 1, "action": "open", "duration_min": 30}, None)["action"], "close")

    def test_wet_soil_skips_schedule(self):
        d = valve.decide("auto", 39, 38, 180, None, self.SCHED)
        self.assertEqual(d["action"], "idle")
        self.assertIn("target", d["skip_reason"])

    def test_manual_stop_wins(self):
        d = valve.decide("auto", 20, 38, 180, {"id": 3, "action": "close"}, self.SCHED)
        self.assertEqual((d["action"], d["ref"]), ("close", "c3"))

    def test_max_run_cap(self):
        d = valve.decide("auto", 20, 38, 30, {"id": 2, "action": "open", "duration_min": 120}, None)
        self.assertEqual(d["minutes"], 30)
        d = valve.decide("auto", 20, 38, 999, {"id": 2, "action": "open", "duration_min": 999}, None)
        self.assertEqual(d["minutes"], planner.MAX_RUN_HARD)

    def test_idle(self):
        self.assertEqual(valve.decide("auto", 30, 38, 180, None, None)["action"], "idle")


def reading(minutes_ago, m, bat=90, now=datetime(2026, 11, 19, 12, 0)):
    return {"recorded_at": now - timedelta(minutes=minutes_ago), "soil_moisture": m, "battery": bat}


class HealthTests(unittest.TestCase):
    NOW = datetime(2026, 11, 19, 12, 0)

    def test_ok(self):
        rs = [reading(30 * i, 30 + i * 0.4) for i in range(12)]
        self.assertEqual(health.assess(rs, self.NOW)["status"], "ok")

    def test_offline(self):
        rs = [reading(400 + 30 * i, 30 + i) for i in range(10)]
        a = health.assess(rs, self.NOW)
        self.assertEqual(a["status"], "offline")

    def test_stuck(self):
        rs = [reading(30 * i, 31.2) for i in range(10)]
        self.assertIn("stuck", health.assess(rs, self.NOW)["issues"])

    def test_jump(self):
        rs = [reading(0, 60), reading(30, 28)] + [reading(30 * i, 28 - i * 0.2) for i in range(2, 10)]
        self.assertIn("jump", health.assess(rs, self.NOW)["issues"])

    def test_battery(self):
        rs = [reading(30 * i, 30 + i * 0.3, bat=12) for i in range(10)]
        a = health.assess(rs, self.NOW)
        self.assertEqual((a["status"], "low_battery" in a["issues"]), ("warning", True))

    def test_no_data(self):
        self.assertEqual(health.assess([], self.NOW)["issues"], ["no_data"])


class SavingsTests(unittest.TestCase):
    def test_baseline_and_summary(self):
        b = savings.baseline_litres(0.5, 10)
        self.assertAlmostEqual(b, 0.5 * 10000 * 0.15 * 4.0 * 10 / 0.9)
        s = savings.summarize(b, b / 2)
        self.assertEqual(s["saved_pct"], 50.0)

    def test_overuse_is_negative(self):
        self.assertLess(savings.summarize(1000, 1500)["saved_l"], 0)

    def test_zero_baseline(self):
        self.assertEqual(savings.summarize(0, 0)["saved_pct"], 0.0)


class I18nTests(unittest.TestCase):
    def test_all_languages_complete(self):
        for table in (i18n.UI, i18n.ALERTS):
            keys = set(table["en"])
            for lang in ("hi", "te"):
                self.assertEqual(keys, set(table[lang]), lang)

    def test_placeholders_match(self):
        import string
        f = string.Formatter()
        for table in (i18n.UI, i18n.ALERTS):
            for key, en in table["en"].items():
                want = {x[1] for x in f.parse(en) if x[1]}
                for lang in ("hi", "te"):
                    got = {x[1] for x in f.parse(table[lang][key]) if x[1]}
                    self.assertEqual(want, got, (lang, key))

    def test_format(self):
        self.assertIn("River", i18n.alert_text("hi", "dry_critical", field="River", v=12))
        self.assertEqual(i18n.ui("xx", "logout"), "Sign out")


class CleanReadingTests(unittest.TestCase):
    def test_clips_and_requires_moisture(self):
        r = clean_reading({"soil_moisture": 140, "air_temp": 80})
        self.assertEqual((r["soil_moisture"], r["air_temp"]), (100.0, 60.0))
        with self.assertRaises(ValueError):
            clean_reading({"air_temp": 20})

    def test_rejects_non_finite_sensor_values(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.assertRaises(ValueError):
                clean_reading({"soil_moisture": value})
            with self.assertRaises(ValueError):
                clean_reading({"soil_moisture": 30, "battery": value})


if __name__ == "__main__":
    unittest.main()
