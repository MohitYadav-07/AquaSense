import json, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ml"))
from features import build_row  # noqa: E402

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "ml", "models")


class Predictor:
    """Loads the TensorFlow model once; falls back to a physics-style heuristic if absent."""

    def __init__(self):
        self.model = None
        self.mae = None
        try:
            import tensorflow as tf
            self.model = tf.keras.models.load_model(os.path.join(MODEL_DIR, "moisture_model.keras"))
            with open(os.path.join(MODEL_DIR, "scaler.json")) as f:
                s = json.load(f)
            self.mean, self.std, self.mae = np.array(s["mean"]), np.array(s["std"]), s["mae"]
            print("[predictor] TensorFlow model loaded")
        except Exception as exc:  # model not trained yet
            print("[predictor] using heuristic fallback:", exc)

    @property
    def margin(self):
        """Approximate 90% forecast band half-width in moisture %-points."""
        return round(1.645 * 1.25 * self.mae, 1) if self.mae else 3.0

    @property
    def name(self):
        return "tensorflow-dense" if self.model is not None else "heuristic"

    def predict_6h(self, moisture, soil_temp, air_temp, humidity, hour, prev_moisture=None):
        soil_temp = 25.0 if soil_temp is None else soil_temp
        air_temp = 28.0 if air_temp is None else air_temp
        humidity = 50.0 if humidity is None else humidity
        if self.model is None:
            evap = max(0.0, 0.05 + 0.012 * (air_temp - 20) + 0.003 * (60 - humidity)) * 6 * 2
            return max(0.0, moisture - evap)
        x = (np.array([build_row(moisture, soil_temp, air_temp, humidity, hour, prev_moisture)],
                      dtype="float32") - self.mean) / self.std
        return float(np.clip(self.model.predict(x, verbose=0)[0][0], 0, 100))
