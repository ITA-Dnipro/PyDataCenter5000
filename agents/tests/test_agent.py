import json
import os
import socket
import tempfile
import types

import mock
import pytest
import urllib2

from agents.agent import CommandHistory, ServerAgent

HTTP_ERROR_OUTPUT = (
    urllib2.HTTPError(
        url='http://mock/api/dest/',
        code=500,
        msg='Internal Server Error',
        hdrs=None,
        fp=None,
    ),
    'HTTP Error 500: Internal Server Error',
)
URL_ERROR_OUTPUT = (
    urllib2.URLError('Connection refused'),
    '<urlopen error Connection refused>',
)
TIMEOUT_ERROR_OUTPUT = (
    socket.timeout('HTTP request timed out'), 'HTTP request timed out'
)
UNEXPECTED_ERROR_OUTPUT = (
    Exception('Unexpected error occurred'), 'Unexpected error occurred'
)


class MockAgent(ServerAgent):

    def __init__(
        self,
        server_name='mock',
        port=None,
        processes=None,
        interface=None,
        protocol=None,
        whitelist_commands=None,
        log_path=None,
    ):
        self.logfile = tempfile.NamedTemporaryFile(delete=False)
        self.logfile.close()

        super(MockAgent, self).__init__(
            server_name,
            port,
            processes,
            interface,
            protocol,
            whitelist_commands,
            log_path or self.logfile.name,
        )

    def __del__(self):
        if hasattr(self, 'logfile'):
            os.remove(self.logfile.name)

    def service_healthy(self):
        return super(MockAgent, self).service_healthy()


def test_command_history_valid_data():
    """Test that command history is properly instantiated."""
    data = {
        'command': 'ls',
        'hostname': 'test-server',
        'status': 'pending',
        'timestamp': '2025-06-03T18:25:35.418746Z',
        'result': 'ok',
        'id': 1,
    }

    command_history = CommandHistory.from_dict(data)

    assert command_history.command == 'ls'
    assert command_history.hostname == 'test-server'
    assert command_history.status == 'pending'
    assert command_history.timestamp == '2025-06-03T18:25:35.418746Z'
    assert command_history.result == 'ok'
    assert command_history.id == 1


def test_command_history_missing_data():
    """
    Test that error is raised on command history input with missing
    fields.
    """
    parameters = [
        {
            'hostname': 'test-server',
            'status': 'pending',
            'timestamp': '2025-06-03T18:25:35.418746Z',
        },
        {
            'command': 'ls',
            'status': 'pending',
            'timestamp': '2025-06-03T18:25:35.418746Z',
        },
    ]

    for data in parameters:
        with pytest.raises(TypeError):
            CommandHistory.from_dict(data)


def test_command_history_bad_input_error():
    """Test that error is raised on bad command history input."""
    parameters = [
        {
            'command': None,
            'hostname': 'test-server',
            'status': 'pending',
            'timestamp': '2025-06-03T18:25:35.418746Z',
        },
        {
            'command': 'ls',
            'hostname': 'test-server',
            'status': None,
            'timestamp': '2025-06-03T18:25:35.418746Z',
        },
        {
            'command': 'ls',
            'hostname': 'test-server',
            'status': 'pending',
            'timestamp': 'bad date',
        },
    ]

    for data in parameters:
        with pytest.raises((TypeError, ValueError)):
            CommandHistory.from_dict(data)


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
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


def test_post_data_success(monkeypatch):
    agent = MockAgent(port=12345)

    class MockResponse:
        def getcode(self):
            return 200

        def read(self):
            return b'{"message":"received"}'

        def close(self):
            pass

    monkeypatch.setattr(
        urllib2, 'urlopen', lambda req, timeout=None: MockResponse()
    )

    agent.post_data('http://mock/api', {'test': 'data'})

    with open(agent.logfile.name) as f:
        f.seek(0)
        contents = f.read()

    assert 'POST request status: 200' in contents
    assert (
        'POST request succeeded on attempt 1: %s' % b'{"message":"received"}'
    ) in contents


