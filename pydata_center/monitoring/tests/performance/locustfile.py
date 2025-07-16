"""
Locust load testing configuration and environment variables.

Environment Variables:
- LOCUST_USERNAME (str): Username for login. Default: 'locust_tester'
- LOCUST_PASSWORD (str): Password for login. Default: 'supersecret'
- TOXI_CLEANUP_DELAY (float): Seconds to wait after
removing toxics before ending test. Default: 2
- TOXIPROXY_API (str): URL for Toxiproxy API. Default: 'http://localhost:8474'
- PROXY_NAME (str): Name of the Toxiproxy proxy. Default: 'django-proxy'
- TOXI_LATENCY (int): Network latency in milliseconds for toxics. Default: 500
- TOXI_JITTER (int): Network jitter in milliseconds for toxics. Default: 100
- TOXI_RATE (int): Bandwidth rate limit for toxics
(bytes per second). Default: 80000
- ENABLE_TOXICS (bool): Enable or disable toxic injection. Default: True
- MAX_REFRESH_RETRIES (int): Number of times to retry
request after token refresh. Default: 2
"""


import logging
import os
import random
import string
import time
from datetime import datetime

import requests
from locust import HttpUser, between, events, task

logger = logging.getLogger(__name__)

API_PREFIX = '/api/v1'

# Authentication credentials for login (can be overridden by env variables)
USERNAME = os.getenv('LOCUST_USERNAME', 'locust_tester')
PASSWORD = os.getenv('LOCUST_PASSWORD', 'supersecret')

# Toxiproxy config
TOXI_CLEANUP_DELAY = float(os.getenv('TOXI_CLEANUP_DELAY', '2'))
TOXIPROXY_API = os.getenv('TOXIPROXY_API', 'http://localhost:8474')
PROXY_NAME = os.getenv('PROXY_NAME', 'django-proxy')

# Network toxics settings
LATENCY_MS = int(os.getenv('TOXI_LATENCY', '500'))
JITTER_MS = int(os.getenv('TOXI_JITTER', '100'))
RATE_LIMIT = int(os.getenv('TOXI_RATE', '80000'))
ENABLE_TOXICS = os.getenv('ENABLE_TOXICS', 'true').lower() == 'true'

# Retry settings
MAX_REFRESH_RETRIES = int(os.getenv('MAX_REFRESH_RETRIES', '2'))


def random_hostname():
    """
    Generate a random hostname string for a simulated agent.

    Returns:
        str: Hostname in format 'agent-XXXX' where X are digits.
    """
    return 'agent-' + ''.join(random.choices(string.digits, k=4))


def ensure_proxy():
    """
    Ensure the Toxiproxy proxy exists with the expected configuration.

    If missing or misconfigured, it will be created or replaced.

    Raises:
        SystemExit: If there is an error communicating with the Toxiproxy API.
    """
    expected_upstream = '127.0.0.1:8000'
    expected_listens = ['0.0.0.0:9000', '[::]:9000']

    try:
        r = requests.get(f'{TOXIPROXY_API}/proxies/{PROXY_NAME}')
        if r.status_code == 200:
            cfg = r.json()
            actual_listen = cfg.get('listen')
            actual_upstream = cfg.get('upstream')

            listen_mismatch = actual_listen not in expected_listens
            upstream_mismatch = actual_upstream != expected_upstream

            if listen_mismatch or upstream_mismatch:
                logger.warning(
                    f'Proxy config mismatch. '
                    f'Expected listen in {expected_listens} '
                    f'and upstream {expected_upstream}, '
                    f'got listen={actual_listen}, upstream={actual_upstream}. '
                    f'Recreating...'
                )
                requests.delete(f'{TOXIPROXY_API}/proxies/{PROXY_NAME}')
                r = None  # Reset to trigger creation block

        if r is None or r.status_code == 404:
            logger.info(
                f'Proxy \'{PROXY_NAME}\' not found or deleted. Creating...'
            )
            create_resp = requests.post(f'{TOXIPROXY_API}/proxies', json={
                'name': PROXY_NAME,
                'listen': '0.0.0.0:9000',  # Or switch to '[::]:9000' if needed
                'upstream': expected_upstream
            })
            create_resp.raise_for_status()
            logger.info(f'Proxy \'{PROXY_NAME}\' created.')
        else:
            r.raise_for_status()
            logger.info(
                f'Proxy \'{PROXY_NAME}\' is available '
                f'and correctly configured.'
            )

    except requests.exceptions.RequestException as e:
        logger.error(f'Could not ensure proxy \'{PROXY_NAME}\': {e}')
        raise SystemExit(1)


