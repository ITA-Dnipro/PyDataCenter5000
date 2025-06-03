import os
import socket
import tempfile
import types

import mock
import pytest
import urllib2

from agents.agent import ServerAgent


class MockAgent(ServerAgent):

    def __init__(
        self,
        server_name='mock',
        port=None,
        processes=None,
        interface=None,
        whitelist_commands=None,
    ):
        super(MockAgent, self).__init__(
            server_name, port, processes, interface, whitelist_commands
        )

    def setup_logging(self, path=None):
        if not path:
            self.logfile = tempfile.NamedTemporaryFile(delete=False)
            self.logfile.close()

            path = self.logfile.name

        return super(MockAgent, self).setup_logging(path)

    def __del__(self):
        if hasattr(self, 'logfile'):
            os.remove(self.logfile.name)


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

    assert msg in contents, ('Expected %s in logs, got:\n%s' % (msg, contents))


def test_status_to_controller_success(monkeypatch):
    """
    Test that successful POST request to controller is properly handled
    and logged.
    """

    def mock_urlopen(request, timeout=5):

        class MockResponse(object):

            def getcode(self):
                return 201

            def read(self):
                return b'{"message":"status received"}'

            def close(self):
                pass

        return MockResponse()

    monkeypatch.setattr(urllib2, 'urlopen', mock_urlopen)

    agent = MockAgent(port=12345)
    agent.setup_logging()

    agent.collect_server_metadata()

    agent.controller_url = 'http://mock/api/status/'

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

    assert msg in contents, 'Expected %s in logs, got:\n%s' % (msg, contents)


def test_status_to_controller_error(monkeypatch):
    """
    Test that the HTTP, URL and timeout failures at POST request to
    controller are properly handled and logged.
    """
    output = [
        (
            urllib2.HTTPError(
                url='http://mock/api/status/',
                code=500,
                msg='Internal Server Error',
                hdrs=None,
                fp=None,
            ),
            'HTTP Error 500: Internal Server Error',
        ),
        (
            urllib2.URLError('Connection refused'),
            '<urlopen error Connection refused>',
        ),
        (
            socket.timeout('HTTP request timed out'), 'HTTP request timed out'
        ),
    ]

    for error, msg in output:
        def mock_urlopen(request, timeout=5):
            raise error

        monkeypatch.setattr(urllib2, 'urlopen', mock_urlopen)

        agent = MockAgent(port=12345)
        agent.setup_logging()

        agent.collect_server_metadata()

        agent.controller_url = 'http://mock/api/status/'

        agent.status_to_controller(max_retries=1)

        with open(agent.logfile.name, 'r') as f:
            f.seek(0)
            contents = f.read()

        assert msg in contents, (
            'Expected %s in logs, got:\n%s' % (
                'Attempt 1 failed: %s' % msg, contents
            )
        )


def test_post_data_success(monkeypatch):
    agent = MockAgent(port=12345)
    agent.setup_logging()

    class MockResponse:
        def getcode(self):
            return 200

        def read(self):
            return b'Success'

        def close(self):
            pass

    monkeypatch.setattr(
        urllib2, 'urlopen', lambda req, timeout=None: MockResponse()
    )

    result = agent.post_data('http://mock/api', {'test': 'data'})

    with open(agent.logfile.name) as f:
        f.seek(0)
        contents = f.read()

    assert result == b'Success'
    assert 'POST request status: 200' in contents
    assert 'Success on attempt 1' in contents


def test_post_data_retry(monkeypatch):
    agent = MockAgent(port=12345)
    agent.setup_logging()

    call_count = {'count': 0}

    def mock_urlopen(req, timeout=None):
        call_count['count'] += 1
        if call_count['count'] < 2:
            raise urllib2.URLError('Temporary failure')

        class MockResponse(object):

            def getcode(self):
                return 200

            def read(self):
                return b'Retry Success'

            def close(self):
                pass

        return MockResponse()

    monkeypatch.setattr(urllib2, 'urlopen', mock_urlopen)

    result = agent.post_data(
        'http://mock/api', {'retry': 'test'}, max_retries=3, delay=0
    )

    with open(agent.logfile.name) as f:
        contents = f.read()

    assert call_count['count'] == 2
    assert result == b'Retry Success'
    assert 'Retrying in 0 seconds...' in contents
    assert 'Success on attempt 2' in contents


def test_post_data_max_retries_fail(monkeypatch):
    agent = MockAgent(port=12345)
    agent.setup_logging()

    monkeypatch.setattr(
        urllib2,
        'urlopen',
        lambda req, timeout=None: (
            _ for _ in ()
        ).throw(urllib2.URLError('Permanent error'))
    )

    with pytest.raises(RuntimeError, match='POST failed after 3 attempts'):
        agent.post_data(
            'http://mock/api', {'fail': True}, max_retries=3, delay=0
        )

    with open(agent.logfile.name) as f:
        f.seek(0)
        contents = f.read()

    assert 'All 3 attempts failed. Data not sent.' in contents
    assert 'Permanent error' in contents


def test_fetch_command_from_controller_success(monkeypatch):
    """
    Test that succesful GET request to controller is properly handled
    and logged.
    """
    class MockResponse(object):
        def read(self):
            return b'''{
                "hostname": "mock_server",
                "command": "uptime",
                "result": null,
                "status": "pending",
                "timestamp": null
            }'''

        def close(self):
            pass

    monkeypatch.setattr(
        urllib2, 'urlopen', lambda req, timeout: MockResponse()
    )

    agent = MockAgent(port=12345)
    agent.setup_logging()

    agent.hostname = 'mock_server'
    agent.controller_url = 'http://mock/'

    result = agent.fetch_command_from_controller()

    assert result == {
        'hostname': agent.hostname,
        'command': 'uptime',
        'result': None,
        'status': 'pending',
        'timestamp': None,
    }, 'Expected command dict, got %r' % result

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'GET request to controller succeded.'

    assert msg in contents, 'Expected %s in logs, got:\n%s' % (msg, contents)
