from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
import requests
from dateutil.parser import isoparse
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from monitoring.email import send_async_email
from monitoring.models import (AgentLogEntry, AgentMetric, AlertRule,
                               ServerStatus)
from monitoring.tasks import evaluate_agent_alerts
from monitoring.webhook import WebhookMessage, send_async_webhook_message
from rest_framework import status
from rest_framework.test import APIClient, APITestCase


@pytest.fixture(scope='session', autouse=True)
def setup_roles(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command('init_roles')


class ServerStatusAPITest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        # add user to Operator group
        operator_group, _ = Group.objects.get_or_create(name='Operator')
        cls.user.groups.add(operator_group)
        cls.url = '/api/v1/server/status/'

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _get_base_payload(self):
        return {
            'hostname': 'server01',
            'ip': '192.168.1.1',
            'uptime': 123.45,
            'timestamp': '2025-06-01T10:00:00Z',
            'os': 'Linux',
            'healthy': True,
            'server_name': 'web01'
        }

    def test_missing_hostname(self):
        payload = self._get_base_payload()
        payload.pop('hostname')
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f'Expected 400 for missing hostname, got {response.status_code}.'
            f' Response: {response.data}'
        )

    def test_invalid_ip(self):
        payload = self._get_base_payload()
        payload['ip'] = '999.999.999.999'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f'Expected 400 for invalid IP, got {response.status_code}.'
            f' Response: {response.data}'
        )

    def test_non_float_uptime(self):
        payload = self._get_base_payload()
        payload['uptime'] = 'up'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f'Expected 400 for non-float uptime, got {response.status_code}.'
            f' Response: {response.data}'
        )

    def test_valid_status_submission(self):
        payload = self._get_base_payload()
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f'Expected 201 Created, got {response.status_code}.'
            f' Response data: {response.data}'
        )
        self.assertIn(
            'message', response.data,
            f"Expected 'message' key in response."
            f' Got: {response.data}'
        )
        self.assertEqual(
            response.data['message'],
            'Status received',
            f"Expected message to be 'Status received'."
            f" Got: {response.data['message']}"
        )

    def test_empty_payload(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f'Expected 400 for empty payload. '
            f'Got: {response.status_code}. Response: {response.data}'
        )
        self.assertIn(
            'hostname', response.data,
            f"'hostname' key not found in response."
            f' Got: {response.data}'
        )

    def test_valid_healthy_type(self):
        payload = self._get_base_payload()
        payload['healthy'] = 'yes'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f'Expected 201 for healthy="yes".'
            f' Got: {response.status_code}. Response: {response.data}'
        )
        payload['healthy'] = 'no'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f'Expected 201 for healthy="no".'
            f' Got: {response.status_code}. Response: {response.data}'
        )

    def test_invalid_healthy_type(self):
        payload = self._get_base_payload()
        payload['healthy'] = 'abc'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f'Expected 400 for invalid healthy value.'
            f' Got: {response.status_code}. Response: {response.data}'
        )

    def test_invalid_timestamp_format(self):
        payload = self._get_base_payload()
        payload['timestamp'] = 'not-a-date'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f'Expected 400 for invalid timestamp.'
            f' Got: {response.status_code}. Response: {response.data}'
        )
        self.assertIn(
            'timestamp', response.data,
            f"'timestamp' key not found in error response."
            f' Got: {response.data}'
        )


class ReceiveStatusEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('monitoring:receive_status')
        cls.username = 'testuser'
        cls.password = 'testpass'
        cls.user = User.objects.create_user(
            username=cls.username, password=cls.password
        )

        # add user to group Operator
        operator_group, _ = Group.objects.get_or_create(name='Operator')
        cls.user.groups.add(operator_group)

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def _get_valid_status_data(self):
        return {
            'hostname': 'testserver',
            'ip': '192.168.0.10',
            'uptime': 34567.8,
            'timestamp': '2025-05-30T06:27:00Z',
            'os': 'Ubuntu 22.04',
            'healthy': True,
            'server_name': 'DNSServer'
        }

    def test_receive_valid_status(self):
        valid_data = self._get_valid_status_data()
        response = self.client.post(self.url, data=valid_data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f'Expected 201 CREATED, got {response.status_code} '
            f'with response: {response.data}'
        )
        self.assertIn(
            'hostname',
            response.data,
            "'hostname' key not found in response data"
        )
        self.assertIn(
            'ip',
            response.data,
            "'ip' key not found in response data"
        )
        self.assertEqual(
            response.data['hostname'],
            valid_data['hostname'],
            'Hostname in response does not match the input'
        )
        self.assertEqual(
            response.data['ip'],
            valid_data['ip'],
            'IP in response does not match the input'
        )
        self.assertTrue(
            ServerStatus.objects.filter(hostname='testserver').exists(),
            'ServerStatus object was not created'
        )

        status_obj = ServerStatus.objects.get(hostname='testserver')
        self.assertEqual(
            status_obj.ip,
            valid_data['ip'],
            'Saved IP does not match'
        )
        self.assertEqual(
            status_obj.uptime,
            valid_data['uptime'],
            'Saved uptime does not match'
        )
        self.assertEqual(
            status_obj.os,
            valid_data['os'],
            'Saved OS does not match'
        )
        self.assertEqual(
            status_obj.healthy,
            valid_data['healthy'],
            'Saved health status does not match'
        )
        self.assertEqual(
            status_obj.server_name,
            valid_data['server_name'],
            'Saved server_name does not match'
        )

    def test_receive_invalid_status(self):
        invalid_data = {
            'hostname': '',
            'uptime': 123
        }
        response = self.client.post(
            self.url,
            data=invalid_data,
            format='json'
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            f'Expected 400 BAD_REQUEST, got {response.status_code}'
        )
        self.assertIn(
            'hostname',
            response.data,
            "'hostname' key not found in error response"
        )
        self.assertIsInstance(
            response.data['hostname'],
            list,
            "Expected 'hostname' error messages to be a list"
        )

    def test_hostname_too_long(self):
        data = self._get_valid_status_data()
        data['hostname'] = 'x' * 300
        response = self.client.post(self.url, data=data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            'Expected 400 BAD_REQUEST for overly long hostname'
        )
        self.assertIn(
            'hostname',
            response.data,
            "Expected 'hostname' validation error"
        )

    def test_invalid_uptime_type(self):
        data = self._get_valid_status_data()
        data['uptime'] = 'not_a_number'
        response = self.client.post(self.url, data=data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            'Expected 400 BAD_REQUEST for invalid uptime type'
        )
        self.assertIn(
            'uptime',
            response.data,
            "Expected 'uptime' validation error"
        )

    def test_missing_hostname_field(self):
        data = self._get_valid_status_data()
        data.pop('hostname')
        response = self.client.post(self.url, data=data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            "Expected 400 BAD_REQUEST when 'hostname' is missing"
        )
        self.assertIn(
            'hostname',
            response.data,
            "'hostname' should be reported as missing"
        )

    def test_missing_ip_field(self):
        data = self._get_valid_status_data()
        data.pop('ip')
        response = self.client.post(self.url, data=data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            "Expected 400 BAD_REQUEST when 'ip' is missing"
        )
        self.assertIn(
            'ip',
            response.data,
            "'ip' should be reported as missing"
        )

    def test_missing_uptime_field(self):
        data = self._get_valid_status_data()
        data.pop('uptime')
        response = self.client.post(self.url, data=data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            "Expected 400 BAD_REQUEST when 'uptime' is missing"
        )
        self.assertIn(
            'uptime',
            response.data,
            "'uptime' should be reported as missing"
        )

    def test_missing_timestamp_field(self):
        data = self._get_valid_status_data()
        data.pop('timestamp')
        response = self.client.post(self.url, data=data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            "Expected 400 BAD_REQUEST when 'timestamp' is missing"
        )
        self.assertIn(
            'timestamp',
            response.data,
            "'timestamp' should be reported as missing"
        )

    def test_missing_os_field(self):
        data = self._get_valid_status_data()
        data.pop('os')
        response = self.client.post(self.url, data=data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            "Expected 400 BAD_REQUEST when 'os' is missing"
        )
        self.assertIn(
            'os',
            response.data,
            "'os' should be reported as missing"
        )

    def test_missing_healthy_field(self):
        data = self._get_valid_status_data()
        data.pop('healthy')
        response = self.client.post(self.url, data=data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            "Expected 201 CREATED when 'healthy' is missing"
        )
        status_obj = ServerStatus.objects.get(hostname='testserver')
        self.assertFalse(
            status_obj.healthy,
            "'healthy' should default to False when missing"
        )

    def test_missing_server_name_field(self):
        data = self._get_valid_status_data()
        data.pop('server_name')
        response = self.client.post(self.url, data=data, format='json')

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            "Expected 400 BAD_REQUEST when 'server_name' is missing"
        )
        self.assertIn(
            'server_name',
            response.data,
            "'server_name' should be reported as missing"
        )


