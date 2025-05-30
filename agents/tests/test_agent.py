import os
import socket
import tempfile
import types

import mock
import pytest
import requests

from agents.agent import ServerAgent


class MockAgent(ServerAgent):

    def __init__(
        self,
        server_name='mock',
        port=None,
        processes=None,
        controller_url=None,
        config_file=None,
    ):
        super(MockAgent, self).__init__(
            server_name, port, processes, controller_url, config_file
        )

    def setup_logging(self, path=None):
        if not path:
            self.logfile = tempfile.NamedTemporaryFile(delete=False)
            self.logfile.close()

            path = self.logfile.name

        return super(MockAgent, self).setup_logging(path)

    def __del__(self):
        if self.log_path:
            os.remove(self.log_path)


def test_type_checks_on_init():
    """Test that type checks fail initialization with bad parameters."""
    with pytest.raises(TypeError):
        MockAgent(port='invalid')

    with pytest.raises(TypeError):
        MockAgent(processes=0)


def test_type_checks_on_config_parse():
    """
    Test that type checks fail initialization with bad config file
    parameters.
    """
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write('[server]\nname=mock\nport=invalid\nprocesses=proc1')
        tmp.flush()

        with pytest.raises(TypeError):
            MockAgent.from_config_file(tmp.name)


def test_status_to_json_type_error():
    """
    Test that the TypeError is handled and logged on JSON serialization
    failure.
    """
    class MockUnserializableParameter(object):
        def __str__(self):
            raise TypeError("Can't serialize me")

    def mock_status_to_dict(self):
        status = ServerAgent.status_to_dict(self)
        status.update({'mock_parameter': MockUnserializableParameter()})
        return status

    agent = MockAgent(port=12345)
    agent.setup_logging()

    agent.status_to_dict = types.MethodType(mock_status_to_dict, agent)

    agent.status_to_json()

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = (
        'JSON serialization of status failed due to error: '
        "Can't serialize me"
    )

    assert msg in contents, (
        'Expected %s in logs, got:\n%s' % (msg, contents)
    )


def test_status_to_controller_success():
    """
    Test that successful POST request to controller is properly handled
    and logged.
    """
    def mock_post(*args, **kwargs):
        class MockResponse(object):
            def __init__(self, status_code=201, text='Success'):
                self.status_code = status_code
                self.text = self.reason = text
                self.url = 'http://mock/api/status/'

            def raise_for_status(self):
                pass

        return MockResponse()

    agent = MockAgent(port=12345)
    agent.setup_logging()

    agent.collect_server_metadata()

    agent.controller_url = 'http://mock/api/status/'

    with mock.patch('requests.post', mock_post):
        agent.status_to_controller()

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    assert 'POST request status: 201' in contents, (
        'Expected "POST request status: 201" in logs, got:\n%s' % contents
    )


def test_status_to_controller_missing_url():
    """Test that missing controller URL is properly handled and logged."""
    agent = MockAgent(port=12345)
    agent.setup_logging()
    agent.collect_server_metadata()

    # Set controller's URL explicitly to be independent of changes
    # of default values in agent.py/
    agent.controller_url = None

    agent.status_to_controller()

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = "Couldn't send status update: controller URL is not set"

    assert msg in contents, (
        'Expected %s in logs, got:\n%s' % (msg, contents)
    )


def test_status_to_controller_http_error():
    """
    Test that the HTTP and URL failures of POST request to controller are
    properly handled and logged.
    """
    def mock_post(*args, **kwargs):
        class MockResponse(object):
            def __init__(self, status_code=500, text='Internal Server Error'):
                self.status_code = status_code
                self.text = self.reason = text
                self.url = 'http://mock/api/status/'

            def raise_for_status(self):
                raise requests.HTTPError(
                    'HTTP Error %s: %s' % (self.status_code, self.reason),
                    response=self,
                )
        return MockResponse()

    agent = MockAgent(port=12345)
    agent.setup_logging()

    agent.collect_server_metadata()

    agent.controller_url = 'http://mock/api/status/'

    with mock.patch('requests.post', mock_post):
        agent.status_to_controller()

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = (
        'POST request to controller failed due to error: '
        'HTTP Error 500: Internal Server Error'
    )

    assert msg in contents, (
        'Expected %s in logs, got:\n%s' % (msg, contents)
    )
