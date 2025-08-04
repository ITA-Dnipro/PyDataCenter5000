import os

import numpy as np
from predictive.models.model_io import load_model


class Predictor:
    def __init__(self):
        model_dir = os.path.join(os.path.dirname(__file__), 'models')
        self.cpu_model = load_model(
            os.path.join(model_dir, 'cpu_forecast.pkl')
        )
        self.iso_model = load_model(os.path.join(model_dir, 'iso_anomaly.pkl'))

    def forecast_cpu(self, windowed_features: np.ndarray) -> float:
        """
        Predict the next CPU value given the last window of features.
        """
        arr = np.asarray(windowed_features).reshape(1, -1)
        return float(self.cpu_model.predict(arr)[0])

    def detect_anomaly(self, windowed_features: np.ndarray) -> bool:
        """
        Use IsolationForest to detect if the given window is anomalous.
        """
        arr = np.asarray(windowed_features).reshape(1, -1)
        return self.iso_model.predict(arr)[0] == -1
