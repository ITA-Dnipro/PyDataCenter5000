from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache as django_cache
from django.utils import timezone
from model_bakery import baker
from monitoring.email import EmailMessage
from monitoring.models import AgentMetric, AlertRule, ServerStatus
from monitoring.tasks import evaluate_agent_alerts
from monitoring.webhook import DiscordMessage, SlackMessage

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache_and_settings(monkeypatch):
    """
    Clear the Django cache and override default
    alert destinations before each test.
    """
    django_cache.clear()
    monkeypatch.setattr('django.conf.settings.DEFAULT_ALERT_DESTINATIONS', [])
    yield


@pytest.fixture
def server():
    """
    Create a ServerStatus instance with all required fields.
    """
    return baker.make(
        ServerStatus,
        hostname='agent-01',
        ip='127.0.0.1',
        uptime=12.3,
        timestamp=timezone.now(),
        os='Linux',
        healthy=True,
        server_name='test-server',
    )


@pytest.fixture
def rule(server):
    """
    Create an active AlertRule for CPU usage above threshold.
    """
    return baker.make(
        AlertRule,
        is_active=True,
        metric='cpu',
        operator='>',
        threshold=50,
        time_window_minutes=5,
        frequency=1,
        notify_message='CPU too high',
        hostname=server.hostname,
    )


@pytest.fixture
def metric_above(server):
    """
    Create an AgentMetric instance that exceeds the CPU threshold.
    """
    return baker.make(
        AgentMetric,
        server_status=server,
        cpu=80.0,
        timestamp=timezone.now()
    )


def test_alert_triggers_and_sends_per_destination(
    rule, metric_above, celery_app, celery_worker
):
    """
    With batch=False, ensure dispatcher.send()
    is called separately for each destination,
    and that EmailMessage and SlackMessage carry the expected content.
    """
    with patch('monitoring.tasks.dispatcher.send') as mock_send:
        result = evaluate_agent_alerts(
            destinations=['email', 'slack'], batch=False
        )

    assert result is not None

    # Two destinations → two calls
    assert mock_send.call_count == 2

    # First call should be EmailMessage
    email_msg = mock_send.call_args_list[0][0][0]
    assert isinstance(email_msg, EmailMessage)
    assert 'CPU' in email_msg.subject
    assert 'too high' in email_msg.body

    # Second call should be SlackMessage
    slack_msg = mock_send.call_args_list[1][0][0]
    assert isinstance(slack_msg, SlackMessage)
    assert 'CPU' in slack_msg.content
    assert 'too high' in slack_msg.content


def test_alert_triggers_as_batch(
        rule, metric_above, celery_app, celery_worker
):
    """
    With batch=True, ensure alerts are sent in batch per each destination,
    and that both EmailMessage and DiscordMessage carry the batched summary.
    """
    with patch('monitoring.tasks.dispatcher.send') as mock_send:
        result = evaluate_agent_alerts(
            destinations=['email', 'discord'], batch=True
        )

    assert result is not None

    # Two destinations → two batch calls
    assert mock_send.call_count == 2

    # Email batch
    email_batch = mock_send.call_args_list[0][0][0]
    assert isinstance(email_batch, EmailMessage)
    assert email_batch.subject.startswith('1 Alert(s) Triggered')
    assert 'CPU too high' in email_batch.body

    # Discord batch
    discord_batch = mock_send.call_args_list[1][0][0]
    assert isinstance(discord_batch, DiscordMessage)
    assert discord_batch.content.startswith('1 Alert(s) Triggered')
    assert 'CPU too high' in discord_batch.content


def test_alert_handles_invalid_destination(
    rule, metric_above, celery_app, celery_worker, caplog
):
    """
    An unknown destination should be logged as an error without raising.
    """
    caplog.set_level('ERROR')
    result = evaluate_agent_alerts(destinations=['telegram'], batch=False)

    assert result is None
    assert 'Unknown alert destination telegram' in caplog.text


def test_no_active_rules_returns_none(celery_app, celery_worker):
    """
    If there are no active rules, the task should return None immediately.
    """
    result = evaluate_agent_alerts(destinations=[], batch=False)
    assert result is None


def test_multiple_rules_triggered_for_same_agent(
        server, celery_app, celery_worker
):
    """
    Given two active AlertRule objects for the
    same server with thresholds 50 and 75,
    and a single AgentMetric of cpu=80,
    evaluate_agent_alerts should send two alerts
    (one per rule) when batch=False.
    """
    baker.make(
        AlertRule,
        is_active=True,
        metric='cpu',
        operator='>',
        threshold=50,
        time_window_minutes=5,
        frequency=1,
        hostname=server.hostname
    )
    baker.make(
        AlertRule,
        is_active=True,
        metric='cpu',
        operator='>',
        threshold=75,
        time_window_minutes=5,
        frequency=1,
        hostname=server.hostname
    )

    baker.make(
        AgentMetric,
        server_status=server,
        cpu=80.0,
        timestamp=timezone.now()
    )

    with patch('monitoring.tasks.dispatcher.send') as mock_send:
        result = evaluate_agent_alerts(destinations=['email'], batch=False)

    assert result is not None
    assert mock_send.call_count == 2


def test_multiple_metrics_aggregated_within_time_window(
        server, celery_app, celery_worker
):
    """
    Given one AlertRule with time_window_minutes=5 and threshold=50,
    multiple AgentMetric entries within
    that 5-minute window (all above threshold)
    should result in exactly one alert when batch=False.
    """
    # arrange: one rule with a 5-minute window
    baker.make(
        AlertRule,
        is_active=True,
        metric='cpu',
        operator='>',
        threshold=50,
        time_window_minutes=5,
        frequency=1,
        hostname=server.hostname
    )
    now = timezone.now()

    # older metric outside the window → ignored
    baker.make(
        AgentMetric,
        server_status=server,
        cpu=80.0,
        timestamp=now - timedelta(minutes=6)
    )
    # two metrics inside the window → both should aggregate into one alert
    baker.make(
        AgentMetric,
        server_status=server,
        cpu=60.0,
        timestamp=now - timedelta(minutes=3)
    )
    baker.make(
        AgentMetric,
        server_status=server,
        cpu=70.0,
        timestamp=now - timedelta(minutes=1)
    )

    with patch('monitoring.tasks.dispatcher.send') as mock_send:
        evaluate_agent_alerts(destinations=['email'], batch=False)

    # assert exactly one send() call because metrics were combined
    assert mock_send.call_count == 1
