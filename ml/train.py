"""Train the 6-hour soil-moisture forecaster (TensorFlow / Keras)."""
import json, os
import numpy as np, tensorflow as tf
from generate_data import simulate
from features import FEATURES

OUT = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(OUT, exist_ok=True)
tf.keras.utils.set_random_seed(7)

df = simulate()
X, y = df[FEATURES].values.astype("float32"), df["target_6h"].values.astype("float32")
mean, std = X.mean(0), X.std(0) + 1e-6
Xn = (X - mean) / std

split = int(len(Xn) * 0.85)          # time-ordered split, no leakage
Xtr, Xte, ytr, yte = Xn[:split], Xn[split:], y[:split], y[split:]

model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(len(FEATURES),)),
    tf.keras.layers.Dense(64, activation="relu"),
    tf.keras.layers.Dense(32, activation="relu"),
    tf.keras.layers.Dense(1),
])
model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="mse", metrics=["mae"])
model.fit(Xtr, ytr, validation_split=0.1, epochs=25, batch_size=128, verbose=2,
          callbacks=[tf.keras.callbacks.EarlyStopping(patience=4, restore_best_weights=True)])

loss, mae = model.evaluate(Xte, yte, verbose=0)
print("test MAE (moisture %%): %.3f" % mae)

model.save(os.path.join(OUT, "moisture_model.keras"))
with open(os.path.join(OUT, "scaler.json"), "w") as f:
    json.dump({"mean": mean.tolist(), "std": std.tolist(), "mae": float(mae)}, f)
print("saved to", OUT)
