from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


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
