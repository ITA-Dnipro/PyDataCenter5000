import logging

from agents.utils import get_fallback_logger, maybe_log_message


def test_get_fallback_logger_returns_logger(temp_file_logging):
    """
    Test that get_fallback_logger returns an instance of logger if
    configured.
    """
    assert isinstance(get_fallback_logger(), logging.Logger)
