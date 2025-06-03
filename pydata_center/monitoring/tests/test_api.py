from django.contrib.auth.models import User
from django.urls import reverse
from monitoring.models import ServerStatus
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken


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
