import json
import os
import platform
import re
import socket
import tempfile
import types

import mock
import psutil
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


def setup_interface_test(monkeypatch, net_if_addrs_mock):
    """Helper function to setup common test environment for interface tests."""
    def mock_gethostbyname(hostname):
        raise socket.gaierror('Name or service not known')

    monkeypatch.setattr(psutil, 'net_if_addrs', net_if_addrs_mock)
    monkeypatch.setattr(socket, 'gethostbyname', mock_gethostbyname)

    agent = MockAgent(port=12345, interface='nonexistent')
    agent.collect_server_metadata()

    assert agent.ip is None

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    return contents


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


def test_is_port_open_invalid_port():
    """Test that is_port_open raises ValueError for invalid port."""
    agent = MockAgent()
    agent.port = -1

    with pytest.raises(ValueError, match='Port not set'):
        agent.is_port_open()


def test_is_port_open_missing_ip():
    """Test that is_port_open returns False when IP is not set."""
    agent = MockAgent(port=12345)
    agent.ip = None

    assert not agent.is_port_open()


def test_is_port_open_missing_protocol():
    """Test that is_port_open raises ValueError when protocol is not set."""
    agent = MockAgent(port=12345)
    agent.ip = '127.0.0.1'

    with pytest.raises(ValueError, match='Protocol not set'):
        agent.is_port_open()


def test_protocol_property_default():
    """Test that protocol property returns None by default."""
    agent = MockAgent(port=12345)
    assert agent.protocol is None


def test_protocol_setter_type_error():
    """Test that protocol setter raises TypeError for non-string values."""
    agent = MockAgent(port=12345)

    with pytest.raises(TypeError, match='Protocol must be a string'):
        agent.protocol = 123

    with pytest.raises(TypeError, match='Protocol must be a string'):
        agent.protocol = None


def test_protocol_setter_value_error():
    """Test that protocol setter raises ValueError for invalid protocols."""
    agent = MockAgent(port=12345)

    with pytest.raises(ValueError, match='Unknown protocol value'):
        agent.protocol = 'invalid_protocol'

    with pytest.raises(ValueError, match='Unknown protocol value'):
        agent.protocol = 'HTTP'


def test_is_port_open_tcp_success(monkeypatch):
    """Test successful TCP port check."""
    agent = MockAgent(port=12345)
    agent.ip = '127.0.0.1'
    agent.protocol = 'tcp'

    mock_socket = mock.MagicMock()
    mock_socket.connect = mock.MagicMock()
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    assert agent.is_port_open()
    mock_socket.connect.assert_called_once_with(('127.0.0.1', 12345))
    mock_socket.close.assert_called_once()


def test_is_port_open_tcp_failure(monkeypatch):
    """Test failed TCP port check."""
    agent = MockAgent(port=12345)
    agent.ip = '127.0.0.1'
    agent.protocol = 'tcp'

    mock_socket = mock.MagicMock()
    mock_socket.connect = mock.MagicMock(
        side_effect=socket.error('Connection refused')
    )
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    assert not agent.is_port_open()
    mock_socket.connect.assert_called_once_with(('127.0.0.1', 12345))
    mock_socket.close.assert_called_once()


def test_is_port_open_udp_success(monkeypatch):
    """Test successful UDP port check."""
    agent = MockAgent(port=12345)
    agent.ip = '127.0.0.1'
    agent.protocol = 'udp'

    mock_socket = mock.MagicMock()
    mock_socket.sendto = mock.MagicMock()
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    assert agent.is_port_open()
    mock_socket.sendto.assert_called_once_with(b'', ('127.0.0.1', 12345))
    mock_socket.close.assert_called_once()