def test_post_data_retry(monkeypatch):
    agent = MockAgent(port=12345)

    call_count = {'count': 0}

    def mock_urlopen(req, timeout=None):
        call_count['count'] += 1
        if call_count['count'] < 2:
            raise urllib2.URLError('Temporary failure')

        class MockResponse(object):

            def getcode(self):
                return 200

            def read(self):
                return b'{"message":"received"}'

            def close(self):
                pass

        return MockResponse()

    monkeypatch.setattr(urllib2, 'urlopen', mock_urlopen)

    agent.post_data(
        'http://mock/endpoint', {'retry': 'test'}, max_retries=3, delay=0
    )

    with open(agent.logfile.name) as f:
        f.seek(0)
        contents = f.read()

    msg = (
        'POST request succeeded on attempt 2: %s'
        % b'{"message":"received"}'
    )

    assert call_count['count'] == 2
    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
                msg, contents
            )
    )


def test_post_data_max_retries_fail(monkeypatch):
    agent = MockAgent(port=12345)

    monkeypatch.setattr(
        urllib2,
        'urlopen',
        lambda req, timeout=None: (
            _ for _ in ()
        ).throw(urllib2.URLError('Permanent error'))
    )

    with pytest.raises(RuntimeError, match='POST failed after 3 attempts'):
        agent.post_data(
            'http://mock/api',
            {'fail': True},
            max_retries=3,
            delay=0,
            fail_silently=False,
        )

    with open(agent.logfile.name) as f:
        f.seek(0)
        contents = f.read()

    assert 'All 3 attempts failed. Data not sent.' in contents
    assert 'Permanent error' in contents


def test_post_data_error():
    agent = MockAgent(port=12345)

    errors = [HTTP_ERROR_OUTPUT, URL_ERROR_OUTPUT, TIMEOUT_ERROR_OUTPUT]

    for error, msg in errors:
        with mock.patch('urllib2.urlopen', side_effect=error):
            agent.post_data(
                'http://mock/api',
                {'fail': True},
                max_retries=1,
                fail_silently=True,
            )

        with open(agent.logfile.name) as f:
            f.seek(0)
            contents = f.read()

        assert msg in contents


def test_post_data_to_controller_success(monkeypatch):
    """
    Test that successful POST request to controller is properly handled
    and logged.
    """

    def mock_urlopen(request, timeout=5):

        class MockResponse(object):

            def getcode(self):
                return 201

            def read(self):
                return b'{"message":"received"}'

            def close(self):
                pass

        return MockResponse()

    monkeypatch.setattr(urllib2, 'urlopen', mock_urlopen)

    agent = MockAgent(port=12345)
    agent.controller_url = 'http://mock/controller/'

    agent.post_data(
        'server/status/', {'to_controller': 'test'}, to_controller=True
    )

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = (
        'POST request succeeded on attempt 1: %s' % b'{"message":"received"}'
    )

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
                msg, contents
            )
    )


def test_post_data_to_controller_missing_url():
    """Test that missing controller URL is properly handled and logged."""
    agent = MockAgent(port=12345)

    # Set controller's URL explicitly to be independent of changes
    # of default values in agent.py/
    agent.controller_url = None

    agent.post_data(
        url='', payload={'to_controller': 'test'}, to_controller=True
    )

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = (
        "Couldn't send POST request to controller: controller URL is not set"
    )

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


def test_fetch_command_from_controller_success(monkeypatch):
    """
    Test that succesful GET request to controller is properly handled
    and logged.
    """
    commands = [
        {
            'hostname': 'mock_server',
            'command': 'uptime',
            'result': None,
            'status': 'pending',
            'timestamp': None,
        },
        None,
    ]
    codes = [200, 204]

    for command, code in zip(commands, codes):
        class MockResponse(object):
            def getcode(self):
                return code

            def read(self):
                return json.dumps(command)

            def close(self):
                pass

        monkeypatch.setattr(
            urllib2, 'urlopen', lambda req, timeout: MockResponse()
        )

        agent = MockAgent(port=12345)

        agent.hostname = 'mock_server'
        agent.controller_url = 'http://mock/'

        result = agent.fetch_command_from_controller()

        assert result == command, 'Expected command dict, got %r' % result

        with open(agent.logfile.name, 'r') as f:
            f.seek(0)
            contents = f.read()

        msg = 'GET request to controller succeded with status: %s' % code

        assert msg in contents, (
            'Expected log message %s not found. Log contents:\n %s' % (
                msg, contents
            )
        )


def test_fetch_command_from_controller_emty_response(monkeypatch):
    class MockResponse(object):
        def getcode(self):
            return 200

        def read(self):
            return ' '

        def close(self):
            pass

    monkeypatch.setattr(
        urllib2, 'urlopen', lambda req, timeout: MockResponse()
    )

    agent = MockAgent(port=12345)

    agent.hostname = 'mock_server'
    agent.controller_url = 'http://mock/'

    agent.fetch_command_from_controller()

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'No pending commands for server %s' % agent.hostname

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


