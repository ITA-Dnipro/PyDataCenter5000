import logging.config
import os
import sys
import tempfile

import mock
import pytest


@pytest.yield_fixture
def setup_temp_file_logging():
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()

    config = {
        'version': 1,
        # 'disable_existing_loggers': True,
        'formatters': {
            'minimal': {
                'format': '%(levelname)s : %(message)s',
            },
        },
        'handlers': {
            'fallback': {
                'class': 'logging.StreamHandler',
                'formatter': 'minimal',
                'level': 'ERROR',
                'stream': 'ext://sys.stderr',
            },
            'file': {
                'class': 'logging.FileHandler',
                'formatter': 'minimal',
                'level': 'INFO',
                'filename': tmp.name,
                'mode': 'w',
            },
        },
        'loggers': {
            'fallback': {
                'handlers': ['fallback'],
                'level': 'ERROR',
                'propagate': False,
            },
            'mock-server-supervisor': {
                'handlers': ['file'],
                'level': 'INFO',
                'propagate': False,
            },
        },
        'root': {
            'handlers': [],
            'level': 'NOTSET',
        },
    }

    logging.config.dictConfig(config)

    yield

    os.remove(tmp.name)


@pytest.fixture
def dummy_supervisor(setup_temp_file_logging):
    from agents.supervisor import AgentSupervisor

    agent = mock.MagicMock()
    agent.server_name = 'mock-server'

    supervisor = AgentSupervisor(agent)

    return supervisor
