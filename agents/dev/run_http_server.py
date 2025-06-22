import logging
import threading
import time

from BaseHTTPServer import HTTPServer

from agents.dns.dns import DNSAgent
from agents.utils.health_http import HealthHandler

logger = logging.getLogger('test_agent')
logger.setLevel(logging.DEBUG)

fh = logging.FileHandler('agent.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

if __name__ == '__main__':
    try:
        agent = DNSAgent(server_name='myagent', port=8081)
    except OSError as e:
        logger.error('Failed to start health server: %s' % e)
        exit(1)
    logger.info('Health server started on port 8081. Press Ctrl+C to stop.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info('Stopping server.')
