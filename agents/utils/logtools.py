import logging


def maybe_log_message(
    message, logger, fallback_logger=None, level=logging.ERROR,
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
    try:
        logger.log(level, message)
    except Exception:
        if fallback_logger:
            fallback_logger.log(level, message)
