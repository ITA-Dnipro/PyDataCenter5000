from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


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
        payload = {
            'ip': '192.168.1.1',
            'uptime': 123.45,
            'timestamp': '2025-06-01T10:00:00Z',
            'os': 'Linux',
            'healthy': True,
            'server_name': 'web01'
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_ip(self):
        payload = {
            'hostname': 'server01',
            'ip': '999.999.999.999',
            'uptime': 123.45,
            'timestamp': '2025-06-01T10:00:00Z',
            'os': 'Linux',
            'healthy': True,
            'server_name': 'web01'
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_float_uptime(self):
        payload = {
            'hostname': 'server01',
            'ip': '192.168.1.1',
            'uptime': 'up',
            'timestamp': '2025-06-01T10:00:00Z',
            'os': 'Linux',
            'healthy': True,
            'server_name': 'web01'
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_valid_status_submission(self):
        payload = {
            'hostname': 'server01',
            'ip': '192.168.1.1',
            'uptime': 123.45,
            'timestamp': '2025-06-01T10:00:00Z',
            'os': 'Linux',
            'healthy': True,
            'server_name': 'web01'
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['message'], 'Status received')
