import os, subprocess, sys, unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def run(code, tz=None, sub="api"):
    # api/ and dashboard/ each have their own `config`, so they must never share a path
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([ROOT, os.path.join(ROOT, sub)]))
    env.pop("APP_TIMEZONE", None)
    if tz:
        env["APP_TIMEZONE"] = tz
    return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, cwd=ROOT).stdout.strip()


class TimezoneTests(unittest.TestCase):
    """The API and the dashboard must use the same clock or every reading looks hours old."""

    API = "import config, datetime; print(config.APP_TZ, datetime.datetime.now().astimezone().utcoffset().total_seconds())"
    DJ = ("import os; os.environ['DJANGO_SETTINGS_MODULE']='config.settings'; import django; django.setup();"
          "from django.conf import settings; import datetime; print(settings.TIME_ZONE, datetime.datetime.now().astimezone().utcoffset().total_seconds())")

    def test_defaults_agree(self):
        self.assertEqual(run(self.API), run(self.DJ, sub="dashboard"))

    def test_override_applies_to_both(self):
        for tz, off in (("Africa/Nairobi", "10800.0"), ("UTC", "0.0")):
            self.assertEqual(run(self.API, tz), "%s %s" % (tz, off))
            self.assertEqual(run(self.DJ, tz, "dashboard"), "%s %s" % (tz, off))


if __name__ == "__main__":
    unittest.main()
