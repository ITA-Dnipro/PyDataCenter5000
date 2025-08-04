import numpy as np
from sklearn.ensemble import (IsolationForest, RandomForestClassifier,
                              RandomForestRegressor)
from sklearn.metrics import classification_report, mean_squared_error
from sklearn.model_selection import train_test_split

from pydata_center.utils.logger import setup_logger

logger = setup_logger()


def train_regression_model(
        X: np.ndarray, y: np.ndarray, test_size: float = 0.2
) -> tuple:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    rmse = mean_squared_error(y_test, preds, squared=False)
    logger.info(f'Regression RMSE: {rmse:.3f}')
    return model, {'rmse': rmse}


def train_anomaly_model(
        X: np.ndarray, contamination: float
) -> IsolationForest:
    model = IsolationForest(contamination=contamination, random_state=42)
    model.fit(X)
    return model


def train_classification_model(
        X: np.ndarray, y: np.ndarray, test_size: float = 0.2
) -> tuple:
    if len(np.unique(y)) < 2:
        logger.warning(
            'Classification stratification failed: not enough label diversity'
        )
        return None, {}

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=y
    )
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train)
    preds = clf.predict(X_test)
    report = classification_report(y_test, preds, output_dict=True)
    logger.info(
        'Classification report:\n' + classification_report(y_test, preds)
    )
    return clf, {'accuracy': report.get('accuracy', 0)}


def train_all_models(
    X_reg: np.ndarray, y_reg: np.ndarray,
    X_clf: np.ndarray, y_clf: np.ndarray,
    contamination: float,
    test_size: float = 0.2
) -> tuple:
    models = {}
    metrics = {}

    if len(y_reg) > 0:
        model, reg_metrics = train_regression_model(X_reg, y_reg, test_size)
        models['regression'] = model
        metrics['regression'] = reg_metrics
    else:
        logger.warning('Not enough data for regression model.')

    if len(X_clf) > 0:
        models['anomaly'] = train_anomaly_model(X_clf, contamination)
        metrics['anomaly'] = {}

        if np.any(y_clf == 1):
            clf_model, clf_metrics = train_classification_model(
                X_clf, y_clf, test_size
            )
            if clf_model:
                models['classifier'] = clf_model
                metrics['classifier'] = clf_metrics
        else:
            logger.warning('No positive labels for supervised classification.')
    else:
        logger.warning('Not enough data for anomaly models.')

    return models, metrics
