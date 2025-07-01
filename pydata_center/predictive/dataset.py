from datetime import timedelta
from typing import Literal, Tuple

import numpy as np
import pandas as pd
from django.utils import timezone
from monitoring.models import AgentMetric, TriggeredAlert
from sklearn.preprocessing import StandardScaler


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
    window: int = 5,
    scale: bool = False,
    missing: Literal['drop', 'mean'] = 'drop'
) -> Tuple[
    Tuple[np.ndarray, np.ndarray],
    Tuple[np.ndarray, np.ndarray]
]:
    if missing == 'drop':
        df = df.dropna()
    elif missing == 'mean':
        df = df.fillna(df.mean(numeric_only=True))

    X_reg, y_reg = [], []
    X_clf, y_clf = [], []

    all_alerts = TriggeredAlert.objects.filter(
        rule__is_active=True
    ).values_list('triggered_at', flat=True)

    alert_times = np.array(list(all_alerts), dtype='datetime64[ns]')

    for sid, group in df.groupby('server_status_id'):
        vals = group[
            ['cpu', 'ram', 'disk', 'load_avg', 'nginx_down_count', 'uptime']
        ].to_numpy()
        times = group['timestamp'].tolist()

        for i in range(len(vals) - window):
            window_X = vals[i: i + window]
            next_time = times[i + window]

            y_reg.append(vals[i + window][0])
            X_reg.append(window_X.flatten())

            t_start = next_time - timedelta(seconds=30)
            t_end = next_time + timedelta(seconds=30)
            has_alert = np.any(
                (alert_times >= t_start) & (alert_times <= t_end)
            )

            y_clf.append(1 if has_alert else 0)
            X_clf.append(window_X.flatten())

    X_reg = np.array(X_reg)
    X_clf = np.array(X_clf)

    if scale:
        scaler = StandardScaler()
        X_reg = scaler.fit_transform(X_reg)
        X_clf = scaler.fit_transform(X_clf)

    return (
        X_reg, np.array(y_reg),
        X_clf, np.array(y_clf)
    )


if __name__ == '__main__':
    df = fetch_raw_metrics(days=7)
    (X_reg, y_reg), (X_clf, y_clf) = build_datasets(df, window=5)
    print('Regression samples:', X_reg.shape, y_reg.shape)
    print('Classification samples:', X_clf.shape, y_clf.shape)
