import sys
import logging


def get_fallback_logger():
    """Get emergency fallback logger if logging to file fails."""
    logger = logging.getLogger("CRITICAL")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.ERROR)

        formatter = logging.Formatter("%(name)s: %(message)s")
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
