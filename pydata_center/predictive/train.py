import argparse
import os

import django
import joblib
import numpy as np
from predictive.dataset import build_datasets, fetch_raw_metrics
from predictive.logger import setup_logger
from sklearn.ensemble import (IsolationForest, RandomForestClassifier,
                              RandomForestRegressor)
from sklearn.metrics import classification_report, mean_squared_error
from sklearn.model_selection import train_test_split

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pydata_center.settings')
django.setup()

logger = setup_logger()


def prepare_model_dir() -> str:
    model_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(model_dir, exist_ok=True)
    return model_dir


def save_model(model, path: str):
    joblib.dump(model, path)
    logger.info(f'Saved model to {os.path.basename(path)}')


def train_regression_model(
        X: np.ndarray,
        y: np.ndarray
) -> RandomForestRegressor:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    rmse = mean_squared_error(y_test, preds, squared=False)
    logger.info(f'Regression RMSE: {rmse:.3f}')
    return model


def train_anomaly_model(
        X: np.ndarray, contamination: float
) -> IsolationForest:
    model = IsolationForest(contamination=contamination, random_state=42)
    model.fit(X)
    return model


def train_classification_model(X: np.ndarray, y: np.ndarray):
    if len(np.unique(y)) < 2:
        logger.warning(
            'Classification stratification failed: not enough label diversity'
        )
        return None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    preds = clf.predict(X_test)
    logger.info(
        'Classification report:\n' + classification_report(y_test, preds)
    )
    return clf


def parse_args():
    parser = argparse.ArgumentParser(description='Train predictive models')
    parser.add_argument(
        '--days', type=int, default=7, help='How many days of metrics to use'
    )
    parser.add_argument(
        '--window', type=int, default=5, help='Sliding window size'
    )
    parser.add_argument(
        '--contamination', type=float,
        default=0.05, help='IsolationForest contamination level'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    model_dir = prepare_model_dir()

    MODEL_PATHS = {
        'regression': os.path.join(model_dir, 'cpu_forecast.pkl'),
        'anomaly': os.path.join(model_dir, 'iso_anomaly.pkl'),
        'classifier': os.path.join(model_dir, 'anom_classifier.pkl')
    }

    df = fetch_raw_metrics(days=args.days)
    (X_reg, y_reg), (X_clf, y_clf) = build_datasets(df, window=args.window)

    if len(y_reg) > 0:
        reg_model = train_regression_model(X_reg, y_reg)
        save_model(reg_model, MODEL_PATHS['regression'])
    else:
        logger.warning('Not enough data for regression model.')

    if len(X_clf) > 0:
        iso_model = train_anomaly_model(
            X_clf, contamination=args.contamination
        )
        save_model(iso_model, MODEL_PATHS['anomaly'])

        if np.any(y_clf == 1):
            clf_model = train_classification_model(X_clf, y_clf)
            if clf_model:
                save_model(clf_model, MODEL_PATHS['classifier'])
        else:
            logger.warning('No positive labels for supervised classification.')
    else:
        logger.warning('Not enough data for anomaly models.')


if __name__ == '__main__':
    main()
