import os

import joblib
import numpy as np

# Path to the folder where models are saved
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

# Load regression model for CPU forecast
CPU_MODEL_PATH = os.path.join(MODEL_DIR, 'cpu_forecast.pkl')
cpu_model = joblib.load(CPU_MODEL_PATH)

# Load unsupervised anomaly detection model
ISO_MODEL_PATH = os.path.join(MODEL_DIR, 'iso_anomaly.pkl')
iso_model = joblib.load(ISO_MODEL_PATH)


def forecast_cpu(windowed_features: np.ndarray) -> float:
    """
    Predict the next CPU value given the last window of features.
    """
    arr = np.asarray(windowed_features).reshape(1, -1)
    return float(cpu_model.predict(arr)[0])


def detect_anomaly(windowed_features: np.ndarray) -> bool:
    """
    Use IsolationForest to detect if the given window is anomalous.
    """
    arr = np.asarray(windowed_features).reshape(1, -1)
    return iso_model.predict(arr)[0] == -1
