from unittest.mock import patch

import pytest
import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from monitoring.discord import DiscordMessage, send_async_discord_message
from monitoring.models import AgentMetric, AlertRule, ServerStatus
from monitoring.tasks import evaluate_agent_alerts
from rest_framework import status
from rest_framework.test import APIClient, APITestCase


class ServerStatusAPITest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
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

    def setUp(self):
        self.client.login(username=self.username, password=self.password)

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


@pytest.mark.parametrize('status_code', [200, 204])
def test_send_async_discord_message_success(monkeypatch, caplog, status_code):
    """Test handling and logging of succesfull Discord POST request."""
    class MockResponse:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = 'OK'

        def raise_for_status(self):
            pass

    monkeypatch.setattr(
        'requests.post', lambda url, json: MockResponse(status_code)
    )

    msg = DiscordMessage(
        'Mock message', webhook='https://discord.com/api/webhooks/mock'
    )

    with caplog.at_level('INFO'):
        send_async_discord_message(msg)

    assert (
        f'POST request sent succesfully. Discord reposnse: {status_code} OK'
        in caplog.text
    )


@pytest.mark.parametrize('fail_silently', [True, False])
def test_send_async_discord_message_http_error(
    monkeypatch, caplog, fail_silently
):
    """Test handling and logging of HTTP error."""
    class MockResponse:
        def __init__(self):
            self.status_code = 400
            self.text = 'Bad Request'

        def raise_for_status(self):
            raise requests.exceptions.HTTPError('Mock HTTP error')

    monkeypatch.setattr('requests.post', lambda url, json: MockResponse())

    msg = DiscordMessage(
        'Mock message',
        webhook='https://discord.com/api/webhooks/mock',
        fail_silently=fail_silently,
    )

    with caplog.at_level('ERROR'):
        if fail_silently:
            send_async_discord_message(msg)
        else:
            with pytest.raises(
                requests.exceptions.HTTPError,
                match='Sending Discord message failed.',
            ):
                send_async_discord_message(msg)

    assert (
        (
            f'Sending Discord message failed due to error: '
            f'{requests.exceptions.HTTPError}'
        )
        in caplog.text
    )


@pytest.mark.parametrize('error_type', [
    requests.exceptions.ConnectionError,
    requests.exceptions.InvalidURL,
])
def test_send_async_discord_message_connection_or_url_error(
    monkeypatch, caplog, error_type
):
    webhook = 'https://discord.com/api/webhooks/mock'

    monkeypatch.setattr(
        'requests.post',
        lambda url, json: (
            _ for _ in ()
        ).throw(error_type(f'Failed to connect to URL {webhook}')),
    )

    msg = DiscordMessage('Mock message', webhook=webhook)

    with caplog.at_level('ERROR'):
        send_async_discord_message(msg)

    assert (
        f'Sending Discord message failed due to error: {error_type}'
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

    @pytest.mark.parametrize('destination,mocked', [
        ('email', 'monitoring.email.send_async_email.apply_async'),
        (
            'discord',
            'monitoring.discord.send_async_discord_message.apply_async',
        )
    ])
    def test_alert_triggered(self, destination, mocked, caplog):
        with caplog.at_level('WARNING'), patch(mocked) as mock_send_message:
            evaluate_agent_alerts(destinations=[destination], batch=False)

            assert mock_send_message.called
        assert 'CPU usage exceeded threshold of 10%' in caplog.text

    @pytest.mark.parametrize('destination,mocked', [
        ('email', 'monitoring.email.send_async_email.apply_async'),
        (
            'discord',
            'monitoring.discord.send_async_discord_message.apply_async',
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
            'monitoring.discord.send_async_discord_message.apply_async',
        )
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
        response = self.client.post(self.url, payload, format='json')
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
        payload['hostname'] = 'nonexistent-host'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_create_metric_invalid_data(self):
        payload = self.generate_report()
        payload['cpu'] = 'not-a-number'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('cpu', response.data)
