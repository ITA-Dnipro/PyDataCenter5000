import datetime
import os
import random
import uuid

from dotenv import load_dotenv
from locust import HttpUser, between, task

load_dotenv()
TOKEN = None

USERNAME = os.getenv('LOCUST_USERNAME', 'user')
PASSWORD = os.getenv('LOCUST_PASSWORD', 'password')
print(f'USERNAME: {USERNAME}')
print(f'PASSWORD: {PASSWORD}')


def get_token_once():
    """Get authentication token from API.
    Returns cached token if available."""
    global TOKEN
    if TOKEN:
        return TOKEN
    import requests
    response = requests.post('http://127.0.0.1:8000/api/v1/token/', json={
        'username': USERNAME,
        'password': PASSWORD
    })
    if response.status_code == 200:
        TOKEN = response.json()['access']
        print(f'TOKEN: {TOKEN[:20]}...')
        return TOKEN
    else:
        print(f'Login failed: {response.status_code}')
        return None


class AgentUser(HttpUser):
    """Simulated user that sends log messages at random intervals."""
    wait_time = between(0.1, 0.3)

    def on_start(self):
        """Get authentication token when user starts."""
        self.token = get_token_once()

    @task
    def send_log(self):
        """Send a randomly generated log message to the API."""
        if not self.token:
            return
        payload = {
            'level': random.choice(['INFO', 'WARNING', 'ERROR']),
            'message': f'Test log {uuid.uuid4()}',
            'agent_name': f'agent-{random.randint(1, 20)}',
            'timestamp': (
                datetime.datetime.now(datetime.timezone.utc).isoformat()
            ),
            'context': {'cpu': random.randint(0, 100)}
        }
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        self.client.post('/api/v1/logs/', json=payload, headers=headers)
