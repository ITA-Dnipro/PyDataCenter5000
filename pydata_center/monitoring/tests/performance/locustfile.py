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
        # Authenticate with up to 3 retries
        resp = None
        for attempt in range(1, 4):
            resp = self.client.post(
                f'{API_PREFIX}/token/',
                json={'username': USERNAME, 'password': PASSWORD}
            )
            if resp.status_code == 200:
                break
            logger.warning(
                f'Auth attempt {attempt} failed '
                f'(status {resp.status_code}); retrying...'
            )
            time.sleep(0.5)
        else:
            logger.error(
                'JWT login failed after 3 attempts; skipping this user'
            )
            return  # Abort init, but user stays alive to run other tasks

        token = resp.json()['access']
        self.client.headers.update({'Authorization': f'Bearer {token}'})

        # Init agent state
        self.hostname = random_hostname()
        self.ip = f'192.168.1.{random.randint(2, 254)}'

        # Preload valid command IDs
        self.valid_ids = list(range(117, 200))

    @task(3)
    def send_status(self):
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
        self.client.get(
            f'{API_PREFIX}/command/fetch/',
            params={'hostname': self.hostname}
        )

    @task(1)
    def submit_result(self):
        fake_id = random.choice(self.valid_ids)
        self.client.patch(
            f'{API_PREFIX}/command/result/',
            json={
                'id': fake_id,
                'status': random.choice(['done', 'failed']),
                'result': 'simulated-result',
            }
        )
