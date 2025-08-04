from datetime import timedelta
from typing import Literal, Tuple

import numpy as np
import pandas as pd
from django.utils import timezone
from monitoring.models import AgentMetric, TriggeredAlert
from sklearn.preprocessing import StandardScaler


class MetricsDataset:
    """
    A wrapper for raw metric data that provides methods for loading,
    handling missing values, and generating training sequences.
    """

    def __init__(self, df: pd.DataFrame):
        """
        Initialize the dataset with a given DataFrame.

        Args:
            df (pd.DataFrame): Raw input DataFrame with metric values.
        """
        self.df = df.copy()

    @classmethod
    def from_db(cls, days: int = 7) -> 'MetricsDataset':
        """
        Load metric data from the database for the past N days.

        Args:
            days (int): Number of days to look back from the current time.

        Returns:
            MetricsDataset: An instance containing the loaded and sorted data.
        """
        cols = [
            'server_status_id', 'timestamp', 'cpu', 'ram',
            'disk', 'load_avg', 'nginx_down_count', 'uptime'
        ]
        since = timezone.now() - timedelta(days=days)
        qs = AgentMetric.objects.filter(timestamp__gte=since).values(*cols)
        df = pd.DataFrame.from_records(qs, columns=cols)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values(['server_status_id', 'timestamp'])
        return cls(df)

    @classmethod
    def from_csv(cls, path: str, **read_csv_kwargs) -> 'MetricsDataset':
        """
        Load metric data from a CSV file (e.g., from Kaggle).

        Args:
            path (str): Path to the CSV file.
            **read_csv_kwargs: Additional arguments for pandas.read_csv.

        Returns:
            MetricsDataset: Dataset instance containing the loaded CSV data.
        """
        df = pd.read_csv(path, parse_dates=['timestamp'], **read_csv_kwargs)
        return cls(df)

    def handle_missing(
        self, method: Literal['drop', 'mean'] = 'drop'
    ) -> 'MetricsDataset':
        """
        Handle missing values in the dataset.

        Args:
            method (str): How to handle missing values.
                          'drop' — remove rows with NaNs;
                          'mean' — fill NaNs with column means.

        Returns:
            MetricsDataset: The current instance (for method chaining).
        """
        if method == 'drop':
            self.df = self.df.dropna()
        else:
            self.df = self.df.fillna(self.df.mean(numeric_only=True))
        return self

    def create_sequences(
        self,
        window: int = 5,
        scale: bool = False,
        alert_padding_sec: int = 30
    ) -> 'SequenceBuilder':
        """
        Create windowed sequences for forecasting and classification.

        Args:
            window (int): Number of past time steps to include per sample.
            scale (bool): Whether to apply StandardScaler to features.
            alert_padding_sec (int): Time window (in seconds) around a
                                     prediction point to check for alerts.

        Returns:
            SequenceBuilder: Helper object for exporting ML-ready sequences.
        """
        return SequenceBuilder(
            df=self.df,
            window=window,
            scale=scale,
            alert_padding_sec=alert_padding_sec
        )


class SequenceBuilder:
    """
    Constructs windowed sequences from metric data for machine learning.
    Supports both regression (CPU forecast) and binary classification (alert).
    """

    def __init__(
        self,
        df: pd.DataFrame,
        window: int,
        scale: bool,
        alert_padding_sec: int
    ):
        """
        Initialize a SequenceBuilder with given parameters.

        Args:
            df (pd.DataFrame): Input metric data.
            window (int): Number of time steps in each sample window.
            scale (bool): Whether to normalize features using StandardScaler.
            alert_padding_sec (int): Number of seconds around each sample
                                     to detect alert correlation.
        """
        self.df = df
        self.window = window
        self.scale = scale
        self.alert_padding = timedelta(seconds=alert_padding_sec)

    def to_numpy(self) -> Tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray
    ]:
        """
        Convert the dataset into NumPy arrays for ML training.

        Returns:
            Tuple containing:
              - X_reg (np.ndarray): Features for regression
              - y_reg (np.ndarray): CPU target values
              - X_clf (np.ndarray): Features for classification
              - y_clf (np.ndarray): Binary alert labels
        """
        X_reg, y_reg, X_clf, y_clf = [], [], [], []

        alerts = TriggeredAlert.objects \
            .filter(rule__is_active=True) \
            .values_list('triggered_at', flat=True)
        alert_times = np.array(list(alerts), dtype='datetime64[ns]')

        for sid, grp in self.df.groupby('server_status_id'):
            vals = grp[[
                'cpu', 'ram', 'disk', 'load_avg', 'nginx_down_count', 'uptime'
            ]].to_numpy()
            times = grp['timestamp'].tolist()

            for i in range(len(vals) - self.window):
                window_X = vals[i: i + self.window].flatten()
                next_time = times[i + self.window]

                # Regression target: next-step CPU
                X_reg.append(window_X)
                y_reg.append(vals[i + self.window][0])

                # Classification target: is there an alert around next_time?
                start = next_time - self.alert_padding
                end = next_time + self.alert_padding
                has_alert = np.any(
                    (alert_times >= start) & (alert_times <= end)
                )
                X_clf.append(window_X)
                y_clf.append(1 if has_alert else 0)

        X_reg = np.array(X_reg)
        y_reg = np.array(y_reg)
        X_clf = np.array(X_clf)
        y_clf = np.array(y_clf)

        if self.scale:
            scaler = StandardScaler()
            X_reg = scaler.fit_transform(X_reg)
            X_clf = scaler.fit_transform(X_clf)

        return X_reg, y_reg, X_clf, y_clf

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert windowed sequences to a single pandas DataFrame.

        Columns include:
          - feat_0, feat_1, ..., feat_N: input features
          - target_reg: CPU regression target
          - target_clf: binary classification label (alert presence)

        Returns:
            pd.DataFrame: Combined features and targets.
        """
        X_reg, y_reg, X_clf, y_clf = self.to_numpy()
        n_feats = X_reg.shape[1]
        col_names = [f'feat_{i}' for i in range(n_feats)]

        df_reg = pd.DataFrame(X_reg, columns=col_names)
        df_reg['target_reg'] = y_reg

        df_clf = pd.DataFrame(X_clf, columns=col_names)
        df_clf['target_clf'] = y_clf

        return pd.concat([df_reg, df_clf], axis=1)