def add_toxics():
    """
    Add network toxics (latency and bandwidth limit)

    to the proxy to simulate network instability.
    """
    logger.info('Adding toxics...')
    ensure_proxy()

    toxics = [
        {
            'name': 'laggy',
            'type': 'latency',
            'stream': 'downstream',
            'toxicity': 1.0,
            'attributes': {
                'latency': LATENCY_MS,
                'jitter': JITTER_MS
            }
        },
        {
            'name': 'choppy',
            'type': 'limit_data',
            'stream': 'downstream',
            'toxicity': 1.0,
            'attributes': {
                'rate': RATE_LIMIT
            }
        }
    ]

    for toxic in toxics:
        try:
            r = requests.post(
                f'{TOXIPROXY_API}/proxies/{PROXY_NAME}/toxics',
                json=toxic
            )
            r.raise_for_status()
            logger.info(f'Toxic \'{toxic["name"]}\' configured.')
        except requests.exceptions.RequestException as e:
            logger.error(f'Failed to add toxic \'{toxic["name"]}\': {e}')


def remove_toxics():
    """
    Remove the configured toxics ('laggy', 'choppy')

    from the proxy to restore normal network behavior.
    """
    logger.info('Removing toxics...')

    for name in ['laggy', 'choppy']:
        try:
            r = requests.delete(
                f'{TOXIPROXY_API}/proxies/{PROXY_NAME}/toxics/{name}'
            )
            if r.status_code in (200, 204):
                logger.info(f'Toxic \'{name}\' removed.')
            elif r.status_code == 404:
                logger.info(f'Toxic \'{name}\' not found.')
            else:
                logger.warning(
                    f'Unexpected status while removing '
                    f'\'{name}\': {r.status_code}'
                )
        except requests.exceptions.RequestException as e:
            logger.error(f'Error removing toxic \'{name}\': {e}')


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """
    Locust event hook that runs once when the test starts.

    If toxics are enabled and the target host is not localhost:8000,
    it will add network toxics to simulate instability.
    """
    if (ENABLE_TOXICS and environment.host and environment.host !=
            'http://localhost:8000'):
        add_toxics()
    else:
        logger.info('🟡 Toxic injection disabled or no proxy target set')


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    Locust event hook that runs once when the test stops.

    Removes network toxics if they were added.
    """
    if (ENABLE_TOXICS and environment.host and environment.host !=
            'http://localhost:8000'):
        remove_toxics()
        time.sleep(TOXI_CLEANUP_DELAY)


class AgentSimulator(HttpUser):
    """
    Locust user class simulating an agent that authenticates, sends status,
    fetches commands, and submits command results to the backend.
    """
    wait_time = between(1, 3)
    host = os.getenv('LOCUST_TARGET', 'http://localhost:8000')

    def on_start(self):
        """
        Called once when a simulated user starts.

        Logs in to obtain a token, initializes hostname and IP,
        and fetches any pending command IDs.
        """
        self.active = False
        resp = None
        for attempt in range(1, 4):
            try:
                resp = self.client.post(
                    f'{API_PREFIX}/token/',
                    name='/token/',
                    json={'username': USERNAME, 'password': PASSWORD}
                )
                if resp.status_code == 200:
                    break
                else:
                    logger.warning(
                        f'Login attempt {attempt} failed: '
                        f'{resp.status_code} - {resp.text.strip()}'
                    )

            except Exception as e:
                logger.warning(f'Login attempt {attempt} failed: {e}')
            time.sleep(0.5)
        else:
            logger.error('Login failed after 3 attempts.')
            return

        try:
            token = resp.json()['access']
            self.client.headers.update({'Authorization': f'Bearer {token}'})
        except Exception as e:
            logger.error(f'Failed to extract token: {e}')
            return

        self.hostname = random_hostname()
        self.ip = f'192.168.1.{random.randint(2, 254)}'

        try:
            pending = self.client.get(
                f'{API_PREFIX}/commands/',
                name='/commands/',
                params={'hostname': self.hostname, 'status': 'pending'}
            )
            if pending.status_code == 200:
                self.valid_ids = [cmd['id'] for cmd in pending.json()]
            else:
                self.valid_ids = []
        except Exception as e:
            logger.warning(f'Failed to fetch pending commands: {e}')
            self.valid_ids = []

        self.active = True

    def _request_with_refresh(self, method, *args, **kwargs):
        """
        Retry the request if it fails due to token expiration (401).
        Retry up to MAX_REFRESH_RETRIES times.

        Args:
            method: self.client.get/post/patch/etc
            *args, **kwargs: passed to the method

        Returns:
            Response object or None if all attempts fail
        """
        for attempt in range(1, MAX_REFRESH_RETRIES + 2):
            try:
                response = method(*args, **kwargs)
                if response.status_code != 401:
                    return response
                logger.warning(
                    f'Attempt {attempt}: Token expired. Refreshing token...'
                )
                self.on_start()  # Refresh token
            except Exception as e:
                logger.warning(f'Attempt {attempt} failed with error: {e}')
            time.sleep(0.5)

        logger.error(
            f'All {MAX_REFRESH_RETRIES + 1} '
            f'attempts failed in _request_with_refresh.'
        )
        return None

    @task(3)
    def send_status(self):
        """
        Simulate sending periodic status updates to the server.

        Posts server health info like uptime, OS, IP, etc.
        """
        if not getattr(self, 'active', False):
            return
        try:
            self._request_with_refresh(
                self.client.post,
                f'{API_PREFIX}/server/status/',
                name='/server/status/',
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
        except Exception as e:
            logger.warning(f'Failed to send status for {self.hostname}: {e}')

    @task(1)
    def fetch_pending(self):
        """
        Fetch a pending command for this agent.

        Adds the command ID to valid_ids if status is 'pending'.
        """
        if not getattr(self, 'active', False):
            return
        r = self._request_with_refresh(
            self.client.get,
            f'{API_PREFIX}/command/fetch/',
            name='/command/fetch/',
            params={'hostname': self.hostname}
        )
        if r.status_code == 200:
            cmd = r.json()
            if cmd.get('status') == 'pending':
                self.valid_ids.append(cmd['id'])

    @task(1)
    def submit_result(self):
        """
        Submit results for a random pending command.

        Randomly marks command as 'done' or 'failed'

        with simulated result data. Handles token expiration
        and 400s for already-handled commands.
        """
        if not getattr(self, 'active', False) or not self.valid_ids:
            return

        cmd_id = random.choice(self.valid_ids)
        try:
            resp = self._request_with_refresh(
                self.client.patch,
                f'{API_PREFIX}/command/result/',
                name='/command/result/',
                json={
                    'id': cmd_id,
                    'status': random.choice(['done', 'failed']),
                    'result': 'simulated-result',
                }
            )
            if resp.status_code == 200:
                self.valid_ids.remove(cmd_id)
            elif resp.status_code == 400:
                logger.info(
                    f'Command {cmd_id} no longer pending; removing from list'
                )
                self.valid_ids.remove(cmd_id)
        except Exception as e:
            logger.warning(f'submit_result failed for {cmd_id}: {e}')