def test_is_port_open_udp_with_packet_size(monkeypatch):
    """Test UDP port check with packet size verification."""
    agent = MockAgent(port=12345)
    agent.ip = '127.0.0.1'
    agent.protocol = 'udp'

    mock_socket = mock.MagicMock()
    mock_socket.sendto = mock.MagicMock()
    mock_socket.recvfrom = mock.MagicMock(
        return_value=(b'response', ('127.0.0.1', 12345))
    )
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    assert agent.is_port_open(packet_size=8)
    mock_socket.sendto.assert_called_once_with(b'', ('127.0.0.1', 12345))
    mock_socket.recvfrom.assert_called_once_with(8)
    mock_socket.close.assert_called_once()


def test_is_port_open_udp_packet_size_mismatch(monkeypatch):
    """Test UDP port check with packet size mismatch."""
    agent = MockAgent(port=12345)
    agent.ip = '127.0.0.1'
    agent.protocol = 'udp'

    mock_socket = mock.MagicMock()
    mock_socket.sendto = mock.MagicMock()
    mock_socket.recvfrom = mock.MagicMock(
        return_value=(b'short', ('127.0.0.1', 12345))
    )
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    assert not agent.is_port_open(packet_size=8)
    mock_socket.sendto.assert_called_once_with(b'', ('127.0.0.1', 12345))
    mock_socket.recvfrom.assert_called_once_with(8)
    mock_socket.close.assert_called_once()


def test_get_ip_from_interface_not_found(monkeypatch):
    """Test that None is returned when interface is not found."""
    def mock_net_if_addrs():
        return {'mock_interface': []}

    monkeypatch.setattr(psutil, 'net_if_addrs', mock_net_if_addrs)

    from agents.agent import get_ip_from_interface
    assert get_ip_from_interface('nonexistent_interface') is None


def test_get_ip_from_interface_loopback_only(monkeypatch):
    """Test that None is returned when only loopback address is present."""
    def mock_net_if_addrs():
        return {
            'mock_interface': [
                mock.MagicMock(
                    address='127.0.0.1',
                    family=socket.AF_INET
                )
            ]
        }

    monkeypatch.setattr(psutil, 'net_if_addrs', mock_net_if_addrs)

    from agents.agent import get_ip_from_interface
    assert get_ip_from_interface('mock_interface') is None


def test_get_ip_from_interface_valid_ipv4(monkeypatch):
    """Test that valid IPv4 address is returned."""
    def mock_net_if_addrs():
        return {
            'mock_interface': [
                mock.MagicMock(
                    address='192.168.1.1',
                    family=socket.AF_INET
                )
            ]
        }

    monkeypatch.setattr(psutil, 'net_if_addrs', mock_net_if_addrs)

    from agents.agent import get_ip_from_interface
    assert get_ip_from_interface('mock_interface') == '192.168.1.1'


def test_get_ip_from_interface_multiple_addresses(monkeypatch):
    """Test that first non-loopback IPv4 address is returned."""
    def mock_net_if_addrs():
        return {
            'mock_interface': [
                mock.MagicMock(
                    address='127.0.0.1',
                    family=socket.AF_INET
                ),
                mock.MagicMock(
                    address='192.168.1.1',
                    family=socket.AF_INET
                ),
                mock.MagicMock(
                    address='fe80::1',
                    family=socket.AF_INET6
                )
            ]
        }

    monkeypatch.setattr(psutil, 'net_if_addrs', mock_net_if_addrs)

    from agents.agent import get_ip_from_interface
    assert get_ip_from_interface('mock_interface') == '192.168.1.1'


def test_collect_server_metadata_os_detection(monkeypatch):
    """Test successful OS type detection."""
    def mock_system():
        return 'Linux'

    monkeypatch.setattr(platform, 'system', mock_system)

    agent = MockAgent(port=12345)
    agent.collect_server_metadata()

    assert agent.os_type == 'linux'


def test_collect_server_metadata_unknown_os(monkeypatch):
    """Test handling of undetectable OS type."""
    def mock_system():
        return ''

    monkeypatch.setattr(platform, 'system', mock_system)

    agent = MockAgent(port=12345)
    agent.collect_server_metadata()

    assert agent.os_type == 'unknown'

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    assert 'Could not deduce OS type' in contents


