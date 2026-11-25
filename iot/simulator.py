"""Simulates soil-moisture sensors posting to the Flask API.
Usage: python iot/simulator.py [--interval 5] [--backfill 48]"""
import argparse, math, os, random, time
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
BASE = os.getenv("API_URL", "http://127.0.0.1:5001")
URL = BASE + "/api/readings"
KEY = os.getenv("API_KEY", "")
DEVICES = {"SM-NT-001": 31.0, "SM-RB-002": 36.0, "SM-HP-003": 27.0}


def payload(code, m, tick):
    hour = (tick * 0.5) % 24
    heat = math.sin((hour - 6) / 24 * 2 * math.pi)
    air = 28 + 8 * heat + random.gauss(0, 0.8)
    return {"device_code": code, "soil_moisture": round(m, 2), "soil_temp": round(air - 3, 2),
            "air_temp": round(air, 2), "humidity": round(55 - 20 * heat + random.gauss(0, 3), 1),
            "battery": round(max(5, 98 - tick * 0.05), 1)}


def poll_valve(code, state):
    """Behave like the ESP32 valve controller: ask for a command, 'water', then acknowledge."""
    h = {"X-API-Key": KEY}
    try:
        c = requests.get("%s/api/devices/%s/command" % (BASE, code), headers=h, timeout=8).json()
        if c.get("action") == "open":
            state[code] += min(16.0, c["minutes"] * 0.12)
            print(code, "valve OPEN for", c["minutes"], "min -> moisture", round(state[code], 1))
            requests.post("%s/api/devices/%s/ack" % (BASE, code), json={"ref": c["ref"], "status": "done"}, headers=h, timeout=8)
    except (requests.RequestException, ValueError):
        pass


if __name__ == "__main__":
    if not KEY:
        raise SystemExit("Set API_KEY in .env before starting the simulator.")
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=float, default=5)
    ap.add_argument("--backfill", type=int, default=0, help="send N quick readings first")
    ap.add_argument("--device", action="append", default=[], help="extra device_code to simulate (repeatable)")
    a = ap.parse_args()
    state, tick = dict(DEVICES), 0
    for code in a.device:
        state[code] = 30.0
    while True:
        for code in state:
            hour = (tick * 0.5) % 24
            state[code] -= max(0.05, 0.12 + 0.01 * (math.sin((hour - 6) / 24 * 2 * math.pi))) + random.random() * 0.1
            if state[code] < 20:
                state[code] += random.uniform(12, 16)   # pretend irrigation happened
            try:
                r = requests.post(URL, json=payload(code, state[code], tick), headers={"X-API-Key": KEY}, timeout=8)
                print(code, round(state[code], 1), r.status_code, r.json())
            except requests.RequestException as exc:
                print("send failed:", exc)
            poll_valve(code, state)
        tick += 1
        if tick > a.backfill:
            time.sleep(a.interval)
