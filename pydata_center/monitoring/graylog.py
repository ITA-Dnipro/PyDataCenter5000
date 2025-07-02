import logging
import os

import graypy
from celery import shared_task

graylog_logger = logging.getLogger('graylog_logger')
graylog_logger.setLevel(logging.DEBUG)

graylog_host = os.getenv('GRAYLOG_HOST', '127.0.0.1')
graylog_gelf_tcp_port = int(os.getenv('GRAYLOG_GELF_TCP_PORT', '12201'))

tcp_handler = graypy.GELFTCPHandler(graylog_host, graylog_gelf_tcp_port)
graylog_logger.addHandler(tcp_handler)

if not any(
    isinstance(h, graypy.GELFTCPHandler) for h in graylog_logger.handlers
):
    tcp_handler = graypy.GELFTCPHandler(graylog_host, graylog_gelf_tcp_port)
    graylog_logger.addHandler(tcp_handler)


@shared_task
def send_log_to_graylog(level, message, agent_name, timestamp_iso, context):
    """
    Send a log message to Graylog with the specified level, message, and
    context.

    This function uses a shared task to send a log message to Graylog. The
    appropriate log level is determined from the input parameter, and the log
    message is sent along with details such as agent name, timestamp, and
    context.

    Args:
        level (str): The severity level of the log. Valid options are 'DEBUG',
            'INFO', 'WARNING', 'ERROR', and 'CRITICAL'.
        message (str): The log message to be sent to Graylog.
        agent_name (str): The name of the agent associated with the log
            message.
        timestamp_iso (str): The ISO formatted timestamp to include in the log.
        context (dict): Additional context to include with the log message.
            Defaults to an empty dictionary.

    Note:
        This function uses a logger specific to Graylog to route the logs.
    """
    extra = {
        'agent_name': agent_name,
        'timestamp': timestamp_iso,
        'context': context or {},
    }

    level_method = {
        'DEBUG': graylog_logger.debug,
        'INFO': graylog_logger.info,
        'WARNING': graylog_logger.warning,
        'ERROR': graylog_logger.error,
        'CRITICAL': graylog_logger.critical,
    }.get(level.upper())

    if not level_method:
        graylog_logger.warning(
            "Invalid log level '%s' provided. Defaulting to INFO.", level
        )
        level_method = graylog_logger.info

    level_method(message, extra=extra)
