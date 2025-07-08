import json
import socket

import urllib2
from urlparse import urljoin, urlparse


def is_tcp_reachable(url, timeout=3):
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)

    try:
        sock = socket.create_connection((host, port), timeout)
        sock.close()
        return True
    except socket.error:
        return False


def check_http_health(url, api_key=None, auth_token_type=None, timeout=3):
    headers = {'Content-Type': 'application/json'}
    if api_key and auth_token_type:
        headers['Authorization'] = f'{auth_token_type} {api_key}'

    health_url = url.rstrip('/') + '/health'

    try:
        req = urllib2.Request(health_url, headers=headers)
        response = urllib2.urlopen(req, timeout=timeout)

        body = response.read()
        data = json.loads(body)

        return data.get('status') == 'healthy'
    except (urllib2.URLError, urllib2.HTTPError, socket.timeout, ValueError):
        return False
