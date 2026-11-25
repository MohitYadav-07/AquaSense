"""Create a synthetic soil-moisture dataset that mimics drying behaviour.
Replace with real sensor exports once your field data accumulates."""
import numpy as np, pandas as pd
from features import FEATURES, build_row

rng = np.random.default_rng(42)


def simulate(n_days=240, step_h=0.5):
    rows, m = [], 34.0
    prev = m
    steps = int(n_days * 24 / step_h)
    for i in range(steps):
        hour = (i * step_h) % 24
        day_heat = np.sin((hour - 6) / 24 * 2 * np.pi)
        air = 28 + 8 * day_heat + rng.normal(0, 1.2)
        hum = np.clip(55 - 20 * day_heat + rng.normal(0, 4), 15, 95)
        soil = air - 3 + rng.normal(0, 0.6)
        rows.append(build_row(m, soil, air, hum, hour, prev) + [m])
        prev = m
        evap = max(0.0, 0.05 + 0.012 * (air - 20) + 0.003 * (60 - hum)) * step_h * 3
        m -= evap
        if rng.random() < 0.004:  m += rng.uniform(6, 16)   # rain
        if m < 22:                m += rng.uniform(10, 14)  # farmer irrigates
        m = float(np.clip(m + rng.normal(0, 0.05), 5, 60))
    df = pd.DataFrame(rows, columns=FEATURES + ["moisture_now"])
    horizon = int(6 / step_h)
    df["target_6h"] = df["moisture_now"].shift(-horizon)   # label: moisture 6h ahead
    return df.dropna().drop(columns=["moisture_now"])


if __name__ == "__main__":
    df = simulate()
    df.to_csv("training_data.csv", index=False)
    print("rows:", len(df))
