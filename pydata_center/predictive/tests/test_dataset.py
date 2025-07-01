from datetime import timedelta

import numpy as np
import pandas as pd
import pytest
from django.utils import timezone
from monitoring.models import (AgentMetric, AlertRule, ServerStatus,
                               TriggeredAlert)
from predictive.dataset import build_datasets, fetch_raw_metrics


@pytest.mark.django_db
def test_fetch_raw_metrics_returns_dataframe_with_expected_columns():
    """fetch_raw_metrics should return a
    DataFrame with the correct columns."""
    now = timezone.now()
    ss = ServerStatus.objects.create(
        hostname='test-server',
        ip='127.0.0.1',
        uptime=0.0,
        timestamp=now,
        os='Linux',
        server_name='test',
        healthy=True
    )
    AgentMetric.objects.create(
        server_status=ss,
        timestamp=now,
        cpu=42.0,
        ram=10.0,
        disk=5.0,
        load_avg=0.5,
        nginx_down_count=0,
        uptime=1.0
    )

    df = fetch_raw_metrics(days=1)
    expected_cols = [
        'server_status_id',
        'timestamp',
        'cpu',
        'ram',
        'disk',
        'load_avg',
        'nginx_down_count',
        'uptime'
    ]
    assert isinstance(df, pd.DataFrame)
    assert df.columns.tolist() == expected_cols
    assert len(df) >= 1
    assert float(df.iloc[0]['cpu']) == 42.0


@pytest.mark.django_db
def test_build_datasets_shapes_and_values_when_no_alerts():
    """build_datasets should return correct
    numpy arrays when there are no alerts."""
    now = timezone.now()
    ss = ServerStatus.objects.create(
        hostname='test-server2',
        ip='127.0.0.2',
        uptime=0.0,
        timestamp=now,
        os='Linux',
        server_name='test2',
        healthy=True
    )
    for i in range(6):
        AgentMetric.objects.create(
            server_status=ss,
            timestamp=now + timedelta(seconds=i),
            cpu=10 * i,
            ram=20 + i,
            disk=30 + i,
            load_avg=1.0 + 0.1 * i,
            nginx_down_count=0,
            uptime=100 + i
        )

    assert TriggeredAlert.objects.count() == 0

    df = fetch_raw_metrics(days=1)
    (X_reg, y_reg), (X_clf, y_clf) = build_datasets(df, window=5)

    assert isinstance(X_reg, np.ndarray)
    assert isinstance(y_reg, np.ndarray)
    assert isinstance(X_clf, np.ndarray)
    assert isinstance(y_clf, np.ndarray)

    assert X_reg.shape == (1, 5 * 6)
    assert y_reg.shape == (1,)
    assert X_clf.shape == (1, 5 * 6)
    assert y_clf.shape == (1,)

    assert y_reg[0] == pytest.approx(50.0)
    assert y_clf[0] == 0


@pytest.mark.django_db
def test_build_datasets_detects_triggered_alerts():
    """build_datasets should set y_clf to 1
    when a TriggeredAlert exists at t+1."""
    now = timezone.now()
    ss = ServerStatus.objects.create(
        hostname='test-server3',
        ip='127.0.0.3',
        uptime=0.0,
        timestamp=now,
        os='Linux',
        server_name='test3',
        healthy=True
    )
    for i in range(6):
        AgentMetric.objects.create(
            server_status=ss,
            timestamp=now + timedelta(seconds=i),
            cpu=5 * i,
            ram=10 + i,
            disk=15 + i,
            load_avg=0.5 * i,
            nginx_down_count=0,
            uptime=50 + i
        )
    rule = AlertRule.objects.create(
        metric='cpu',
        operator='>',
        threshold=0,
        time_window_minutes=1,
        frequency=1,
        is_active=True,
        hostname=None,
        notify_message='Test alert'
    )
    triggered_time = now + timedelta(seconds=5)
    TriggeredAlert.objects.create(
        rule=rule,
        message='Alert!',
        triggered_at=triggered_time
    )

    df = fetch_raw_metrics(days=1)
    (Xr, yr), (Xc, yc) = build_datasets(df, window=5)

    assert yc[0] == 1
