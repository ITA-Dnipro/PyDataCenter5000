import logging
import sys

from agents.utils import get_fallback_logger, maybe_log_message


def test_get_fallback_logger_returns_logger():
    """
    Test that get_fallback_logger always returns the same instance of
    logger.
    """
    logger1 = get_fallback_logger()
    assert isinstance(logger1, logging.Logger)

    assert get_fallback_logger() is logger1


def test_maybe_log_message_logged(setup_temp_file_logging):
    """Test logger is called with appropriate parameters."""
    logger = logging.getLogger('mock-logger')

    maybe_log_message('Dummy message', logger=logger, level=logging.INFO)

    with open(logger.handlers[0].baseFilename, 'r') as f:
        f.seek(0)
        contents = f.read()

    assert 'Dummy message' in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            'Dummy message', contents
        )
    )


def test_maybe_log_message_logged_with_fallback_logger(
    setup_temp_file_logging
):
    class DummyLogger(object):
        def log(self, level, message, *args, **kwargs):
            raise RuntimeError('Something went wrong')

    try:
        maybe_log_message(
            u'Dummy message', logger=DummyLogger(), level=logging.ERROR
        )

        assert u'Dummy message' in sys.stderr.getvalue()
    finally:
        pass
