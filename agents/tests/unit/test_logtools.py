import logging
import logging.config
import os
import tempfile

import pytest

from agents.utils import get_fallback_logger, maybe_log_message


@pytest.fixture(scope='session')
def config_logging():
    config = """
[loggers]
keys=fallback

[handlers]
keys=fallback

[formatters]
keys=minimal

[logger_fallback]
level=ERROR
handlers=fallback
qualname=fallback
propagate=0

[handler_fallback]
class=StreamHandler
formatter=minimal
args=(sys.stdout,)

[formatter_minimal]
format=%(levelname)s : %(message)s
style=%
class=logging.Formatter
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, mode='w')
    tmp.write(config)
    tmp.close()

    logging.config.fileConfig(tmp.name)

    yield

    os.remove(tmp.name)


def test_get_fallback_logger_returns_logger():
    assert isinstance(get_fallback_logger(), logging.Logger)