def test_collect_server_metadata_interface_ip_success(monkeypatch):
    """Test successful IP address retrieval from interface."""
    def mock_net_if_addrs():
        return {
            'eth0': [
                mock.MagicMock(
                    address='192.168.1.1',
                    family=socket.AF_INET
                )
            ]
        }

    monkeypatch.setattr(psutil, 'net_if_addrs', mock_net_if_addrs)

    agent = MockAgent(port=12345, interface='eth0')
    agent.collect_server_metadata()

    assert agent.ip == '192.168.1.1'


def test_collect_server_metadata_interface_key_error(monkeypatch):
    """Test handling of KeyError when getting IP from interface."""
    def mock_net_if_addrs():
        return {}

    contents = setup_interface_test(monkeypatch, mock_net_if_addrs)
    expected_msg = (
        'Could not deduce IP address from hostname: '
        'Name or service not known'
    )
    assert expected_msg in contents


def test_collect_server_metadata_interface_attribute_error(monkeypatch):
    """Test handling of AttributeError when getting IP from interface."""
    def mock_net_if_addrs():
        return {
            'eth0': [
                mock.MagicMock(
                    address=None,
                    family=None
                )
            ]
        }

    contents = setup_interface_test(monkeypatch, mock_net_if_addrs)
    expected_msg = (
        'Could not deduce IP address from hostname: '
        'Name or service not known'
    )
    assert expected_msg in contents


def test_collect_server_metadata_hostname_error(monkeypatch):
    """Test handling of socket error when getting hostname."""
    def mock_gethostname():
        raise socket.error('Failed to get hostname')

    monkeypatch.setattr(socket, 'gethostname', mock_gethostname)

    agent = MockAgent(port=12345)
    agent.collect_server_metadata()

    assert agent.hostname == 'unknown'

    with open(agent.logfile.name, 'r') as f:
        f.seek(0)
        contents = f.read()

    assert 'Could not get hostname: Failed to get hostname' in contents


def test_default_whitelist_commands_is_empty_list():
    """Test that whitelist_commands is initialized with default commands."""
    agent1 = MockAgent()
    agent2 = MockAgent()
    assert agent1.whitelist_commands == agent2.whitelist_commands
    original_list = agent1.whitelist_commands
    agent1.whitelist_commands = ['new', 'list']
    assert agent2.whitelist_commands == original_list
    assert agent1.whitelist_commands != agent2.whitelist_commands


def test_explicit_whitelist_commands_extends_default_list():
    """Test that provided commands are added to whitelist."""
    commands = ['cmd_a', 'cmd_b']
    agent = MockAgent(whitelist_commands=commands)
    assert all(cmd in agent.whitelist_commands for cmd in commands)


def test_explicit_whitelist_commands_none_uses_default_list():
    """Test that None whitelist_commands uses default list."""
    agent = MockAgent(whitelist_commands=None)
    assert agent.whitelist_commands == MockAgent().whitelist_commands


def test_class_whitelist_commands():
    """Test that class-level whitelist_commands are properly handled."""
    MockAgent.whitelist_commands = ['class_cmd1', 'class_cmd2']

    agent = MockAgent()
    assert 'class_cmd1' in agent.whitelist_commands
    assert 'class_cmd2' in agent.whitelist_commands

    agent2 = MockAgent(whitelist_commands=['instance_cmd'])
    assert 'instance_cmd' in agent2.whitelist_commands
    assert 'class_cmd1' in agent2.whitelist_commands
    assert 'class_cmd2' in agent2.whitelist_commands

    MockAgent.whitelist_commands = None


