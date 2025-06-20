import logging

import mock

from agents.utils import get_fallback_logger, maybe_log_message


def test_get_fallback_logger_returns_logger():
    """
    Test that get_fallback_logger always returns the same instance of
    logger.
    """
    logger1 = get_fallback_logger()
    assert isinstance(logger1, logging.Logger)

    assert get_fallback_logger() is logger1


def test_maybe_log_message_logger_called():
    """Test logger is called with appropriate parameters."""
    logger = mock.Mock()

    maybe_log_message(
        'Dummy message', logger=logger, level=logging.INFO, param='foo'
    )

    logger.log.assert_called_with(logging.INFO, 'Dummy message', param='foo')


def test_maybe_log_message_exception_handled(caplog):
    class DummyLogger(object):
        def log(self, level, message, *args, **kwargs):
            raise RuntimeError('Something went wrong')

    with caplog.at_level(logging.INFO):
        maybe_log_message(
            'Dummy message', logger=DummyLogger(), level=logging.ERROR
        )

    assert 'Dummy message' in caplog.text
