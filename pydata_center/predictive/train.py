import os

import django
import joblib
import numpy as np
from predictive.dataset import build_datasets, fetch_raw_metrics
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.metrics import classification_report, mean_squared_error
from sklearn.model_selection import train_test_split

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pydata_center.settings')
django.setup()

MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')
os.makedirs(MODEL_DIR, exist_ok=True)


def train_regression_model(
        X: np.ndarray,
        y: np.ndarray
) -> RandomForestRegressor:
    """
    Train a RandomForestRegressor on the provided data.
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    rmse = mean_squared_error(y_test, preds, squared=False)
    print(f'Regression RMSE: {rmse:.3f}')
    return model


def train_anomaly_model(X: np.ndarray) -> IsolationForest:
    """
    Train an IsolationForest for anomaly
    detection on the feature matrix.
    """
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(X)
    return model


def train_classification_model(X: np.ndarray, y: np.ndarray):
    """
    Train a RandomForestClassifier
    for anomaly classification.
    """
    from sklearn.ensemble import RandomForestClassifier
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    preds = clf.predict(X_test)
    print('Classification report:')
    print(classification_report(y_test, preds))
    return clf


def main():
    # Fetch and build datasets
    df = fetch_raw_metrics(days=7)
    (X_reg, y_reg), (X_clf, y_clf) = build_datasets(df, window=5)

    # Train regression model
    if len(y_reg) > 0:
        reg_model = train_regression_model(X_reg, y_reg)
        joblib.dump(reg_model, os.path.join(MODEL_DIR, 'cpu_forecast.pkl'))
        print('Saved regression model to cpu_forecast.pkl')
    else:
        print('Not enough data for regression model.')

    # Train anomaly detection
    if len(X_clf) > 0:
        iso_model = train_anomaly_model(X_clf)
        joblib.dump(iso_model, os.path.join(MODEL_DIR, 'iso_anomaly.pkl'))
        print('Saved IsolationForest model to iso_anomaly.pkl')

        # supervised classification (optional)
        if np.any(y_clf == 1):
            clf_model = train_classification_model(X_clf, y_clf)
            joblib.dump(
                clf_model, os.path.join(MODEL_DIR, 'anom_classifier.pkl')
            )
            print('Saved classifier model to anom_classifier.pkl')
        else:
            print('No positive labels for supervised classification.')
    else:
        print('Not enough data for anomaly models.')


if __name__ == '__main__':
    main()
