import logging
from datetime import datetime

import joblib

logger = logging.getLogger(__name__)


def save_model(model, path: str, model_name: str = None) -> None:
    """
    Serialize `model` to `path` with joblib.
    If `model_name` is given, log where it was written.
    """
    joblib.dump(model, path)
    if model_name:
        logger.info(f'{model_name} model saved to {path}')


def load_model(path: str):
    """
    Load a model from the given path using joblib.
    """
    return joblib.load(path)
