import logging
import re
import subprocess
import sys
import time

import ConfigParser
import pkg_resources

from .logtools import maybe_log_message


def load_global_config():
    """Attempt loading agents global config file at agents/global.ini."""
    config = ConfigParser.ConfigParser()
    files = config.read(
        pkg_resources.resource_filename('agents', 'global.ini')
    )

    if not files:
        sys.stderr.write(
            '[WARN] Global config file not found - '
            'falling back to default values'
        )

    if config.sections():
        return config


def parse_csv_list(value):
    """Parse a comma-separated string into a list of strings."""
    if not isinstance(value, (str, unicode)):
        raise TypeError('Expected a string as input, got %s' % type(value))

    if not value:
        return []

    return [elem.strip() for elem in value.split(',')]


def get_config_option(
    config,
    section,
    option,
    default=None,
    logger=None,
    fallback_logger=None,
    cast=None,
):
    """
    Helper function to get a config option from a config parser falling
    back to a default value if data not found. If NoSectionError or
    NoOptionError arises and a logger is provided, logging is attempted.

    Parameters:
        config (ConfigParser.ConfigParser): Config parser.
        section (str): Section name.
        option (str): Option name.
        default (Any): Fallback value. Default is None.
        logger (logging.Logger): Primary logger. Default is None (no logging).
        fallback_logger (logging.Logger): Fallback logger. Default is
            None.
        cast (Callable): Callable to convert the option value to a required
            type or form. For example, use `int` for integers and `float`
            for floats. To implement custom logic, a lambda-function
            should be passed. On cast failure or if cast function is not
            provided, the original string returned by ConfigParser will
            be returned. Default is None.

    Returns:
        Any: Option value.

    Notes:
        Note that by default, section names are case-sensitive, whereas
        option-names are case-insensitive.
    """
    try:
        value = config.get(section, option)

        if cast:
            try:
                value = cast(value)
            except (TypeError, ValueError) as e:
                maybe_log_message(
                    (
                        'Could not cast option value '
                        '%s due to error: %s' % (value, str(e))
                    ),
                    logger,
                    fallback_logger=fallback_logger,
                )
                return value

    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError) as e:
        if logger:
            maybe_log_message(
                'Config not found [%s] %s: %s' % (section, option, str(e)),
                logger,
                fallback_logger=fallback_logger,
                level=logging.WARNING,
            )

    return value or default


def is_valid_ip(output):
    """
    Validate if the output is a correctly formatted IPv4 address.
    Returns:
        bool: True if the output is a valid IP address, False otherwise.
    """
    return re.match(r'^\d{1,3}(\.\d{1,3}){3}$', output.strip()) is not None


def restart_service(agent, service):
    """
    Attempts to restart a system service with exponential backoff
    if it is found to be inactive. Logs each attempt and result.

    Parameters:
        agent (ServerAgent): Agent instance used for logging. Must have
            `logger` and `fallback_logger` attributes.
        service (str): Name of the system service to restart (e.g., 'ssh').

    Returns:
        bool: True if the service was restarted successfully, False otherwise.

    Notes:
        This function uses 'sudo systemctl restart <service>' and expects
        that the agent has sufficient privileges to perform the operation.
        Backoff strategy uses 2s, 4s, and 8s delays between attempts.
    """

    maybe_log_message(
        '%s not active. Attempting restart...' % service,
        agent.logger,
        fallback_logger=agent.fallback_logger
    )

    delays = [2, 4, 8]
    for delay in delays:
        try:
            maybe_log_message(
                'Restarting %s (delay before restart: %s).' % (service, delay),
                agent.logger,
                fallback_logger=agent.fallback_logger
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
                    agent.logger,
                    fallback_logger=agent.fallback_logger
                )
                return True
            else:
                maybe_log_message(
                    '%s restart failed with code %s.' % (service, retcode),
                    agent.logger,
                    fallback_logger=agent.fallback_logger
                )

        except Exception as restart_err:
            maybe_log_message(
                'Error during %s service restart: %s' % (service, restart_err),
                agent.logger,
                fallback_logger=agent.fallback_logger,
                exc_info=True
            )
            return False  # Stop after first fatal error

    return False  # If restsrting failed
