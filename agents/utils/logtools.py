import logging


def maybe_log_message(
    message, logger, fallback_logger=None, level=logging.ERROR,
):
    try:
        logger.log(level, message)
    except Exception:
        if fallback_logger:
            fallback_logger.log(level, message)
