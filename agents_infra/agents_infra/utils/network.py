import json
import logging
import socket

import urllib2
from logtools import maybe_log_message
from urlparse import urljoin, urlparse


def is_tcp_reachable(url, timeout=3, logger=None):
    """
    Checks whether a TCP connection can be established to the host
    and port derived from the URL.

    Args:
        url (str): The target URL to check.
        timeout (int, optional): Timeout in seconds for the connection.
        Defaults to 3.
        logger (logging.Logger, optional): Logger for structured logging.

    Returns:
        bool: True if reachable, False otherwise.
    """
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)

        sock = socket.create_connection((host, port), timeout)
        sock.close()
        return True
    except Exception as e:
        maybe_log_message(
            f'TCP reachability check failed for {url}: {e}',
            logger=logger,
            level=logging.WARNING
        )
        return False


def check_http_health(
        url,
        api_key=None,
        auth_token_type=None,
        timeout=3,
        health_path='/health',
        logger=None):
    """
    Performs a GET request to the URL's health endpoint and checks
    if the status is healthy.

    Args:
        url (str): Base controller URL.
        api_key (str, optional): API key for authentication.
        auth_token_type (str, optional): Authorization token type
        (e.g., 'Bearer').
        timeout (int, optional): Timeout for the request in seconds.
        Defaults to 3.
        health_path (str, optional): Endpoint to hit for health check.
        Defaults to '/health'.
        logger (logging.Logger, optional): Logger for structured logging.

    Returns:
        bool: True if the controller reports healthy status, False otherwise.
    """
    headers = {'Content-Type': 'application/json'}

    if api_key and auth_token_type:
        if not isinstance(api_key, str) or not isinstance(
                auth_token_type, str
        ):
            maybe_log_message(
                'Invalid API key or token type format.'
                ' Must be strings.',
                logger=logger,
                level=logging.WARNING
            )
            return False
        headers['Authorization'] = f'{auth_token_type} {api_key}'

    health_url = url.rstrip('/') + health_path

    try:
        req = urllib2.Request(health_url, headers=headers)
        response = urllib2.urlopen(req, timeout=timeout)
        body = response.read()
        data = json.loads(body)
        return data.get('status') == 'healthy'
    except (
            urllib2.URLError,
            urllib2.HTTPError,
            socket.timeout,
            ValueError
    ) as e:
        maybe_log_message(
            f'HTTP health check failed for {url}: {e}',
            logger=logger,
            level=logging.WARNING
        )
        return False


def ping_url(
        url,
        api_key=None,
        auth_token_type=None,
        logger=None,
        timeout=3
):
    """
    Performs a TCP-level and HTTP health check for the given URL.

    Args:
        url (str): The URL to check.
        api_key (str, optional): API key for the health check request.
        auth_token_type (str, optional): Auth token type for headers.
        logger (logging.Logger, optional): Logger for structured logging.
        timeout (int, optional): Timeout in seconds. Defaults to 3.

    Returns:
        bool: True if both TCP and health checks succeed, False otherwise.
    """
    if not is_tcp_reachable(url, timeout, logger=logger):
        maybe_log_message(
            f'Controller unreachable at TCP level: {url}',
            logger=logger,
            level=logging.WARNING
        )
        return False

    healthy = check_http_health(
        url,
        api_key,
        auth_token_type,
        timeout,
        logger=logger
    )
    if not healthy:
        maybe_log_message(
            f'Health check failed for controller: {url}',
            logger=logger,
            level=logging.ERROR
        )

    return healthy


def find_first_healthy_url(
        urls,
        api_key,
        auth_token_type,
        logger=None,
        timeout=3
):
    """
    Iterates through a list of URLs and returns the first one that is healthy.

    Args:
        urls (list[str]): List of controller URLs to check.
        api_key (str): API key for authentication.
        auth_token_type (str): Type of auth token (e.g., 'Bearer').
        logger (logging.Logger, optional): Logger for logging status messages.
        timeout (int, optional): Timeout for each health check.

    Returns:
        str or None: First healthy URL found, or None if none are healthy.
    """
    for url in urls:
        if ping_url(
            url,
            api_key,
            auth_token_type,
            logger=logger,
            timeout=timeout
        ):
            return url
    return None
