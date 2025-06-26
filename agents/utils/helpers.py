import logging
import os
import re
import socket
import subprocess
import time

from .logtools import maybe_log_message


def restart_service(service, attempts=3, logger=None):
    """
    Attempts to restart a system service with exponential backoff
    if it is found to be inactive. Logs each attempt and result.

    Parameters:
        agent (ServerAgent): Agent instance used for logging. Must have
        `logger` and `fallback_logger` attributes.
        service (str): Name of the system service to restart (e.g., 'ssh').

    Returns:
        bool: True if the service was restarted, False otherwise.

    Notes:
        This function uses 'sudo systemctl restart <service>' and expects
        that the agent has sufficient privileges to perform the operation.
        Backoff strategy uses 2s, 4s, and 8s delays between attempts.
    """

    maybe_log_message(
        '%s not active. Attempting restart...' % service, logger=logger
    )

    for i in range(1, attempts + 1):
        try:
            delay = 2**i

            maybe_log_message(
                'Attempt %s: Restarting %s (delay before restart: %s).' % (
                    i,
                    service,
                    delay
                ),
                logger=logger,
            )

            time.sleep(delay)

            retcode = subprocess.call([
                'sudo',
                'systemctl',
                'restart',
                service
                ])

            if retcode == 0:
                maybe_log_message(
                    '%s service restarted successfully.' % service,
                    logger=logger,
                    level=logging.INFO
                    )
                return True  # If restsrting successful
            else:
                maybe_log_message(
                    '%s restart failed with code %s.' % (service, retcode),
                    logger=logger,
                )

        except Exception as restart_err:
            maybe_log_message(
                'Error during %s service restart: %s' % (
                    service, restart_err
                ),
                logger=logger,
                exc_info=True,
            )
            return False  # Stop after first fatal error
    return False  # If restarting failed


def is_valid_ip(output):
    try:
        socket.inet_aton(output.strip())
        return True
    except socket.error:
        return False


def get_env_or_param(param_value, env_name):
    """
    Get value from parameter or environment variable.

    Args:
        param_value: Value passed as parameter
        env_name (str): Name of environment variable

    Returns:
        The parameter value if provided, otherwise environment variable

    Raises:
        ValueError: If neither parameter nor environment variable is set
    """
    if param_value is None and env_name not in os.environ:
        raise ValueError('%s environment variable is not set.' % env_name)
    return param_value or os.environ[env_name]