@pytest.mark.parametrize('func,msg', [
    (send_async_webhook_message, {'content': 'mock-content'}),
    (
        send_async_webhook_message,
        {'content': 'mock-content', 'webhook': 'mock-webhook', 'bad': 'arg'}
    ),
    (send_async_email, {'body': 'mock-body'}),
    (
        send_async_email,
        {
            'subject': 'mock-subject',
            'body': 'mock-body',
            'recipients': ['mock-rec'],
            'bad': 'arg',
        }
    ),
])
def test_send_async_bad_serialized_message(caplog, func, msg):
    """
    Test handling and logging of invalid serialized message passed to
    send_async_discord_message or send_async_email.
    """
    with caplog.at_level('ERROR'):
        result = func(msg)

    assert result is None
    assert 'Error due to missing or invalid arguments' in caplog.text


@pytest.mark.parametrize('status_code', [200, 204])
def test_send_async_webhook_message_success(monkeypatch, caplog, status_code):
    """Test handling and logging of succesfull webhook POST request."""
    class MockResponse:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = 'OK'

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        'requests.post', lambda url, json, timeout: MockResponse(status_code)
    )

    msg = WebhookMessage(
        'Mock message', webhook='https://mock.com/api/webhooks/mock'
    )

    with caplog.at_level('INFO'):
        send_async_webhook_message(msg)

    assert (
        f'POST request sent successfully. Webhook response: {status_code} OK'
        in caplog.text
    )


@pytest.mark.parametrize('fail_silently', [True, False])
def test_send_async_webhook_message_http_error(
    monkeypatch, caplog, fail_silently
):
    """Test handling and logging of HTTP error."""
    class MockResponse:
        def __init__(self):
            self.status_code = 400
            self.text = 'Bad Request'

        def raise_for_status(self):
            raise requests.exceptions.HTTPError('Mock HTTP error')

    monkeypatch.setattr(
        'requests.post', lambda url, json, timeout: MockResponse()
    )

    msg = WebhookMessage(
        'Mock message',
        webhook='https://mock.com/api/webhooks/mock',
        fail_silently=fail_silently,
    )

    with caplog.at_level('ERROR'):
        if fail_silently:
            send_async_webhook_message(msg)
        else:
            with pytest.raises(requests.exceptions.HTTPError):
                send_async_webhook_message(msg)

    assert (
        (
            f'Sending message to webhook failed due to error: '
            f'{requests.exceptions.HTTPError}'
        )
        in caplog.text
    )


