import datetime
import logging
import os
import random
import uuid

from dotenv import load_dotenv
from locust import HttpUser, between, task

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

USERNAME = os.getenv('LOCUST_USERNAME', 'user')
PASSWORD = os.getenv('LOCUST_PASSWORD', 'password')

logger.info(f'USERNAME: {USERNAME}')
logger.info(f'PASSWORD: {PASSWORD}')


class AgentUser(HttpUser):
    """Simulated user that sends log messages at random intervals."""
    wait_time = between(0.1, 0.3)
    token = None

    def on_start(self):
        """Get authentication token when user starts."""
        if not AgentUser.token:
            AgentUser.token = self.get_token()
        self.token = AgentUser.token

    def get_token(self):
        import requests
        response = requests.post('http://127.0.0.1:8000/api/v1/token/', json={
            'username': USERNAME,
            'password': PASSWORD
        })
        if response.status_code == 200:
            token = response.json()['access']
            logger.info(f'TOKEN: {token[:20]}...')
            return token
        else:
            logger.error(f'Login failed: {response.status_code}')
            return None

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
