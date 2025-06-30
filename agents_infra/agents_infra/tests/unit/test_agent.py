import json
import logging
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

from ...agents.base import CommandHistory, ServerAgent

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


def load_agent_from_config(config_content):
    """Helper to create a MockAgent from a string config."""
    with tempfile.NamedTemporaryFile(mode='w+', delete=True) as tmp:
        tmp.write(config_content)
        tmp.flush()
        return MockAgent.from_config_file(tmp.name)


class MockAgent(ServerAgent):

    def __init__(
        self,
        server_name='mock',
        port=None,
        processes=None,
        critical_processes=None,
        interface=None,
        protocol=None,
        whitelist_commands=None,
        command_queue_size=0,
    ):
        super(MockAgent, self).__init__(
            server_name,
            port,
            processes,
            critical_processes,
            interface,
            protocol,
            whitelist_commands,
            command_queue_size=command_queue_size,
        )

    def setup_logging(self, log_path=None):
        """Patch logging setup to do nothing to allow temp file logging."""
        pass

    @property
    def logger(self):
        """Override logger to use temp file logger."""
        return logging.getLogger('mock-logger')

    def __del__(self):
        if hasattr(self, 'logfile'):
            os.remove(self.logfile.name)

    def is_service_healthy(self):
        return super(MockAgent, self).is_service_healthy()

    def maybe_restart_service(self):
        return super(MockAgent, self).maybe_restart_service()


def mock_popen_with_output(stdout, stderr=''):
    process_mock = mock.Mock()
    process_mock.communicate.return_value = (stdout, stderr)
    return process_mock


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


def test_critical_processes_parsing():
    """Test that critical_processes are correctly parsed from config."""
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write(
            '[server]\n'
            'name=mock\n'
            'port=123\n'
            'processes=proc1\n'
            'critical_processes=sshd, nginx, postgres\n'
        )
        tmp.flush()

        agent = MockAgent.from_config_file(tmp.name)
        assert agent.critical_processes == ['sshd', 'nginx', 'postgres']


