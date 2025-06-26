import errno
import logging
import os
from logging.handlers import TimedRotatingFileHandler

import pkg_resources

LOG_CONFIG_PATH = pkg_resources.resource_filename(
    'agents_infra.config', 'logging.ini'
)


def get_fallback_logger():
    return logging.getLogger('fallback')


def maybe_log_message(
    message, logger, fallback_logger=None, level=logging.ERROR, **kwargs
):
    """
    Helper function allowing to log a message with fallback behaviour.

    Parameters:
        message (str): Log message.
        logger (logging.Logger): Primary logger.
        fallback_logger (logging.Logger): Fallback logger that will try
            logging the message if the primary logger fails due to exception.
            Default is None. If not set, fallback behaviour will not be
            triggered.
        level (int): Log level. Default is logging.ERROR.
    """
    if logger:
        try:
            logger.log(level, message, **kwargs)
        except Exception:
            if not fallback_logger:
                fallback_logger = get_fallback_logger()

            fallback_logger.log(level, message, **kwargs)


def maybe_make_dir(path):
    """Create parent directory for path if it doesn't exist"""
    dirpath = os.path.dirname(path)

    if dirpath and not os.path.exists(dirpath):
        try:
            os.makedirs(dirpath)
        except OSError as e:
            # Pass if race condition, otherwise something is very wrong
            if e.errno != errno.EEXIST or not os.path.isdir(dirpath):
                raise


class CustomTimedRotatingHandler(TimedRotatingFileHandler, object):

    def __init__(
        self,
        filename,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8',
        delay=False,
        utc=False,
    ):
        maybe_make_dir(filename)

        super(CustomTimedRotatingHandler, self).__init__(
            filename,
            when,
            interval,
            backupCount,
            encoding,
            delay,
            utc,
        )
