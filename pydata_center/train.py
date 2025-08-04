import argparse
import datetime
import json
import os

import django
import numpy as np
from data.dataset import build_datasets, fetch_raw_metrics
from django.conf import settings
from predictive.forecasting import (train_anomaly_model,
                                    train_classification_model,
                                    train_regression_model)
from predictive.models.model_io import save_model

from pydata_center.utils.logger import setup_logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pydata_center.settings')
django.setup()

logger = setup_logger()

AVAILABLE_MODELS = ['regression', 'anomaly', 'classifier']


def prepare_model_dir(output_dir: str | None) -> str:
    """
    Determine where to write model files.
    If `output_dir` is provided, use that; otherwise
    default to BASE_DIR/predictive/models.
    """
    if output_dir:
        model_dir = output_dir
    else:
        model_dir = os.path.join(settings.BASE_DIR, 'predictive', 'models')
    os.makedirs(model_dir, exist_ok=True)
    return model_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Train predictive models')
    parser.add_argument(
        '--days', type=int, default=7,
        help='How many days of metrics to use'
    )
    parser.add_argument(
        '--window', type=int, default=5,
        help='Sliding window size'
    )
    parser.add_argument(
        '--contamination', type=float, default=0.05,
        help='IsolationForest contamination level'
    )
    parser.add_argument(
        '--test-size', type=float, default=0.2,
        help='Test split ratio'
    )
    parser.add_argument(
        '--metrics-out', type=str, default=None,
        help='Optional path to save training metrics JSON'
    )
    parser.add_argument(
        '--model-types', nargs='*', default=AVAILABLE_MODELS,
        choices=AVAILABLE_MODELS,
        help='Which models to train'
    )
    parser.add_argument(
        '--output-dir', type=str, default=None,
        help='Where to save trained model files'
    )
    return parser.parse_args()


def train_models(
    X_reg: np.ndarray, y_reg: np.ndarray,
    X_clf: np.ndarray, y_clf: np.ndarray,
    contamination: float, test_size: float,
    model_types: list[str]
) -> dict[str, tuple]:
    """
    Train only the requested model types and return a dict:
      {
        'regression': (model, metrics),
        'anomaly':    (model, {}),
        'classifier': (model, metrics),
      }
    """
    results: dict[str, tuple] = {}

    if 'regression' in model_types and len(y_reg) > 0:
        results['regression'] = train_regression_model(X_reg, y_reg, test_size)

    if 'anomaly' in model_types and len(X_clf) > 0:
        # anomaly only
        results['anomaly'] = (train_anomaly_model(X_clf, contamination), {})

    if 'classifier' in model_types and len(y_clf) > 0 and np.any(y_clf == 1):
        results['classifier'] = train_classification_model(
            X_clf, y_clf, test_size
        )

    return results


def main():
    args = parse_args()
    model_dir = prepare_model_dir(args.output_dir)

    # 1) load & preprocess
    df = fetch_raw_metrics(days=args.days)
    (X_reg, y_reg), (X_clf, y_clf) = build_datasets(
        df,
        window=args.window,
        scale=False,       # or make this another CLI flag if you want
        missing='drop'     # or 'mean'
    )

    # 2) train requested models
    trained = train_models(
        X_reg, y_reg, X_clf, y_clf,
        contamination=args.contamination,
        test_size=args.test_size,
        model_types=args.model_types
    )

    # 3) save models with versioned filenames
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for name, (model, _) in trained.items():
        filename = f'{name}_{timestamp}.pkl'
        path = os.path.join(model_dir, filename)
        save_model(model, path, model_name=name)

    # 4) optionally write out metrics JSON
    if args.metrics_out:
        # collect just the metrics dicts
        metrics = {n: m for n, (_, m) in trained.items()}
        with open(args.metrics_out, 'w') as f:
            json.dump(metrics, f, indent=2)
        logger.info(f'Training metrics written to {args.metrics_out}')


if __name__ == '__main__':
    main()
