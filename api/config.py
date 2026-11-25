import os
import time
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# One clock for the whole system: timestamps are stored as naive local time, so the API and the
# Django dashboard must agree on the zone (Django applies TIME_ZONE the same way).
APP_TZ = os.getenv("APP_TIMEZONE", "Asia/Kolkata")
os.environ["TZ"] = APP_TZ
if hasattr(time, "tzset"):
    time.tzset()

DB = dict(host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", 3306)),
          user=os.getenv("MYSQL_USER", "aqua"), password=os.getenv("MYSQL_PASSWORD", "aqua_pass"),
          database=os.getenv("MYSQL_DB", "aquasense"), charset="utf8mb4", autocommit=True)
API_KEY = os.getenv("API_KEY", "")
