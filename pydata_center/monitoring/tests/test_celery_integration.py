import pytest
from django.conf import settings
from django.core.cache import cache as django_cache
from monitoring.tasks import evaluate_agent_alerts

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def disable_alert_destinations():
    """
    Prevent any child tasks that serialize dataclasses by clearing
    the default alert destinations.
    """
    settings.DEFAULT_ALERT_DESTINATIONS = []
    yield


@pytest.fixture
def fetch_result():
    """
    Normalize a Celery AsyncResult:
      – if it's a dict with 'result', return that;
      – otherwise return the raw value.
    """
    def _fetch(async_res, timeout=10):
        raw = async_res.get(timeout=timeout)
        return raw.get('result') if isinstance(raw, dict) else raw
    return _fetch


def test_alert_task_runs_successfully(celery_app, celery_worker, fetch_result):
    """
    Integration test: ensure the alert evaluation task completes
    and returns None or a dictionary.
    """
    django_cache.clear()
    result = evaluate_agent_alerts.delay()
    output = fetch_result(result)
    assert output is None or isinstance(output, dict)


def test_alert_task_with_invalid_destination(
        celery_app, celery_worker, fetch_result
):
    """
    Integration test: the task should handle
    invalid destinations gracefully.
    """
    result = evaluate_agent_alerts.apply_async(
        kwargs={'destinations': ['fakechannel']}
    )
    output = fetch_result(result)
    assert output is None or 'error' in output


def test_alert_task_with_default_destinations(
        celery_app, celery_worker, fetch_result
):
    """
    Integration test: verify the task works
    when no destinations are passed.
    """
    result = evaluate_agent_alerts.apply_async(kwargs={'destinations': None})
    output = fetch_result(result)
    assert output is None or isinstance(output, dict)


def test_alert_task_batch_false(celery_app, celery_worker, fetch_result):
    """
    Integration test: test task
    behavior with batch=False.
    """
    result = evaluate_agent_alerts.apply_async(kwargs={'batch': False})
    output = fetch_result(result)
    assert output is None or isinstance(output, dict)
