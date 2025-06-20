import logging
import os
import sys
import tempfile

import mock
import pytest


@pytest.yield_fixture
def setup_temp_file_logging():
    config_file = tempfile.NamedTemporaryFile(delete=False)
    log_file = tempfile.NamedTemporaryFile(delete=False)

    config_file.write("""
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

    config_file.close()
    log_file.close()

    logging.config.fileConfig(
        config_file.name, defaults={'filename': log_file.name}
    )

    yield

    os.remove(config_file.name)
    os.remove(log_file.name)


@pytest.fixture
def mock_supervisor(setup_temp_file_logging, monkeypatch):
    from agents.supervisor import AgentSupervisor

    agent = mock.MagicMock()

    supervisor = AgentSupervisor(agent)
    monkeypatch(supervisor, 'logger', logging.getLogger('mock-logger'))

    return supervisor
