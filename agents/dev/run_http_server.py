import logging
import threading
import time

from BaseHTTPServer import HTTPServer

from agents.dns.dns import DNSAgent
from agents.utils.health_http import HealthHandler

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    agent = DNSAgent(server_name='myagent', port=8081)
    print('Health server started on port 8081. Press Ctrl+C to stop.')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print('Stopping server.')
