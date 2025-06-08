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
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )


def test_status_to_controller_error(monkeypatch):
    """
    Test that the HTTP, URL and timeout failures at POST request to
    controller are properly handled and logged.
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

        agent.controller_url = 'http://mock/api/status/'

        agent.status_to_controller(max_retries=1)

        with open(agent.logfile.name, 'r') as f:
            f.seek(0)
            contents = f.read()

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


def test_maybe_add_to_queue_adds_item():
    """Test that good command history input is added to queue."""
    data = {
        'command': 'ls',
        'hostname': 'test-server',
        'status': 'pending',
        'timestamp': '2025-06-03T18:25:35.418746Z',
    }

    agent = MockAgent(port=12345)

    agent.maybe_add_to_queue(data)

    with agent.queue.mutex:
        assert CommandHistory.from_dict(data) in agent.queue.queue


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

    agent.maybe_add_to_queue(data)

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    msg = 'Command validation failed due to error'

    assert msg in contents, (
        'Expected log message %s not found. Log contents:\n %s' % (
            msg, contents
        )
    )

    with agent.queue.mutex:
        assert len(agent.queue.queue) == 0


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


def test_get_cpu_usage():
    """
    Test that get_cpu_usage returns the mocked CPU usage percentage.
    """
    agent = MockAgent()
    with mock.patch('psutil.cpu_percent', return_value=55.5):
        assert agent.get_cpu_usage() == 55.5


def test_get_ram_usage():
    """
    Test that get_ram_usage returns the mocked RAM usage percentage.
    """
    agent = MockAgent()
    mock_mem = mock.Mock()
    mock_mem.percent = 66.6
    with mock.patch('psutil.virtual_memory', return_value=mock_mem):
        assert agent.get_ram_usage() == 66.6


def test_get_disk_usage():
    """
    Test that get_disk_usage returns the mocked disk usage percentage.
    """
    agent = MockAgent()
    mock_disk = mock.Mock()
    mock_disk.percent = 77.7
    with mock.patch('psutil.disk_usage', return_value=mock_disk):
        assert agent.get_disk_usage() == 77.7


def test_get_load_average():
    """
    Test that get_load_average returns the mocked 1-minute load average.
    """
    agent = MockAgent()
    with mock.patch('os.getloadavg', return_value=(2.22, 1.0, 0.5)):
        assert agent.get_load_average() == 2.22


def test_get_load_average_unsupported():
    """
    Test that get_load_average returns -1.0 when os.getloadavg
    raises an exception.
    """
    agent = MockAgent()
    with mock.patch('os.getloadavg', side_effect=OSError()):
        assert agent.get_load_average() == -1.0


def test_generate_report():
    """
    Test that generate_report returns
    correct mocked metrics data and hostname.
    """
    agent = MockAgent()
    cpu_patch = mock.patch.object(agent, 'get_cpu_usage', return_value=10.1)
    ram_patch = mock.patch.object(agent, 'get_ram_usage', return_value=20.2)
    disk_patch = mock.patch.object(agent, 'get_disk_usage', return_value=30.3)
    load_patch = mock.patch.object(
        agent,
        'get_load_average',
        return_value=40.4
    )

    cpu_patch.start()
    ram_patch.start()
    disk_patch.start()
    load_patch.start()

    try:
        report = agent.generate_report()
        print(report)
        assert report['cpu_usage_percent'] == 10.1
        assert report['ram_usage_percent'] == 20.2
        assert report['disk_usage_percent'] == 30.3
        assert report['load_avg_1min'] == 40.4
        assert report['hostname'] == agent.hostname
    finally:
        cpu_patch.stop()
        ram_patch.stop()
        disk_patch.stop()
        load_patch.stop()
