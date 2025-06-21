import logging
import os
import sys
import tempfile
from io import StringIO

import mock
import pytest


@pytest.yield_fixture
def setup_temp_file_logging():
    """
    Setup the primary file logger and the fallback stream logger for
    tests.
    """
    # Temporarily redirect stderr (fallback logging destination).
    stderr = sys.stderr
    sys.stderr = StringIO()

    config = tempfile.NamedTemporaryFile(delete=False)
    log = tempfile.NamedTemporaryFile(delete=False)

    config.write("""
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
args=('%(filename)s', 'w')

[formatter_minimal]
class=logging.Formatter
    """)

    config.close()
    log.close()

    logging.config.fileConfig(
        config.name, defaults={'filename': log.name}
    )

    yield

    os.remove(config.name)
    os.remove(log.name)

    sys.stderr = stderr


@pytest.fixture
def dummy_supervisor(setup_temp_file_logging, monkeypatch):
    from agents.supervisor import AgentSupervisor

    @property
    def mock_logger(self):
        return logging.getLogger('mock-logger')

    monkeypatch.setattr(AgentSupervisor, 'logger', mock_logger)

    agent = mock.MagicMock()
    supervisor = AgentSupervisor(agent)

    return supervisor
