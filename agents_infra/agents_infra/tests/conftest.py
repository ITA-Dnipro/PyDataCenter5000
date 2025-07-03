import logging
import logging.config
import os
import sys
import tempfile

import mock
import pytest
from StringIO import StringIO


@pytest.fixture
def setup_temp_file_logging_with_fallback(request):
    """
    Setup a temporary file logger and fallback stderr logger for tests.
    """
    original_stderr = sys.stderr
    sys.stderr = StringIO()

    config_file = tempfile.NamedTemporaryFile(delete=False)
    log_file = tempfile.NamedTemporaryFile(delete=False)
    config_path = config_file.name
    log_path = log_file.name

    config_content = """
[loggers]
keys=root,fallback,supervisor

[handlers]
keys=fallback,file

[formatters]
keys=minimal

[logger_root]
level=NOTSET
handlers=

[logger_fallback]
level=ERROR
handlers=fallback
qualname=fallback
propagate=0

[logger_supervisor]
level=INFO
handlers=file
qualname=mock-logger
propagate=0

[handler_fallback]
class=StreamHandler
formatter=minimal
args=(sys.stderr,)

[handler_file]
class=FileHandler
formatter=minimal
args=('%s', 'w')

[formatter_minimal]
class=logging.Formatter
format=%%(asctime)s - %%(name)s - %%(levelname)s - %%(message)s
""" % log_path

    config_file.write(config_content)
    config_file.close()
    log_file.close()

    logging.config.fileConfig(config_path)

    def teardown():
        if os.path.exists(config_path):
            os.remove(config_path)
        if os.path.exists(log_path):
            os.remove(log_path)
        sys.stderr = original_stderr

    request.addfinalizer(teardown)

    return log_path


@pytest.fixture
def assert_msg_in_logfile(setup_temp_file_logging_with_fallback):
    def wrapped(msg):
        logger = logging.getLogger('mock-logger')
        handler = None
        for h in logger.handlers:
            if isinstance(h, logging.FileHandler):
                handler = h
                break

        if not handler:
            raise RuntimeError('No file handler found in mock-logger')

        with open(handler.baseFilename, 'r') as f:
            contents = f.read()

        assert msg in contents, (
            'Expected log message "%s" not found. Log contents:\n%s'
            % (msg, contents)
        )

    return wrapped


@pytest.fixture
def dummy_supervisor(setup_temp_file_logging_with_fallback, monkeypatch):
    from ..supervisor import AgentSupervisor

    def get_logger(self):
        return logging.getLogger('mock-logger')

    monkeypatch.setattr(AgentSupervisor, 'logger', property(get_logger))

    agent = mock.MagicMock()
    supervisor = AgentSupervisor(agent)

    return supervisor
