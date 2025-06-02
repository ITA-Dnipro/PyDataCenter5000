import base64
import json
import logging
import os

import urllib2


def load_env(filename='.env'):
    if not os.path.isfile(filename):
        return
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()


load_env()

# --- Setup logging ---
logger = logging.getLogger('test_agent')
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('agent.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

ip = os.environ.get('CONTROLLER_IP')
port = os.environ.get('CONTROLLER_PORT')
if not ip or not port:
    logger.error('Missing CONTROLLER_IP or CONTROLLER_PORT')
    exit(1)
controller_url = 'http://%s:%s/api/v1/server/status/' % (ip, port)

# --- Example payloads ---
payloads = [
    {
        'hostname': 'web01',
        'ip': '192.168.1.1',
        'uptime': 123.45,
        'timestamp': '2025-06-01 10:00:00',
        'os': 'linux',
        'healthy': True,
        'server_name': 'api01'
    },
    {
        # Missing required 'hostname' (will likely error)
        'ip': '192.168.1.2',
        'uptime': 99.9,
        'timestamp': '2025-06-01 11:00:00',
        'os': 'linux',
        'healthy': False,
        'server_name': 'api02'
    },
    {
        # Invalid IP (will likely error)
        'hostname': 'web02',
        'ip': '999.999.999.999',
        'uptime': 55.0,
        'timestamp': '2025-06-01 12:00:00',
        'os': 'linux',
        'healthy': True,
        'server_name': 'api03'
    }
]


def post_payload(data):
    try:
        json_data = json.dumps(data)

        user = os.environ.get('USERNAME')
        pwd = os.environ.get('PASSWORD')

        if not user or not pwd:
            logger.error('Missing USERNAME or PASSWORD environment variables.')
            return

        credentials = base64.b64encode('%s:%s' % (user, pwd)).strip()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Basic ' + credentials,
        }

        request = urllib2.Request(controller_url, json_data, headers)
        response = urllib2.urlopen(request, timeout=5)
        logger.info('Sending payload to controller: %s', controller_url)
        logger.debug('Payload content: %s', json_data)
        logger.info(
            'Success: %s - Status code: %s' % (
                data.get('server_name'), response.getcode()
            )
        )
    except urllib2.HTTPError as e:
        logger.error('HTTPError (%s): %s' % (e.code, e.read()))
    except urllib2.URLError as e:
        logger.error('URLError: %s' % str(e))
    except Exception:
        logger.exception('Unexpected error:')


def main():
    success, fail = 0, 0
    for payload in payloads:
        try:
            post_payload(payload)
            success += 1
        except Exception:
            fail += 1
    logger.info('Run summary: %d success, %d failed', success, fail)


if __name__ == '__main__':
    main()