def test_fetch_command_from_controller_missing_data():
    """
    Test proper handling and logging of missing data
    (hostname or controller URL) in fetch_command_from_controller.
    """
    parameters = [(None, 'mock_server'), ('http://mock/', None)]

    for controller_url, hostname in parameters:
        agent = MockAgent(port=12345)

        agent.hostname = hostname
        agent.controller_url = controller_url

        agent.fetch_command_from_controller()

        with open(agent.logfile.name, 'r') as f:
            f.seek(0)
            contents = f.read()

        msg = (
            "Couldn't fetch controller command: controller URL or "
            'hostname not set'
        )

        assert msg in contents, (
            'Expected log message %s not found. Log contents:\n %s' % (
                msg, contents
            )
        )


def test_fetch_command_from_controller_error(monkeypatch):
    """
    Test proper handling and logging of errors in
    fetch_command_from_controller.
    """
    for error, msg in [
        HTTP_ERROR_OUTPUT,
        URL_ERROR_OUTPUT,
        TIMEOUT_ERROR_OUTPUT,
        UNEXPECTED_ERROR_OUTPUT,
    ]:
        def mock_urlopen(request, timeout=5):
            raise error

        monkeypatch.setattr(urllib2, 'urlopen', mock_urlopen)

        agent = MockAgent(port=12345)

        agent.collect_server_metadata()

        agent.hostname = 'mock_server'
        agent.controller_url = (
            'http://mock/api/command/?hostname=%s' % agent.hostname
        )

        agent.fetch_command_from_controller()

        with open(agent.logfile.name, 'r') as f:
            f.seek(0)
            contents = f.read()

        assert msg in contents, (
            'Expected log message %s not found. Log contents:\n %s' % (
                msg, contents
            )
        )


@pytest.mark.coro
def test_maybe_add_to_queue_adds_item():
    """Test that good command history input is added to queue."""
    data = {
        'command': 'ls',
        'hostname': 'test-server',
        'status': 'pending',
        'timestamp': '2025-06-03T18:25:35.418746Z',
    }

    agent = MockAgent(port=12345)

    agent.maybe_add_command_to_queue(data)

    assert agent.queue.qsize() == 1


@pytest.mark.coro
def test_maybe_add_to_queue_logs_bad_input():
    """
    Test that bad command history input is logged by server agent and
    not added to queue.
    """
    data = {
        'command': None,
        'hostname': 'test-server',
        'status': 'pending',
        'timestamp': '2025-06-03T18:25:35.418746Z',
    }

    agent = MockAgent(port=12345)

    agent.maybe_add_command_to_queue(data)

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Command validation failed due to error'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )

    assert agent.queue.qsize() == 0


def test_status_to_dict_keys():
    """
    Verify that status_to_dict() returns all expected keys
    in the status dictionary.
    """
    agent = MockAgent(port=12345)

    # Set attributes manually
    agent.os_type = 'linux'
    agent.hostname = 'test-host'
    agent.ip = '127.0.0.1'
    agent.server_name = 'dns'
    agent.uptime = 12345
    agent.timestamp = '2025-06-03 20:00:00'
    agent.healthy = True

    result = agent.status_to_dict()

    required_keys = set([
        'os',
        'hostname',
        'ip',
        'server_name',
        'uptime',
        'timestamp',
        'healthy',
    ])

    msg_keys = 'Expected status_to_dict() keys to match: %s' % required_keys
    assert set(result.keys()) == required_keys, msg_keys


def test_status_to_dict_with_missing_fields():
    """
    Ensure status_to_dict() handles missing or None fields gracefully.
    """
    agent = MockAgent(port=12345)

    agent.os_type = None
    agent.hostname = None
    agent.ip = None
    agent.server_name = 'dns'
    agent.uptime = -1
    agent.timestamp = None
    agent.healthy = False

    result = agent.status_to_dict()

    assert result['os'] is None, "Expected 'os' to be None when missing"
    assert result['hostname'] is None, "Expected 'hostname' to be None"
    assert result['ip'] is None, "Expected 'ip' to be None when missing"
    assert result['uptime'] == -1, "Expected 'uptime' to be -1 when missing"
