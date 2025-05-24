def maybe_log_error(message, logger, fallback_logger=None):
    try:
        logger.error(message)
    except Exception:
        if fallback_logger:
            fallback_logger.error(message)
