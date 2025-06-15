import logging
import os
import tempfile
from logging.handlers import MemoryHandler

import pytest
from mock import patch

from agents.web.web import WebAgent


@pytest.yield_fixture
def web_agent():
    """Fixture to create a WebAgent instance with required environment setup"""
    os.environ['PORT'] = '8000'

    logfile = tempfile.NamedTemporaryFile(delete=False)
    logfile.close()

    agent = WebAgent(log_path=logfile.name)

    handler = MemoryHandler(capacity=10000)
    agent.logger.addHandler(handler)
    agent.logger.setLevel(logging.INFO)

    yield agent, handler

    if os.path.exists(logfile.name):
        os.remove(logfile.name)
