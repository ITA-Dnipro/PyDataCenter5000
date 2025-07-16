import argparse
import json
import os

import django
import numpy as np
from django.conf import settings
from predictive.dataset import build_datasets, fetch_raw_metrics
from predictive.logger import setup_logger
from predictive.models.model_io import save_model
from predictive.models.training import train_all_models

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pydata_center.settings')
django.setup()

logger = setup_logger()


def prepare_model_dir() -> str:
    model_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(model_dir, exist_ok=True)
    return model_dir


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
    parser.add_argument(
        '--test-size', type=float, default=0.2, help='Test split ratio'
    )
    parser.add_argument(
        '--metrics-out', type=str, default=None,
        help='Optional path to save training metrics JSON'
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

    models, metrics = train_all_models(
        X_reg, y_reg, X_clf, y_clf,
        contamination=args.contamination,
        test_size=args.test_size
    )

    for key, model in models.items():
        save_model(model, MODEL_PATHS[key])

    if args.metrics_out:
        with open(args.metrics_out, 'w') as f:
            json.dump(metrics, f, indent=2)
        logger.info(f'Metrics saved to {args.metrics_out}')


if __name__ == '__main__':
    main()