def test_config_file_parsing():
    """Test parsing of config file options."""
    with tempfile.NamedTemporaryFile() as tmp:
        config_content = """
[server]
name = test_server
port = 12345
processes = proc1,proc2,proc3
interface = eth0

[controller]
whitelist_commands = cmd1,cmd2,cmd3
"""
        tmp.write(config_content)
        tmp.flush()

        agent = MockAgent.from_config_file(tmp.name)

        assert agent.server_name == 'test_server'
        assert agent.port == 12345
        assert agent.processes == ['proc1', 'proc2', 'proc3']
        assert agent.interface == 'eth0'
        assert all(
            cmd in agent.whitelist_commands
            for cmd in ['cmd1', 'cmd2', 'cmd3']
        )


def test_config_file_missing_options():
    """Test handling of missing config file options."""
    with tempfile.NamedTemporaryFile() as tmp:
        config_content = """
[server]
name = test_server
port = 12345
"""
        tmp.write(config_content)
        tmp.flush()

        agent = MockAgent.from_config_file(tmp.name)

        assert agent.server_name == 'test_server'
        assert agent.port == 12345
        assert agent.processes == []
        assert agent.interface is None
        assert agent.whitelist_commands == []


def test_config_file_empty_processes():
    """Test handling of empty processes list in config."""
    with tempfile.NamedTemporaryFile() as tmp:
        config_content = """
[server]
name = test_server
port = 12345
processes =
"""
        tmp.write(config_content)
        tmp.flush()

        agent = MockAgent.from_config_file(tmp.name)
        assert agent.processes == []


def test_config_file_empty_whitelist_commands():
    """Test handling of empty whitelist_commands in config."""
    with tempfile.NamedTemporaryFile() as tmp:
        config_content = """
[server]
name = test_server
port = 12345

[controller]
whitelist_commands =
"""
        tmp.write(config_content)
        tmp.flush()

        agent = MockAgent.from_config_file(tmp.name)
        assert agent.whitelist_commands == []


def test_config_file_whitelist_commands_extends_default():
    """Test that config whitelist_commands extends default list."""
    MockAgent.whitelist_commands = ['default_cmd1', 'default_cmd2']

    with tempfile.NamedTemporaryFile() as tmp:
        config_content = """
[server]
name = test_server
port = 12345

[controller]
whitelist_commands = config_cmd1,config_cmd2
"""
        tmp.write(config_content)
        tmp.flush()

        agent = MockAgent.from_config_file(tmp.name)
        assert 'default_cmd1' in agent.whitelist_commands
        assert 'default_cmd2' in agent.whitelist_commands
        assert 'config_cmd1' in agent.whitelist_commands
        assert 'config_cmd2' in agent.whitelist_commands

    MockAgent.whitelist_commands = None


def test_fetch_command_from_controller_headers_default():
    """Test that default headers are set correctly."""
    agent = MockAgent(port=12345)
    agent.hostname = 'mock_server'
    agent.controller_url = 'http://mock/'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        captured_request['headers'] = request.headers
        return mock.MagicMock(
            getcode=lambda: 200,
            read=lambda: '{}',
            close=lambda: None
        )

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.fetch_command_from_controller()

    assert captured_request['headers'] == {'Accept': 'application/json'}


def test_fetch_command_from_controller_headers_with_api_key():
    """Test that headers include Authorization when api_key is provided."""
    agent = MockAgent(port=12345)
    agent.hostname = 'mock_server'
    agent.controller_url = 'http://mock/'
    agent.auth_token_type = 'Bearer'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        captured_request['headers'] = request.headers
        return mock.MagicMock(
            getcode=lambda: 200,
            read=lambda: '{}',
            close=lambda: None
        )

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.fetch_command_from_controller(api_key='test-token')

    expected_headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer test-token'
    }
    assert captured_request['headers'] == expected_headers


def test_fetch_command_from_controller_headers_with_kwargs():
    """Test that additional headers from kwargs are added correctly."""
    agent = MockAgent(port=12345)
    agent.hostname = 'mock_server'
    agent.controller_url = 'http://mock/'
    agent.auth_token_type = 'Bearer'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        captured_request['headers'] = request.headers
        return mock.MagicMock(
            getcode=lambda: 200,
            read=lambda: '{}',
            close=lambda: None
        )

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.fetch_command_from_controller(
            api_key='test-token',
            CustomHeader='custom-value',
            XRequestID='12345'
        )

    expected_headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer test-token',
        'Customheader': 'custom-value',
        'Xrequestid': '12345'
    }
    assert captured_request['headers'] == expected_headers


