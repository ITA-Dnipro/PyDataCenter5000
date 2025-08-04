import os

import numpy as np
from predictive.models.model_io import load_model

# Path to the folder where models are saved
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

# Load regression model for CPU forecast
CPU_MODEL_PATH = os.path.join(MODEL_DIR, 'cpu_forecast.pkl')
cpu_model = load_model(CPU_MODEL_PATH)

# Load unsupervised anomaly detection model
ISO_MODEL_PATH = os.path.join(MODEL_DIR, 'iso_anomaly.pkl')
iso_model = load_model(ISO_MODEL_PATH)


def forecast_cpu(windowed_features: np.ndarray) -> float:
    arr = np.asarray(windowed_features).reshape(1, -1)
    return float(cpu_model.predict(arr)[0])


def detect_anomaly(windowed_features: np.ndarray) -> bool:
    arr = np.asarray(windowed_features).reshape(1, -1)
    return iso_model.predict(arr)[0] == -1
