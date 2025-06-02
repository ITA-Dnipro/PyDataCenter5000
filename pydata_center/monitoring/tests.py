from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


def get_base_payload():
    return {
        'hostname': 'server01',
        'ip': '192.168.1.1',
        'uptime': 123.45,
        'timestamp': '2025-06-01T10:00:00Z',
        'os': 'Linux',
        'healthy': True,
        'server_name': 'web01'
    }


class ServerStatusAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/server/status/'

        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.client.force_authenticate(user=self.user)

    def test_missing_hostname(self):
        payload = get_base_payload()
        payload.pop('hostname')
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_ip(self):
        payload = get_base_payload()
        payload['ip'] = '999.999.999.999'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_float_uptime(self):
        payload = get_base_payload()
        payload['uptime'] = 'up'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_status_submission(self):
        payload = get_base_payload()
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['message'], 'Status received')

    def test_empty_payload(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('hostname', response.data)

    def test_valid_healthy_type(self):
        payload = get_base_payload()
        payload['healthy'] = 'yes'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload['healthy'] = 'no'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_invalid_healthy_type(self):
        payload = get_base_payload()
        payload['healthy'] = 'abc'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_timestamp_format(self):
        payload = get_base_payload()
        payload['timestamp'] = 'not-a-date'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('timestamp', response.data)
