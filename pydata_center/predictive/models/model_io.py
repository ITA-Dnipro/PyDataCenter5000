import joblib


def save_model(model, path: str) -> None:
    """
    Save model to the given file path using joblib.
    """
    joblib.dump(model, path)


def load_model(path: str):
    """
    Load model from the given file path using joblib.
    """
    return joblib.load(path)
