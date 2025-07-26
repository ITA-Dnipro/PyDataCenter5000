import os
import random

import pytest
import requests

BASE_URL = os.getenv('LOCUST_TARGET', 'http://localhost:8000')
USERNAME = os.getenv('LOCUST_USERNAME', 'locust_tester')
PASSWORD = os.getenv('LOCUST_PASSWORD', 'supersecret')


@pytest.fixture(scope='session')
def access_token():
    response = requests.post(
        f'{BASE_URL}/api/v1/token/',
        json={'username': USERNAME, 'password': PASSWORD}
    )
    assert response.status_code == 200
    return response.json()['access']


@pytest.fixture
def auth_headers(access_token):
    return {'Authorization': f'Bearer {access_token}'}


def test_token_issue(benchmark):
    def login():
        r = requests.post(
            f'{BASE_URL}/api/v1/token/',
            json={'username': USERNAME, 'password': PASSWORD}
        )
        assert r.status_code == 200
        return r.json()

    benchmark(login)


def test_pending_commands(benchmark, auth_headers):
    def fetch():
        r = requests.get(
            f'{BASE_URL}/api/v1/commands/',
            params={'hostname': 'agent-0001', 'status': 'pending'},
            headers=auth_headers
        )
        assert r.status_code == 200 or r.status_code == 404
        return r

    benchmark(fetch)


def test_status_update(benchmark, auth_headers):
    def send_status():
        r = requests.post(
            f'{BASE_URL}/api/v1/server/status/',
            json={
                'hostname': 'agent-0001',
                'ip': '192.168.1.10',
                'uptime': round(random.uniform(0, 10000), 2),
                'healthy': random.choice([True, False]),
                'timestamp': '2025-01-01T00:00:00Z',
                'os': 'Linux',
                'server_name': 'agent_0001'
            },
            headers=auth_headers
        )
        assert r.status_code == 200
        return r

    benchmark(send_status)


def test_command_fetch(benchmark, auth_headers):
    def fetch():
        r = requests.get(
            f'{BASE_URL}/api/v1/command/fetch/',
            params={'hostname': 'agent-0001'},
            headers=auth_headers
        )
        assert r.status_code in (200, 404)
        return r

    benchmark(fetch)


def test_result_submit(benchmark, auth_headers):
    def submit():
        # Use an invalid command ID just for performance hit;
        # adjust logic if needed
        r = requests.patch(
            f'{BASE_URL}/api/v1/command/result/',
            json={
                'id': 9999,
                'status': 'done',
                'result': 'simulated-result'
            },
            headers=auth_headers
        )
        assert r.status_code in (200, 400, 404)
        return r

    benchmark(submit)
