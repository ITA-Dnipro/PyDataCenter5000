import random
import string

from locust import HttpUser, between

API_PREFIX = '/api/v1'  # adjust to your actual settings.API_PREFIX


def random_hostname():
    return 'agent-' + ''.join(random.choices(string.digits, k=4))


class AgentSimulator(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Initialize each “user” as a unique agent
        self.hostname = random_hostname()
        self.ip = f'192.168.1.{random.randint(2, 254)}'

    def send_status(self):
        payload = {
            'hostname': self.hostname,
            'ip':       self.ip,
            'uptime':   round(random.uniform(0, 10000), 2),
            'healthy':  random.choice([True, False])
        }
        self.client.post(f'{API_PREFIX}/server/status/', json=payload)

    def fetch_pending(self):
        self.client.get(
            f'{API_PREFIX}/command/',
            params={'hostname': self.hostname}
        )

    def submit_result(self):
        fake_id = random.randint(1, 100)
        body = {
            'id':     fake_id,
            'status': random.choice(['done', 'failed']),
            'result': 'simulated-result'
        }
        self.client.patch(
            f'{API_PREFIX}/command/submit-command/',
            json=body
        )

    # Explicitly register tasks with weights
    tasks = {
        send_status:   3,  # send status 3× as often
        fetch_pending: 1,
        submit_result: 1,
    }
