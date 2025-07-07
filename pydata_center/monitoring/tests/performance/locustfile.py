import logging
import random
import string
import time
from datetime import datetime

from locust import HttpUser, between, task

API_PREFIX = '/api/v1'
USERNAME = 'locust_tester'
PASSWORD = 'supersecret'

logger = logging.getLogger(__name__)


def random_hostname():
    return 'agent-' + ''.join(random.choices(string.digits, k=4))


class AgentSimulator(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.active = False  # default to inactive
        resp = None
        for attempt in range(1, 4):
            resp = self.client.post(
                f'{API_PREFIX}/token/',
                json={'username': USERNAME, 'password': PASSWORD}
            )
            if resp.status_code == 200:
                break
            time.sleep(0.5)
        else:
            return  # login failed

        token = resp.json()['access']
        self.client.headers.update({'Authorization': f'Bearer {token}'})

        self.hostname = random_hostname()
        self.ip = f'192.168.1.{random.randint(2, 254)}'

        pending = self.client.get(
            f'{API_PREFIX}/commands/',
            params={'hostname': self.hostname, 'status': 'pending'}
        )
        if pending.status_code == 200:
            self.valid_ids = [cmd['id'] for cmd in pending.json()]
        else:
            self.valid_ids = []

        self.active = True  # only mark active after full setup

    @task(3)
    def send_status(self):
        if not getattr(self, 'active', False):
            return
        self.client.post(
            f'{API_PREFIX}/server/status/',
            json={
                'hostname': self.hostname,
                'ip': self.ip,
                'uptime': round(random.uniform(0, 10000), 2),
                'healthy': random.choice([True, False]),
                'timestamp': datetime.utcnow().isoformat(),
                'os': random.choice(['Linux', 'Windows', 'macOS']),
                'server_name': self.hostname.replace('-', '_'),
            }
        )

    @task(1)
    def fetch_pending(self):
        if not getattr(self, 'active', False):
            return
        r = self.client.get(
            f'{API_PREFIX}/command/fetch/',
            params={'hostname': self.hostname}
        )
        if r.status_code == 200:
            cmd = r.json()
            if cmd.get('status') == 'pending':
                self.valid_ids.append(cmd['id'])

    @task(1)
    def submit_result(self):
        if not getattr(self, 'active', False):
            return
        if not self.valid_ids:
            return
        cmd_id = random.choice(self.valid_ids)
        resp = self.client.patch(
            f'{API_PREFIX}/command/result/',
            json={
                'id': cmd_id,
                'status': random.choice(['done', 'failed']),
                'result': 'simulated-result',
            }
        )
        if resp.status_code == 200:
            self.valid_ids.remove(cmd_id)
