import sys
import logging


def get_fallback_logger(name, level=logging.ERROR, formatter=None):
    """Get fallback logger with stderr handler."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)

        formatter = (
            formatter
            or logging.Formatter(
                "%(name)s - %(asctime)s - %(levelname)s - %(message)s"
            )
        )
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