@pytest.mark.parametrize('error_type', [
    requests.exceptions.ConnectionError,
    requests.exceptions.InvalidURL,
])
def test_send_async_webhook_message_connection_or_url_error(
    monkeypatch, caplog, error_type
):
    webhook = 'https://mock.com/api/webhooks/mock'

    monkeypatch.setattr(
        'requests.post',
        lambda url, json, timeout: (
            _ for _ in ()
        ).throw(error_type(f'Failed to connect to URL {webhook}')),
    )

    msg = WebhookMessage('Mock message', webhook=webhook)

    with caplog.at_level('ERROR'):
        send_async_webhook_message(msg)

    assert (
        f'Sending message to webhook failed due to error: {error_type}'
        in caplog.text
    )
    assert webhook not in caplog.text


@pytest.mark.django_db
class TestEvaluateAgentAlerts:
    """Test suite for evaluate_agent_alerts task."""
    def setup_method(self):
        self.server = ServerStatus.objects.create(
            hostname='test-alerts-server',
            ip='0.0.0.0',
            uptime=100,
            timestamp=timezone.now(),
            os='linux',
            healthy=True,
            server_name='test_alerts_server',
        )
        self.rule = AlertRule.objects.create(
            metric='cpu',
            operator='>',
            threshold='10',
            notify_message='CPU usage exceeded threshold of 10%',
        )
        AgentMetric.objects.create(
            cpu=50, timestamp=timezone.now(), server_status=self.server
        )

    @pytest.mark.parametrize(
        ['destination', 'mocked'],
        [
            (
                'email',
                'monitoring.email.send_async_email.apply_async'
            ),
            (
                'discord',
                'monitoring.webhook.send_async_webhook_message.apply_async'
            ),
            (
                'slack',
                'monitoring.webhook.send_async_webhook_message.apply_async'
            ),
        ]
    )
    def test_alert_triggered(self, destination, mocked, caplog):
        with caplog.at_level('WARNING'), patch(mocked) as mock_send:
            if destination in ('discord', 'slack'):
                with patch(
                    f'pydata_center.settings.ALERT_'
                    f'{destination.upper()}_WEBHOOK',
                    'https://mock/webhook',
                    create=True,
                ):
                    evaluate_agent_alerts(
                        destinations=[destination],
                        batch=False,
                    )
            else:
                evaluate_agent_alerts(
                    destinations=[destination],
                    batch=False,
                )

        assert mock_send.called
        assert 'CPU usage exceeded threshold of 10%' in caplog.text

    @pytest.mark.parametrize('destination,mocked', [
        ('email', 'monitoring.email.send_async_email.apply_async'),
        (
            'discord',
            'monitoring.webhook.send_async_webhook_message.apply_async',
        )
    ])
    def test_no_alerts_triggered(self, destination, mocked, caplog):
        self.rule.threshold = 60
        self.rule.save()

        with caplog.at_level('INFO'), patch(mocked) as mock_send_message:
            evaluate_agent_alerts(destinations=[destination], batch=False)

            assert not mock_send_message.called
        assert 'No alerts triggered' in caplog.text

    @patch('monitoring.tasks.AlertDispatcher.send')
    def test_no_data_for_metric(self, mock_send, caplog):
        self.rule.metric = 'ram'
        self.rule.save()

        with caplog.at_level('INFO'):
            evaluate_agent_alerts(destinations=['email'], batch=False)

        assert not mock_send.called
        assert 'No data for rule' in caplog.text

    @pytest.mark.parametrize('destination,mocked', [
        ('email', 'monitoring.email.send_async_email.apply_async'),
        (
            'discord',
            'monitoring.webhook.send_async_webhook_message.apply_async'
        ),
        (
            'slack',
            'monitoring.webhook.send_async_webhook_message.apply_async'
        ),
    ])
    def test_alert_triggered_with_less_than_operator(
        self, destination, mocked, caplog
    ):
        self.rule.metric = 'cpu'
        self.rule.operator = '<'
        self.rule.threshold = 100
        self.rule.notify_message = 'CPU usage below 100%'
        self.rule.save()

        with caplog.at_level('WARNING'), patch(mocked) as mock_send_message:
            evaluate_agent_alerts(destinations=[destination], batch=False)

            assert mock_send_message.called
        assert 'CPU usage below 100%' in caplog.text

    @patch('monitoring.tasks.AlertDispatcher.send')
    def test_rate_limit(self, mock_send):
        self.rule.operator = '>'
        self.rule.threshold = 10
        self.notify_message = 'CPU usage exceeded threshold of 10%'
        self.rule.save()

        cache.set(f'alert_sent_{self.rule.id}', True, timeout=1000)

        evaluate_agent_alerts(destinations=['email'], batch=False)

        assert not mock_send.called

    @patch('monitoring.tasks.AlertDispatcher.send')
    def test_batch_alerts_triggered(self, mock_send, caplog):
        # Add another rule that will trigger an alert with existing
        # agent metric.
        AlertRule.objects.create(
            metric='cpu',
            operator='>',
            threshold=25,
            notify_message='CPU usage exceeded threshold of 25%'
        )

        with caplog.at_level('WARNING'):
            evaluate_agent_alerts(destinations=['email'], batch=True)

        assert mock_send.call_count == 1
        assert (
            'CPU usage exceeded threshold of 25%' in caplog.text
            and 'CPU usage exceeded threshold of 10%' in caplog.text
        )

    @patch('monitoring.tasks.AlertDispatcher.send')
    def test_rate_limit_batch_alerts_triggered(self, mock_send, caplog):
        AlertRule.objects.create(
            metric='cpu',
            operator='>',
            threshold=15,
            notify_message='CPU usage exceeded threshold of 15%'
        )

        cache.set(f'alert_sent_{self.rule.id}', True, timeout=1000)

        with caplog.at_level('WARNING'):
            evaluate_agent_alerts(destinations=['email'], batch=True)

        assert mock_send.call_count == 1
        assert (
            'CPU usage exceeded threshold of 15%' in caplog.text
            and 'CPU usage exceeded threshold of 10%' not in caplog.text
        )

    @pytest.mark.parametrize('batch', [False, True])
    @override_settings(DEFAULT_ALERT_DESTINATIONS=['unknown'])
    @patch('monitoring.tasks.AlertDispatcher.send')
    def test_bad_destination(self, mock_send, batch, caplog):
        with caplog.at_level('ERROR'):
            evaluate_agent_alerts(batch=batch)

        assert not mock_send.called
        assert 'Unknown alert destination unknown' in caplog.text


