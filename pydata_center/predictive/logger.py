import logging


def setup_logger():
    """
    Configure and return a logger for predictive checks.

    The logger will print INFO-level messages with a timestamp.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
    )
    return logging.getLogger(__name__)
