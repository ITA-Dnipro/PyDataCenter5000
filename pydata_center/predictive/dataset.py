from datetime import timedelta
from typing import Tuple

import numpy as np
import pandas as pd
from django.utils import timezone
from monitoring.models import AgentMetric, TriggeredAlert


def fetch_raw_metrics(days: int = 7) -> pd.DataFrame:
    """
    Fetch all AgentMetric records from the past `days` days
    and return a DataFrame with the expected columns,
    even if there are no records.
    """
    cols = [
        'server_status_id',
        'timestamp',
        'cpu',
        'ram',
        'disk',
        'load_avg',
        'nginx_down_count',
        'uptime'
    ]
    since = timezone.now() - timedelta(days=days)
    qs = AgentMetric.objects.filter(timestamp__gte=since).values(*cols)
    df = pd.DataFrame.from_records(qs, columns=cols)

    if df.empty:
        return df

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(['server_status_id', 'timestamp'])
    return df


def build_datasets(
    df: pd.DataFrame,
    window: int = 5
) -> Tuple[
    Tuple[np.ndarray, np.ndarray],
    Tuple[np.ndarray, np.ndarray]
]:
    """
    Build regression and classification datasets from a raw metrics DataFrame.

    Regression dataset:
      - X_reg: ndarray of shape (n_samples, window * n_features)
      - y_reg: ndarray of shape (n_samples,)
      Target is cpu at t+1.

    Classification dataset:
      - X_clf: ndarray of shape (n_samples, window * n_features)
      - y_clf: ndarray of shape (n_samples,)
      Target is 1 if a TriggeredAlert exists at t+1, else 0.

    Args:
        df (pd.DataFrame): DataFrame returned by fetch_raw_metrics().
        window (int): Number of timesteps per sample window.

    Returns:
        Tuple:
            (X_reg, y_reg), (X_clf, y_clf)
    """
    X_reg, y_reg = [], []
    X_clf, y_clf = [], []

    for sid, group in df.groupby('server_status_id'):
        vals = group[
            ['cpu', 'ram', 'disk', 'load_avg', 'nginx_down_count', 'uptime']
        ].to_numpy()
        times = group['timestamp'].tolist()

        for i in range(len(vals) - window):
            window_X = vals[i: i + window]
            next_time = times[i + window]

            y_reg.append(vals[i + window + 0][0])
            X_reg.append(window_X.flatten())

            # Classification target: presence of TriggeredAlert at t+1
            has_alert = TriggeredAlert.objects.filter(
                rule__is_active=True,
                triggered_at__date=next_time.date(),
                triggered_at__hour=next_time.hour,
                triggered_at__minute=next_time.minute
            ).exists()
            y_clf.append(1 if has_alert else 0)
            X_clf.append(window_X.flatten())

    return (
        np.array(X_reg), np.array(y_reg),
        np.array(X_clf), np.array(y_clf)
    )


if __name__ == '__main__':
    df = fetch_raw_metrics(days=7)
    (X_reg, y_reg), (X_clf, y_clf) = build_datasets(df, window=5)
    print('Regression samples:', X_reg.shape, y_reg.shape)
    print('Classification samples:', X_clf.shape, y_clf.shape)