def test_status_to_json_type_error(
    setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

    assert_msg_in_logfile(
        'JSON serialization of status failed due to error: '
        "Can't serialize me"
    )


def test_post_data_success_logged(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

    assert_msg_in_logfile('POST request status: 200')
    assert_msg_in_logfile(
        'POST request succeeded on attempt 1: %s' % b'{"message":"received"}'
    )


def test_post_data_retry(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

    assert_msg_in_logfile(
        'POST request succeeded on attempt 2: %s' % b'{"message":"received"}'
    )

    assert call_count['count'] == 2


def test_post_data_max_retries_fail(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

    assert_msg_in_logfile('All 3 attempts failed. Data not sent.')
    assert_msg_in_logfile('Permanent error')


def test_post_data_error_logged(
    setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

        assert_msg_in_logfile(msg)


def test_post_data_to_controller_success_logged(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

    assert_msg_in_logfile(
        'POST request succeeded on attempt 1: %s' % b'{"message":"received"}'
    )


def test_post_data_to_controller_missing_url(
    setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    """Test that missing controller URL is properly handled and logged."""
    agent = MockAgent(port=12345)

    # Set controller's URL explicitly to be independent of changes
    # of default values in agent.py/
    agent.controller_url = None

    agent.post_data(
        url='', payload={'to_controller': 'test'}, to_controller=True
    )

    assert_msg_in_logfile(
        "Couldn't send POST request to controller: controller URL is not set"
    )


def test_fetch_command_from_controller_success(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

        assert_msg_in_logfile(
            'GET request to controller succeded with status: %s' % code
        )


def test_fetch_command_from_controller_emty_response(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

    assert_msg_in_logfile(
        'No pending commands for server %s' % agent.hostname
    )


def test_fetch_command_from_controller_missing_data(
    setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

        assert_msg_in_logfile(
            "Couldn't fetch controller command: controller URL or "
            'hostname not set'
        )


def test_fetch_command_from_controller_error(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

        assert_msg_in_logfile(msg)


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


def test_maybe_add_to_queue_full_logged(
    setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    """
    Test that trying to add command to the full queue is properly handled
    and logged.
    """
    import datetime

    agent = MockAgent(whitelist_commands=['cmd'], command_queue_size=1)

    cmd = CommandHistory(
        command='cmd',
        hostname='mock-server',
        status='pending',
        timestamp=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    )

    agent.maybe_add_command_to_queue(cmd)
    agent.maybe_add_command_to_queue(cmd)

    assert agent.queue.qsize() == 1

    assert_msg_in_logfile('Queue is full - could not append command')


def test_get_command_from_queue_has_item():
    agent = MockAgent()

    agent.queue.put('cmd')
    assert agent.get_command_from_queue(block=True) == 'cmd'


def test_get_command_from_queue_no_item_logged(
    setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    import threading

    agent = MockAgent()

    with threading.Lock():
        agent.get_command_from_queue()

    assert_msg_in_logfile('Queue is empty - could not retrieve command')


def test_maybe_add_to_queue_logs_bad_input(
    setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
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

    assert_msg_in_logfile('Command validation failed due to error')

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


def test_get_cpu_usage():
    """
    Test that get_cpu_usage returns the mocked CPU usage percentage.
    """
    agent = MockAgent()
    with mock.patch('psutil.cpu_percent', return_value=55.5):
        assert agent.get_cpu_usage() == 55.5


def test_get_cpu_usage_exception():
    """
    Test that get_cpu_usage handles the mock Exception.
    """
    agent = MockAgent()
    for exc in [
        psutil.Error('CPU psutil error'),
        ValueError('CPU value error')
    ]:
        with mock.patch('psutil.cpu_percent', side_effect=exc):
            result = agent.get_cpu_usage()
            assert result == -1.0


def test_get_ram_usage():
    """
    Test that get_ram_usage returns the mocked RAM usage percentage.
    """
    agent = MockAgent()
    mock_mem = mock.Mock()
    mock_mem.percent = 66.6
    with mock.patch('psutil.virtual_memory', return_value=mock_mem):
        assert agent.get_ram_usage() == 66.6


def test_get_ram_usage_exception():
    """
    Test that get_ram_usage handles the ram Exception.
    """
    agent = MockAgent()
    with mock.patch(
        'psutil.virtual_memory',
        side_effect=psutil.Error('RAM error')
    ):
        result = agent.get_ram_usage()
        assert result == -1.0


def test_get_disk_usage():
    """
    Test that get_disk_usage returns the mocked disk usage percentage.
    """
    agent = MockAgent()
    mock_disk = mock.Mock()
    mock_disk.percent = 77.7
    with mock.patch('psutil.disk_usage', return_value=mock_disk):
        assert agent.get_disk_usage() == 77.7


def test_get_disk_usage_exception():
    """
    Test that get_disk_usage returns the mocked disk usage percentage.
    """
    agent = MockAgent()
    exc = psutil.Error('Disk psutil error')
    with mock.patch('psutil.disk_usage', side_effect=exc):
        result = agent.get_disk_usage()
        assert result == -1.0


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
    for exc in [OSError('no loadavg'), AttributeError('not available')]:
        with mock.patch('os.getloadavg', side_effect=exc):
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
        assert report['cpu'] == 10.1
        assert report['ram'] == 20.2
        assert report['disk'] == 30.3
        assert report['load_avg'] == 40.4
    finally:
        cpu_patch.stop()
        ram_patch.stop()
        disk_patch.stop()
        load_patch.stop()


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

    from agents_infra.agents.base import get_ip_from_interface
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

    from agents_infra.agents.base import get_ip_from_interface
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

    from agents_infra.agents.base import get_ip_from_interface
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

    from agents_infra.agents.base import get_ip_from_interface
    assert get_ip_from_interface('mock_interface') == '192.168.1.1'


def test_collect_server_metadata_os_detection(monkeypatch):
    """Test successful OS type detection."""
    def mock_system():
        return 'Linux'

    def mock_get_linux_uptime():
        return 12345.0

    monkeypatch.setattr(platform, 'system', mock_system)

    from ...agents import base as agent
    monkeypatch.setattr(agent,
                        'get_linux_uptime',
                        mock_get_linux_uptime)

    agent = MockAgent(port=12345)

    agent.collect_server_metadata()

    assert agent.os_type == 'linux'
    assert agent.uptime == 12345.0


def test_collect_server_metadata_unknown_os_logged(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    """Test handling of undetectable OS type."""
    def mock_system():
        return ''

    monkeypatch.setattr(platform, 'system', mock_system)

    agent = MockAgent(port=12345)

    agent.collect_server_metadata()

    assert agent.os_type == 'unknown'

    assert_msg_in_logfile('Could not deduce OS type')


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


def test_collect_server_metadata_interface_errors(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    """
    Test handling of KeyError and AttributeError when getting IP from
    interface.
    """
    def mock_gethostbyname(hostname):
        raise socket.gaierror('Name or service not known')

    monkeypatch.setattr(socket, 'gethostbyname', mock_gethostbyname)

    for mock_net_if_addrs in [
        lambda: {},
        lambda: {
            'eth0': [
                mock.MagicMock(
                    address=None,
                    family=None
                )
            ]
        }
    ]:
        monkeypatch.setattr(psutil, 'net_if_addrs', mock_net_if_addrs)

        agent = MockAgent(port=12345, interface='nonexistent')
        agent.collect_server_metadata()

        assert agent.ip is None

        assert_msg_in_logfile(
            'Could not deduce IP address from hostname: '
            'Name or service not known'
        )


def test_collect_server_metadata_hostname_error(
    monkeypatch, setup_temp_file_logging_with_fallback, assert_msg_in_logfile
):
    """Test handling of socket error when getting hostname."""
    def mock_gethostname():
        raise socket.error('Failed to get hostname')

    monkeypatch.setattr(socket, 'gethostname', mock_gethostname)

    agent = MockAgent(port=12345)
    agent.collect_server_metadata()

    assert agent.hostname == 'unknown'

    assert_msg_in_logfile('Could not get hostname: Failed to get hostname')


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
    commands = ['cmd1', 'cmd1']

    agent = MockAgent(whitelist_commands=commands)

    assert all(cmd in agent.whitelist_commands for cmd in commands)


def test_explicit_whitelist_commands_none_uses_default_list():
    """Test that None whitelist_commands uses default list."""
    agent = MockAgent(whitelist_commands=None)
    assert agent.whitelist_commands == MockAgent().whitelist_commands


def test_class_whitelist_commands():
    """Test that class-level whitelist_commands are properly handled."""
    MockAgent.whitelist_commands = ['cmd1', 'cmd2']

    agent1 = MockAgent()

    assert 'cmd1' in agent1.whitelist_commands
    assert 'cmd2' in agent1.whitelist_commands

    agent2 = MockAgent(whitelist_commands=['cmd3'])

    assert 'cmd3' in agent2.whitelist_commands
    assert 'cmd1' in agent2.whitelist_commands
    assert 'cmd2' in agent2.whitelist_commands

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

        agent = MockAgent.from_config_file(filename=tmp.name)
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

    assert captured_request['headers'] == {'Accept': 'application/json'}, (
        "Expected headers {'Accept': 'application/json'}, "
        'but got %r' % captured_request['headers']
    )


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
    assert captured_request['headers'] == expected_headers, (
        'Expected headers %r, but got %r'
        % (expected_headers, captured_request['headers'])
    )


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
    assert captured_request['headers'] == expected_headers, (
        'Expected headers %r, but got %r'
        % (expected_headers, captured_request['headers'])
    )


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
    assert captured_request['headers'] == expected_headers, (
        'Expected headers %r, but got %r'
        % (expected_headers, captured_request['headers'])
    )


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
    assert captured_request['headers'] == expected_headers, (
        'Expected headers %r, but got %r'
        % (expected_headers, captured_request['headers'])
    )


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
            payload={'test': 'data'},
            api_key='test-token'
        )

    expected_headers = {
        'Content-type': 'application/json',
        'Authorization': 'Bearer test-token'
    }
    assert captured_request['headers'] == expected_headers, (
        'Expected headers %r, but got %r'
        % (expected_headers, captured_request['headers'])
    )


def test_is_process_running_when_any_process_running():
    agent = MockAgent(processes=['nginx', 'named'])

    output = 'COMMAND\nnginx\nssh\nnamed\n'

    with mock.patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value = mock_popen_with_output(output)

        result = agent._is_process_running()

        assert result, (
            'Expected _is_process_running to return True when at '
            'least one process from the list is running.'
        )


def test_is_process_running_didnt_find_any_process():
    agent = MockAgent(processes=['nginx', 'ssh'])
    output = 'COMMAND\napache\npostgres\n'

    with mock.patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value = mock_popen_with_output(output)

        result = agent._is_process_running()

        assert not result, (
            'Expected _is_process_running to return False when '
            'none of the required processes are found.'
            )


def test_is_process_running_matches_first_process_only():
    agent = MockAgent(processes=['named', 'nonexistent'])
    output = 'COMMAND\nnamed\nanother\n'

    with mock.patch('subprocess.Popen') as mock_popen:
        mock_popen.return_value = mock_popen_with_output(output)

        result = agent._is_process_running()

        assert result


def test_is_process_running_with_error():
    agent = MockAgent(processes=['nginx'])

    with mock.patch('subprocess.Popen', side_effect=OSError('boom')):
        with mock.patch(
            'agents_infra.agents.base.maybe_log_message'
        ) as mock_log:

            result = agent._is_process_running()

            assert not result, (
                'Expected _is_process_running to return False '
                'when OSError is raised.'
            )

            mock_log.assert_called_once_with(
                'Process check failed: boom',
                logger=agent.logger,
                exc_info=True,
            )


def test_is_ssh_service_active_returns_true_when_active():
    agent = MockAgent()
    output = 'active\n'

    with mock.patch('agents_infra.agents.base.subprocess.Popen') as mock_popen:
        mock_popen.return_value = mock_popen_with_output(output, '')

        result = agent.is_ssh_service_active()

        assert result, (
            'Expected is_ssh_service_active return True when '
            'ssh active'
        )


def test_is_ssh_service_active_returns_false_when_inactive():
    agent = MockAgent()
    output = 'inactive\n'

    with mock.patch('agents_infra.agents.base.subprocess.Popen') as mock_popen:
        mock_popen.return_value = mock_popen_with_output(output, '')

        result = agent.is_ssh_service_active()

        assert not result, (
            'Expected is_ssh_service_active return False when '
            'ssh inactive'
        )


def test_is_ssh_service_active_returns_false_when_output_empty():
    agent = MockAgent()
    output = ''

    with mock.patch('agents_infra.agents.base.subprocess.Popen') as mock_popen:
        mock_popen.return_value = mock_popen_with_output(output, '')

        result = agent.is_ssh_service_active()

        assert not result, (
            'Expected is_ssh_service_active return False when '
            'output is empty'
        )


def test_is_ssh_service_active_logs_and_returns_false_on_oserror():
    agent = MockAgent()

    with mock.patch(
                   'agents_infra.agents.base.subprocess.Popen',
                   side_effect=OSError('boom')
    ):
        with mock.patch(
            'agents_infra.agents.base.maybe_log_message'
        ) as mock_log:
            result = agent.is_ssh_service_active()

            assert result is False, 'Expected return False, when OSError'
            mock_log.assert_called_once_with(
                'SSH service check failed: boom',
                agent.logger,
                exc_info=True
                )


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

    match = re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', timestamp)
    assert match is not None and match.group(0) == timestamp, (
        "Timestamp '%s' does not match format YYYY-MM-DD HH:MM:SS"
        % timestamp
    )


def test_tag_parsing_full_config():
    """
    Test that all tags (env, role, region) are correctly parsed
    from the config file.
    """
    config_content = """
[server]
name = test_server
env = production
role = web
region = eu-central
"""
    agent = load_agent_from_config(config_content)

    expected_tags = {
        'env': 'production',
        'role': 'web',
        'region': 'eu-central',
    }
    assert agent.tags == expected_tags


def test_tag_parsing_partial_config():
    """
    Test that only provided tags are parsed, and missing ones are ignored.
    """
    config_content = """
[server]
name = test_server
env = staging
role = db
"""
    agent = load_agent_from_config(config_content)

    expected_tags = {
        'env': 'staging',
        'role': 'db',
    }
    assert agent.tags == expected_tags
    assert 'region' not in agent.tags


def test_tag_parsing_ignores_empty_values():
    """
    Test that tags with empty values in the config are not included.
    """
    config_content = """
[server]
name = test_server
env = dev
role =
region = us-east
"""
    agent = load_agent_from_config(config_content)

    expected_tags = {
        'env': 'dev',
        'region': 'us-east',
    }
    assert agent.tags == expected_tags
    assert 'role' not in agent.tags


def test_tag_parsing_normalizes_values():
    """
    Tests that tag values are correctly normalized:
    - Whitespace is stripped from both ends.
    - Value is converted to lowercase.
    """
    config_content = """
[server]
name = test_server
env =   Production
role =   WEB
"""
    agent = load_agent_from_config(config_content)

    expected_tags = {
        'env': 'production',
        'role': 'web',
    }
    assert agent.tags == expected_tags


def test_status_dict_includes_tags_when_present():
    """
    Test that status_to_dict() includes the 'tags' key
    when tags are configured.
    """
    config_content = """
[server]
name = test_server
env = production
role = web
"""
    agent = load_agent_from_config(config_content)
    status = agent.status_to_dict()

    assert 'tags' in status
    assert status['tags'] == {'env': 'production', 'role': 'web'}


def test_status_dict_omits_tags_for_backward_compatibility():
    """
    Test that status_to_dict() does not include the 'tags' key
    when no tags are configured, ensuring backward compatibility.
    """
    config_content = """
[server]
name = old_agent_server
"""
    agent = load_agent_from_config(config_content)
    status = agent.status_to_dict()

    assert agent.tags == {}
    assert 'tags' not in status
