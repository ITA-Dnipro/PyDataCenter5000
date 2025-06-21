import logging
import sys

from agents.utils import get_fallback_logger, maybe_log_message


def test_get_fallback_logger_returns_logger(
    setup_temp_file_logging_with_fallback
):
    """
    Test that get_fallback_logger always returns the same instance of
    logger.
    """
    logger1 = get_fallback_logger()
    assert isinstance(logger1, logging.Logger)

    assert get_fallback_logger() is logger1


def test_maybe_log_message_logged(
    setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    """Test logger is called with appropriate parameters."""
    logger = logging.getLogger('mock-logger')

    maybe_log_message('Dummy message', logger=logger, level=logging.INFO)

    assert_msg_in_logfile('Dummy message')


def test_maybe_log_message_logged_with_fallback_logger(
    setup_temp_file_logging_with_fallback
):
    class DummyLogger(object):
        def log(self, level, message, *args, **kwargs):
            raise RuntimeError('Something went wrong')

    maybe_log_message(
        u'Dummy message', logger=DummyLogger(), level=logging.ERROR
    )

    assert u'Dummy message' in sys.stderr.getvalue()
