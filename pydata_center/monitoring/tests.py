from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import ServerStatus


class ReceiveStatusEndpointTests(APITestCase):
    def setUp(self):
        self.url = reverse('monitoring:receive_status')

    def test_receive_valid_status(self):
        valid_data = {
            'hostname': 'testserver',
            'ip': '192.168.0.10',
            'uptime': 34567.8,
            'timestamp': '2025-05-30T06:27:00Z',
            'os': 'Ubuntu 22.04',
            'healthy': True,
            'server_name': 'DNSServer'
        }

        response = self.client.post(self.url, data=valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('hostname', response.data)
        self.assertIn('ip', response.data)
        self.assertEqual(response.data['hostname'], valid_data['hostname'])
        self.assertEqual(response.data['ip'], valid_data['ip'])

        self.assertTrue(
            ServerStatus.objects.filter(hostname='testserver').exists()
        )

        status_obj = ServerStatus.objects.get(hostname='testserver')
        self.assertEqual(status_obj.ip, valid_data['ip'])
        self.assertEqual(status_obj.uptime, valid_data['uptime'])
        self.assertEqual(status_obj.os, valid_data['os'])
        self.assertEqual(status_obj.healthy, valid_data['healthy'])
        self.assertEqual(status_obj.server_name, valid_data['server_name'])

    def test_receive_invalid_status(self):
        invalid_data = {
            'hostname': '',
            'uptime': 123
        }

        response = self.client.post(self.url, data=invalid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('hostname', response.data)
        self.assertIsInstance(response.data['hostname'], list)