def test_fetch_command_from_controller_headers_kwargs_override():
    """Test that kwargs headers override default headers."""
    agent = MockAgent(port=12345)
    agent.hostname = 'mock_server'
    agent.controller_url = 'http://mock/'
    agent.auth_token_type = 'Bearer'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        captured_request['headers'] = request.headers
        return mock.MagicMock(
            getcode=lambda: 200,
            read=lambda: '{}',
            close=lambda: None
        )

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.fetch_command_from_controller(
            api_key='test-token',
            Accept='text/plain'
        )

    expected_headers = {
        'Accept': 'text/plain',
        'Authorization': 'Bearer test-token'
    }
    assert captured_request['headers'] == expected_headers


def test_fetch_command_from_controller_headers_update():
    """Test that headers.update correctly adds Authorization header."""
    agent = MockAgent(port=12345)
    agent.hostname = 'mock_server'
    agent.controller_url = 'http://mock/'
    agent.auth_token_type = 'Bearer'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        captured_request['headers'] = request.headers
        return mock.MagicMock(
            getcode=lambda: 200,
            read=lambda: '{}',
            close=lambda: None
        )

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.fetch_command_from_controller(api_key='test-token')

    expected_headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer test-token'
    }
    assert captured_request['headers'] == expected_headers


def test_post_data_headers_update():
    """Test that post_data correctly adds Authorization header."""
    agent = MockAgent(port=12345)
    agent.auth_token_type = 'Bearer'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        captured_request['headers'] = request.headers
        return mock.MagicMock(
            getcode=lambda: 200,
            read=lambda: '{}',
            close=lambda: None
        )

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.post_data(
            url='http://mock/api',
            data={'test': 'data'},
            api_key='test-token'
        )

    expected_headers = {
        'Content-type': 'application/json',
        'Authorization': 'Bearer test-token'
    }
    assert captured_request['headers'] == expected_headers


def test_status_to_dict_format():
    agent = MockAgent(port=12345)
    agent.collect_server_metadata()
    result = agent.status_to_dict()

    required_keys = set([
        'os', 'hostname', 'ip', 'server_name', 'uptime', 'timestamp',
        'healthy'
    ])
    assert set(result.keys()) == required_keys

    assert isinstance(result['os'], str)
    assert isinstance(result['hostname'], str)
    assert isinstance(result['ip'], (str, type(None)))
    assert result['server_name'] == 'mock'
    assert isinstance(result['uptime'], (int, float))
    assert isinstance(result['timestamp'], str)
    assert isinstance(result['healthy'], bool)


def test_status_to_dict_timestamp_format():
    agent = MockAgent(port=12345)
    agent.collect_server_metadata()
    result = agent.status_to_dict()
    timestamp = result['timestamp']

    assert re.match(
        r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', timestamp
    ) is not None


@mock.patch('agents.agent.ServerAgent.service_healthy')
def test_status_to_dict_healthy_status(mock_healthy):
    agent = MockAgent(port=12345)

    mock_healthy.return_value = True
    result = agent.status_to_dict()
    assert result['healthy'] is True

    mock_healthy.return_value = False
    result = agent.status_to_dict()
    assert result['healthy'] is False


def test_status_to_txt():
    agent = MockAgent(port=12345)
    agent.collect_server_metadata()

    with open(agent.logfile.name, 'w') as f:
        f.truncate(0)

    agent.status_to_txt()

    with open(agent.logfile.name, 'r') as f:
        contents = f.read()

    dict_data = agent.status_to_dict()
    for key, value in dict_data.items():
        expected_message = '%s: %s' % (key, value)
        assert expected_message in contents
