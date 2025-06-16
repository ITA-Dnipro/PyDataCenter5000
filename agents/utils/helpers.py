import logging
import re
import subprocess
import time

from .logtools import maybe_log_message


def restart_service(logger, fallback_logger, service, attempts=3):
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
        '%s not active. Attempting restart...' % service,
        logger,
        fallback_logger=fallback_logger
        )

    for i in range(1, attempts+1):
        try:
            delay = 2**i

            maybe_log_message(
                'Restarting %s (delay before restart: %s).' % (service, delay),
                logger,
                fallback_logger=fallback_logger
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
                    logger,
                    fallback_logger=fallback_logger,
                    level=logging.INFO
                    )
                return True  # If restsrting successful
            else:
                maybe_log_message(
                    '%s restart failed with code %s.' % (service, retcode),
                    logger,
                    fallback_logger=fallback_logger
                    )

        except Exception as restart_err:
            maybe_log_message(
                'Error during %s service restart: %s' % (
                    service,
                    restart_err),
                logger,
                fallback_logger=fallback_logger,
                exc_info=True
                )
            return False  # Stop after first fatal error
    return False  # If restarting failed


def is_valid_ip(output):
    """
    Validate if the output is a correctly formatted IPv4 address.
    Returns:
        bool: True if the output is a valid IP address, False otherwise.
    """
    return re.match(r'^\d{1,3}(\.\d{1,3}){3}$', output.strip()) is not None