class TestCreateAgentMetrics(APITestCase):

    def setUp(self):
        self.url = '/api/v1/agent/metrics/'
        self.hostname = 'test-host'
        self.ip = '192.168.56.11'
        self.os_type = 'linux'
        self.uptime = 123456
        self.timestamp = timezone.now()

        self.server = ServerStatus.objects.create(
            hostname=self.hostname,
            ip=self.ip,
            os=self.os_type,
            uptime=self.uptime,
            timestamp=self.timestamp,
            server_name='Test Server'
        )
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def get_cpu_usage(self):
        return 45.0

    def get_ram_usage(self):
        return 70.5

    def get_disk_usage(self):
        return 55.0

    def get_load_average(self):
        return 1.23

    def generate_report(self):
        return {
            'hostname': self.hostname,
            'cpu': self.get_cpu_usage(),
            'ram': self.get_ram_usage(),
            'disk': self.get_disk_usage(),
            'load_avg': self.get_load_average(),
            'timestamp': timezone.now(),
        }

    def test_create_metric_successfully(self):
        payload = self.generate_report()

        response = self.client.post(
            f'{self.url}?hostname={self.hostname}',
            payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'metric recorded')
        self.assertEqual(AgentMetric.objects.count(), 1)

    def test_create_metric_missing_hostname(self):
        payload = self.generate_report()
        del payload['hostname']
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_create_metric_with_unknown_hostname(self):
        payload = self.generate_report()
        response = self.client.post(
            f'{self.url}?hostname=nonexistent-host',
            payload,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_create_metric_invalid_data(self):
        payload = self.generate_report()
        payload['cpu'] = 'not-a-number'

        response = self.client.post(
            f'{self.url}?hostname={self.hostname}',
            payload,
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cpu', response.data)


class MetricsHistoryViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.url = reverse('monitoring:metrics_history')
        cls.username = 'testuser'
        cls.password = 'testpass'
        cls.user = User.objects.create_user(
            username=cls.username,
            password=cls.password
        )

        cls.fixed_now = (
            timezone.now()
            .replace(microsecond=0)
            .astimezone(timezone.utc)
        )

        cls.server = ServerStatus.objects.create(
            hostname='server1',
            ip='127.0.0.1',
            uptime=1000,
            timestamp=cls.fixed_now,
            os='Ubuntu',
            healthy=True,
            server_name='MainServer'
        )

        metric_early = AgentMetric.objects.create(
            server_status=cls.server,
            cpu=10.5, ram=20.0, disk=50.0, load_avg=0.5
        )
        metric_mid = AgentMetric.objects.create(
            server_status=cls.server,
            cpu=30.2, ram=40.0, disk=60.0, load_avg=0.9
        )
        metric_latest = AgentMetric.objects.create(
            server_status=cls.server,
            cpu=50.1, ram=80.0, disk=90.0, load_avg=1.3
        )

        metric_early.timestamp = cls.fixed_now - timedelta(minutes=10)
        metric_early.save(update_fields=['timestamp'])

        metric_mid.timestamp = cls.fixed_now - timedelta(minutes=5)
        metric_mid.save(update_fields=['timestamp'])

        metric_latest.timestamp = cls.fixed_now
        metric_latest.save(update_fields=['timestamp'])

        cls.metric_early = metric_early
        cls.metric_mid = metric_mid
        cls.metric_latest = metric_latest

    def setUp(self):
        self.client.login(
            username=self.username,
            password=self.password
        )
        self.fixed_now = self.__class__.fixed_now

    def test_get_all_metrics(self):
        response = self.client.get(self.url)
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f'Expected 200 OK, got {response.status_code}'
        )
        self.assertEqual(
            len(response.data),
            3,
            f'Expected 3 metrics, got {len(response.data)}'
        )

    def test_filter_by_hostname(self):
        response = self.client.get(self.url, {'hostname': 'server1'})
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f'Expected 200 OK, got {response.status_code}'
        )
        self.assertTrue(
            all(
                item['server_status__hostname'] == 'server1'
                for item in response.data
            ),
            f"Not all items have hostname 'server1': {response.data}"
        )

    def test_filter_by_start_time(self):
        start_time = (
            self.fixed_now - timedelta(minutes=7)
        ).isoformat()
        response = self.client.get(self.url, {'start': start_time})
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f'Expected 200 OK, got {response.status_code}'
        )
        expected_timestamps = {
            self.metric_mid.timestamp,
            self.metric_latest.timestamp
        }
        returned_timestamps = {item['timestamp'] for item in response.data}
        self.assertSetEqual(
            returned_timestamps,
            expected_timestamps,
            f'Expected timestamps {expected_timestamps}, '
            f'got {returned_timestamps}'
        )

    def test_filter_by_end_time(self):
        end_time = (
            self.fixed_now - timedelta(minutes=6)
        ).isoformat()
        response = self.client.get(self.url, {'end': end_time})
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f'Expected 200 OK, got {response.status_code}'
        )
        self.assertEqual(
            len(response.data),
            1,
            f'Expected 1 metric, got {len(response.data)}'
        )
        self.assertEqual(
            response.data[0]['timestamp'],
            self.metric_early.timestamp,
            f'Expected timestamp {self.metric_early.timestamp.isoformat()}, '
            f"got {response.data[0]['timestamp']}"
        )

    def test_filter_by_start_and_end_time(self):
        start_time = (
            self.fixed_now - timedelta(minutes=7)
        ).isoformat()
        end_time = (
            self.fixed_now - timedelta(minutes=3)
        ).isoformat()
        response = self.client.get(
            self.url,
            {'start': start_time, 'end': end_time}
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f'Expected 200 OK, got {response.status_code}'
        )
        self.assertEqual(
            len(response.data),
            1,
            f'Expected 1 metric between start and end, got '
            f'{len(response.data)}'
        )
        expected_ts = self.metric_mid.timestamp
        self.assertEqual(
            response.data[0]['timestamp'],
            expected_ts,
            f'Expected timestamp {expected_ts}, '
            f"got {response.data[0]['timestamp']}"
        )

    def test_invalid_time_format(self):
        response = self.client.get(self.url, {'start': 'invalid-date'})
        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
            'Expected 400 Bad Request for invalid date, '
            f'got {response.status_code}'
        )
        self.assertIn(
            'start', response.data, "Expected 'start' key in error response"
        )

    def test_unauthenticated_access_denied(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            'Expected 403 FORBIDDEN for unauthenticated access '
            f'got {response.status_code}'
        )

    def test_no_metrics_in_range(self):
        start = (self.fixed_now + timedelta(minutes=1)).isoformat()
        response = self.client.get(self.url, {'start': start})
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            'Expected 200 OK for no metrics in range, '
            f'got {response.status_code}'
        )
        self.assertEqual(len(response.data), 0)

    def test_naive_start_datetime_is_made_aware(self):
        naive_start = datetime(2025, 6, 1, 10, 0, 0).isoformat()
        response = self.client.get(self.url, {'start': naive_start})
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f'Expected 200 OK for naive datetime, got {response.status_code}'
        )


class ReceiveLogEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.operator_group, _ = Group.objects.get_or_create(name='Operator')

        self.operator_user = User.objects.create_user(
            username='operator', password='pass123'
        )
        self.operator_user.groups.add(self.operator_group)

        self.viewer_user = User.objects.create_user(
            username='viewer', password='pass123'
        )

        self.valid_payload = {
            'agent_name': 'agent-01',
            'timestamp': '2025-06-25T12:30:00Z',
            'level': 'ERROR',
            'message': 'Failed to restart ssh service',
            'context': {'uptime': 123.45, 'ip': '192.168.1.100'}
        }

        self.invalid_payload = {
            'agent_name': 'agent-01',
            # timestamp missing
            'level': 'ERROR',
            'message': 'Missing timestamp'
        }

        self.url = reverse('monitoring:receive_log')

    def test_successful_log_post_by_operator(self):
        """Operator user can successfully post a valid log."""
        self.client.force_authenticate(user=self.operator_user)
        response = self.client.post(
            self.url, self.valid_payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED,
            msg=f'Expected 201 CREATED but got {response.status_code}'
        )
        self.assertEqual(
            AgentLogEntry.objects.count(), 1,
            msg='Log entry was not created in the database'
        )
        self.assertEqual(
            response.data['agent_name'], 'agent-01',
            msg='Response data does not contain the correct agent_name'
        )

    def test_log_post_by_unauthorized_user(self):
        """Viewer user cannot post logs (permission denied)."""
        self.client.force_authenticate(user=self.viewer_user)
        response = self.client.post(
            self.url, self.valid_payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN,
            msg=f'Expected 403 FORBIDDEN but got {response.status_code}'
        )

    def test_log_post_by_unauthenticated_user(self):
        """Unauthenticated users cannot post logs."""
        response = self.client.post(
            self.url, self.valid_payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN,
            msg=f'Expected 403 FORBIDDEN but got {response.status_code}'
        )

    def test_log_post_with_invalid_payload(self):
        """Posting log with invalid payload returns 400 Bad Request."""
        self.client.force_authenticate(user=self.operator_user)
        response = self.client.post(
            self.url, self.invalid_payload, format='json'
        )
        self.assertEqual(
            response.status_code, status.HTTP_400_BAD_REQUEST,
            msg=f'Expected 400 BAD REQUEST but got {response.status_code}'
        )
        self.assertIn(
            'timestamp', response.data,
            msg="Response data does not contain error missing 'timestamp'"
        )
