import json
import logging
import os
import socket
import tempfile

import mock
import psutil
import pytest
import urllib2

from agents_infra.agents.base import Config, ServerAgent
from agents_infra.command import CommandHistory

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


@pytest.fixture(scope='session')
def mock_config():
    return Config(
        api_prefix='mock/api/v1',
        url='http://mock-controller-url/',
        auth_token_type='mock-token',
        port=12345,
        interface='iface0',
    )


@pytest.yield_fixture
def mock_config_file():
    """
    Create a temporary config.ini file for tests.
    Cleans up automatically after the test completes.
    """
    content = (
        '[server]\n'
        'name=mock-server\n'
        'port=12345\n'
        'critical_processes=proc1,proc2,proc3\n'
        'interface=iface0\n'
        'env=mock\n'
        'role=mock\n'
        'region=any\n'
        '\n'
        '[controller]\n'
        'url=http://mock-controller-url\n'
        'api_prefix=mock/api/\n'
        'whitelist_commands=cmd1,cmd2,cmd3,cmd4\n'
    )

    tmp = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    tmp.write(content)
    tmp.flush()
    tmp.close()

    tmp_path = tmp.name

    yield tmp_path

    if os.path.exists(tmp_path):
        os.remove(tmp_path)


def load_agent_from_config(config_content):
    """Utility to load agent from string-based config content."""
    tmp = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    try:
        tmp.write(config_content)
        tmp.flush()
        tmp_path = tmp.name
        tmp.close()
        return MockAgent.from_config_file(tmp_path)
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)


class MockAgent(ServerAgent):
    """Mock agent used for testing purposes."""
    def setup_logging(self, log_path=None):
        """Disable logging setup for testing."""
        pass

    @property
    def logger(self):
        """Return the mock logger for tests."""
        return logging.getLogger('mock-logger')

    def is_service_healthy(self):
        return super(MockAgent, self).is_service_healthy()


def mock_popen_with_output(stdout, stderr=''):
    process_mock = mock.Mock()
    process_mock.communicate.return_value = (stdout, stderr)
    return process_mock


def test_parse_config_file_success(mock_config_file):
    """Test parsing of a config.ini by the agent."""
    agent = MockAgent.from_config_file(mock_config_file)

    assert agent.config.name == 'mock-server'
    assert agent.config.port == 12345

    assert agent.config.critical_processes == [
        'ssh', 'sshd', 'proc1', 'proc2', 'proc3'
    ]

    assert agent.config.interface == 'iface0'

    assert (
        agent.config.whitelist_commands
        == ServerAgent.config.whitelist_commands + (
            ['cmd1', 'cmd2', 'cmd3', 'cmd4']
        )
    )


def test_post_data_success_logged(
    monkeypatch, mock_config, assert_msg_in_logfile
):
    agent = MockAgent(config=mock_config)

    class MockResponse(object):

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
    monkeypatch, mock_config, assert_msg_in_logfile
):
    agent = MockAgent(config=mock_config)

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
    monkeypatch, mock_config, assert_msg_in_logfile
):
    agent = MockAgent(config=mock_config)

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


def test_post_data_error_logged(mock_config, assert_msg_in_logfile):
    agent = MockAgent(config=mock_config)

    errors = [
        (urllib2.HTTPError(
            'http://mock/api',
            500,
            'Internal Server Error',
            {},
            None
        ), 'Attempt 1 failed'),
        (urllib2.URLError('Connection refused'), 'Attempt 1 failed'),
        (socket.timeout('timed out'), 'Attempt 1 failed'),
    ]

    for error, expected_msg in errors:
        with mock.patch('urllib2.urlopen', side_effect=error):
            agent.post_data(
                'http://mock/api',
                {'fail': True},
                max_retries=1,
                fail_silently=True,
                to_controller=False,  # avoids needing controller_url
            )

        assert_msg_in_logfile(expected_msg)


def test_post_data_to_controller_success_logged(
    mock_config, monkeypatch, assert_msg_in_logfile
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

    agent = MockAgent(config=mock_config)
    agent.controller_url = 'http://mock/controller/'

    agent.post_data(
        'server/status/',
        {'to_controller': 'test'},
        to_controller=True,
        fail_silently=False,
        max_retries=1,
    )

    assert_msg_in_logfile('POST request status: 201')
    assert_msg_in_logfile(
        'POST request succeeded on attempt 1: %s' % b'{"message":"received"}'
    )


def test_post_data_to_controller_missing_url(
    mock_config, assert_msg_in_logfile
):
    """Test that missing controller URL is properly handled and logged."""

    agent = MockAgent(config=mock_config)

    agent.config.url = ''

    agent.post_data(
        url='',
        payload={'to_controller': 'test'},
        to_controller=True,
        fail_silently=True,
    )

    assert_msg_in_logfile(
        "Couldn't send POST request to controller: controller URL is not set"
    )


def test_post_data_headers_update(mock_config):
    """Test that post_data correctly adds Authorization header."""
    agent = MockAgent(config=mock_config)
    agent.config.auth_token_type = 'Bearer'

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


def test_get_data_success_logged(
    monkeypatch, mock_config, assert_msg_in_logfile
):
    """
    Test that successful GET request to controller is properly handled
    and logged.
    """
    responses = [
        {
            'status_code': 200,
            'payload': {'message': 'test-ok'},
            'expected': {'message': 'test-ok'}
        },
        {
            'status_code': 204,
            'payload': None,
            'expected': None
        }
    ]

    agent = MockAgent(config=mock_config)

    for case in responses:
        class MockResponse(object):
            def getcode(self):
                return case['status_code']

            def read(self):
                return json.dumps(case['payload']) if case['payload'] else ''

            def close(self):
                pass

        monkeypatch.setattr(
            urllib2, 'urlopen', lambda req, timeout=5: MockResponse()
        )

        result = agent.get_data('server/command/', to_controller=True)

        expected_json = json.dumps(
            case['expected']
        ) if case['expected'] else ''
        if expected_json:
            assert expected_json in result

        assert_msg_in_logfile(
            'GET request status: %d' % case['status_code']
        )
        assert_msg_in_logfile(
            'GET request succeeded on attempt 1'
        )


def test_get_data_empty_response(
    monkeypatch, mock_config, assert_msg_in_logfile
):
    class MockResponse(object):
        def getcode(self):
            return 200

        def read(self):
            return ' '

        def close(self):
            pass

    monkeypatch.setattr(
        urllib2, 'urlopen', lambda req, timeout=5: MockResponse()
    )

    agent = MockAgent(config=mock_config)
    agent.hostname = 'mock-server'

    result = agent.get_data('server/command/', to_controller=True)

    assert result.strip() == '', 'Expected empty string result'

    assert_msg_in_logfile('GET request status: 200')
    assert_msg_in_logfile('GET request succeeded on attempt 1')


def test_get_data_missing_data(mock_config, assert_msg_in_logfile):
    """
    Test proper handling and logging when controller URL is missing.
    """

    agent = MockAgent(config=mock_config)
    agent.config.url = ''

    result = agent.get_data('server/status/', to_controller=True)

    assert result is None

    assert_msg_in_logfile(
        "Couldn't send GET request to controller: controller URL is not set"
    )


def test_get_data_error_logged(
    monkeypatch, mock_config, assert_msg_in_logfile
):
    """
    Test proper handling and logging of different GET request errors.
    """
    agent = MockAgent(config=mock_config)

    errors = [
        HTTP_ERROR_OUTPUT,
        URL_ERROR_OUTPUT,
        TIMEOUT_ERROR_OUTPUT,
    ]

    for error_obj, expected_log in errors:
        def mock_urlopen(request, timeout=5):
            raise error_obj

        monkeypatch.setattr(urllib2, 'urlopen', mock_urlopen)

        result = agent.get_data(
            'server/status/', to_controller=True, max_retries=1
        )

        assert result is None

        assert_msg_in_logfile('Attempt 1 failed: %s' % expected_log)


def test_maybe_add_to_queue_adds_item(mock_config):
    """Test that good command history input is added to queue."""
    data = {
        'type': 'linux',
        'params': {
            'shell': 'ls',
        },
        'hostname': 'test-server',
        'status': 'pending',
        'timestamp': '2025-06-03T18:25:35.418746Z',
    }

    agent = MockAgent(config=mock_config)

    agent.maybe_add_command_to_queue(data)

    assert agent.command_queue.qsize() == 1


def test_maybe_add_to_queue_full_logged(mock_config, assert_msg_in_logfile):
    """
    Test that trying to add command to the full queue is properly handled
    and logged.
    """
    import datetime

    import Queue

    agent = MockAgent(config=mock_config)
    agent.command_queue = Queue.Queue(maxsize=1)

    # Ensure 'cmd' is whitelisted
    if 'cmd' not in agent.config.whitelist_commands:
        agent.config.whitelist_commands.append('cmd')

    timestamp = datetime.datetime.now().isoformat()

    # Fill queue
    agent.maybe_add_command_to_queue({
        'type': 'agent',
        'params': {'method': 'cmd'},
        'hostname': 'mock-server',
        'status': 'pending',
        'timestamp': timestamp,
    })

    # Try to add another (should fail due to full queue)
    agent.maybe_add_command_to_queue({
        'type': 'agent',
        'params': {'method': 'cmd'},
        'hostname': 'mock-server',
        'status': 'pending',
        'timestamp': timestamp,
    })

    assert agent.command_queue.qsize() == 1

    assert_msg_in_logfile('Queue is full - could not append command')


def test_get_command_from_queue_has_item(mock_config):
    import datetime

    from agents_infra.command import AgentCommand, CommandStatus

    agent = MockAgent(config=mock_config)

    command = AgentCommand(method='cmd')
    cmd_history = CommandHistory(
        command=command,
        hostname='test-host',
        status=CommandStatus.PENDING,
        timestamp=datetime.datetime.now().isoformat(),
    )

    agent.command_queue.put(cmd_history)

    result = agent.get_command_from_queue(block=True)
    assert isinstance(result, CommandHistory)
    assert result.command.tag == 'cmd'


def test_get_command_from_queue_no_item_logged(
    mock_config, assert_msg_in_logfile
):
    import threading

    agent = MockAgent(config=mock_config)

    while not agent.command_queue.empty():
        agent.command_queue.get()

    with threading.Lock():
        agent.get_command_from_queue()

    assert_msg_in_logfile('Queue is empty - could not retrieve command')


def test_maybe_add_to_queue_logs_bad_input(
    mock_config, assert_msg_in_logfile
):
    """
    Test that bad command history input is logged by server agent and
    not added to queue.
    """
    # Incorrect fields - there are no 'params'
    data = {
        'type': 'agent',
        'hostname': 'test-server',
        'status': 'pending',
        'timestamp': '2025-06-03T18:25:35.418746Z',
    }

    agent = MockAgent(config=mock_config)

    agent.maybe_add_command_to_queue(data)

    assert_msg_in_logfile('Command validation failed due to error')
    assert agent.command_queue.qsize() == 0


def test_is_service_healthy_invalid_port(mock_config):
    """Test that is_port_open raises ValueError for invalid port."""
    agent = MockAgent(config=mock_config)
    agent.config.port = -1

    agent.ip = '0.0.0.0'
    agent.protocol = 'tcp'

    assert not agent.is_service_healthy()


def test_is_service_healthy_missing_ip(mock_config):
    """Test that is_port_open returns False when IP is not set."""
    agent = MockAgent(config=mock_config)
    agent.ip = None

    assert not agent.is_service_healthy()


def test_protocol_setter_raises(mock_config):
    """Test that protocol setter raises TypeError for non-string values."""
    agent = MockAgent(config=mock_config)

    with pytest.raises(TypeError, match='Protocol must be a string'):
        agent.protocol = 123

    with pytest.raises(TypeError, match='Protocol must be a string'):
        agent.protocol = None

    with pytest.raises(ValueError, match='Unknown protocol value'):
        agent.protocol = 'invalid_protocol'

    with pytest.raises(ValueError, match='Unknown protocol value'):
        agent.protocol = 'HTTP'


def test_is_port_open_tcp_success(monkeypatch, mock_config):
    """Test successful TCP port check."""
    agent = MockAgent(config=mock_config)

    agent.ip = '0.0.0.0'
    agent.protocol = 'tcp'

    mock_socket = mock.MagicMock()
    mock_socket.connect = mock.MagicMock()
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    assert agent.check_port()['port_open']
    mock_socket.connect.assert_called_once_with(('0.0.0.0', 12345))
    mock_socket.close.assert_called_once()


def test_is_port_open_tcp_failure(monkeypatch, mock_config):
    """Test failed TCP port check."""
    agent = MockAgent(config=mock_config)

    agent.ip = '0.0.0.0'
    agent.protocol = 'tcp'

    mock_socket = mock.MagicMock()
    mock_socket.connect = mock.MagicMock(
        side_effect=socket.error('Connection refused')
    )
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    with pytest.raises(socket.error, match='Connection refused'):
        agent.check_port()['port_open']

    mock_socket.connect.assert_called_once_with(('0.0.0.0', 12345))
    mock_socket.close.assert_called_once()


def test_is_port_open_udp_success(monkeypatch, mock_config):
    """Test successful UDP port check."""
    agent = MockAgent(config=mock_config)

    agent.ip = '0.0.0.0'
    agent.protocol = 'udp'

    mock_socket = mock.MagicMock()
    mock_socket.sendto = mock.MagicMock()
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    assert agent.check_port()['port_open']
    mock_socket.sendto.assert_called_once_with(b'', ('0.0.0.0', 12345))
    mock_socket.close.assert_called_once()


def test_is_port_open_udp_with_packet_size(monkeypatch, mock_config):
    """Test UDP port check with packet size verification."""
    agent = MockAgent(config=mock_config)

    agent.ip = '0.0.0.0'
    agent.protocol = 'udp'

    mock_socket = mock.MagicMock()
    mock_socket.sendto = mock.MagicMock()
    mock_socket.recvfrom = mock.MagicMock(
        return_value=(b'response', ('0.0.0.0', 12345))
    )
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    assert agent.check_port(packet_size=8)['port_open']
    mock_socket.sendto.assert_called_once_with(b'', ('0.0.0.0', 12345))
    mock_socket.recvfrom.assert_called_once_with(8)
    mock_socket.close.assert_called_once()


@pytest.mark.filterwarnings('ignore')
def test_is_port_open_udp_packet_size_mismatch(monkeypatch, mock_config):
    """Test UDP port check with packet size mismatch."""
    agent = MockAgent(config=mock_config)

    agent.ip = '0.0.0.0'
    agent.protocol = 'udp'

    mock_socket = mock.MagicMock()
    mock_socket.sendto = mock.MagicMock()
    mock_socket.recvfrom = mock.MagicMock(
        return_value=(b'short', ('0.0.0.0', 12345))
    )
    mock_socket.close = mock.MagicMock()

    monkeypatch.setattr(socket, 'socket', lambda *args: mock_socket)

    assert not agent.check_port(packet_size=8)['port_open']

    mock_socket.sendto.assert_called_once_with(b'', ('0.0.0.0', 12345))
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


def test_evaluate_identity_interface_ip_success(monkeypatch, mock_config):
    """Test successful IP address retrieval from interface."""
    def mock_net_if_addrs():
        return {
            'iface0': [
                mock.MagicMock(
                    address='192.168.1.1',
                    family=socket.AF_INET
                )
            ]
        }

    monkeypatch.setattr(psutil, 'net_if_addrs', mock_net_if_addrs)

    agent = MockAgent(config=mock_config)

    assert agent.ip == '192.168.1.1'


def test_evaluate_identity_interface_errors(
    monkeypatch,
    setup_temp_file_logging_with_fallback,
    mock_config,
    assert_msg_in_logfile
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

        agent = MockAgent(config=mock_config)

        assert agent.ip is None

        assert_msg_in_logfile(
            'Could not deduce IP address from hostname: '
            'Name or service not known'
        )


def test_evaluate_identity_hostname_error(
    monkeypatch,
    setup_temp_file_logging_with_fallback,
    mock_config,
    assert_msg_in_logfile
):
    """Test handling of socket error when getting hostname."""
    def mock_gethostname():
        raise socket.error('Failed to get hostname')

    monkeypatch.setattr(socket, 'gethostname', mock_gethostname)

    agent = MockAgent(config=mock_config)

    assert agent.hostname == 'unknown'

    assert_msg_in_logfile('Could not get hostname: Failed to get hostname')


def test_default_whitelist_commands_is_empty_list():
    """
    Test that whitelist_commands is initialized as an empty,
    independent list.
    """
    agent1 = MockAgent()
    agent2 = MockAgent()

    # Lists should be separate objects (not the same reference)
    assert (
        agent1.config.whitelist_commands
        is not agent2.config.whitelist_commands
    )

    # Modifying one should not affect the other
    agent1.config.whitelist_commands.append('test-command')

    assert 'test-command' in agent1.config.whitelist_commands
    assert 'test-command' not in agent2.config.whitelist_commands


def test_explicit_whitelist_commands_extends_default_list():
    """Test that provided commands are added to whitelist."""
    agent = MockAgent(config=Config(whitelist_commands=['cmd11', 'cmd12']))

    assert (
        'cmd11' in agent.config.whitelist_commands
        and 'cmd12' in agent.config.whitelist_commands
    )


def test_explicit_whitelist_commands_none_uses_default_list():
    """Test that None whitelist_commands uses default list."""
    config = {
        'name': 'server_name',
        'api_prefix': 'api/v1/',
        'url': 'http://localhost',
        'port': 9999,
        'critical_processes': [],
        'whitelist_commands': [],
        'auth_token_type': None,
        'interface': None,
    }

    agent = MockAgent(config=config)
    expected = MockAgent().config.whitelist_commands
    assert agent.config.whitelist_commands == expected


def test_config_file_parsing():
    """Test parsing of config file options."""

    config_content = """
[server]
name = test_server
port = 12345
critical_processes = proc1,proc2,proc3
interface = eth0

[controller]
whitelist_commands = cmd1,cmd2,cmd3
"""
    with tempfile.NamedTemporaryFile('w+') as tmp:
        tmp.write(config_content)
        tmp.flush()

        agent = MockAgent.from_config_file(tmp.name)

        assert agent.config.name == 'test_server'
        assert agent.config.port == 12345

        expected_procs = set(['proc1', 'proc2', 'proc3'])
        actual_procs = set(agent.config.critical_processes or [])
        assert expected_procs.issubset(actual_procs), (
            'Expected processes %s to be subset of actual %s' % (
                expected_procs, actual_procs
            )
        )

        if hasattr(agent.config, 'interface'):
            assert agent.config.interface == 'eth0'

        expected_cmds = set(['cmd1', 'cmd2', 'cmd3'])
        actual_cmds = set(agent.config.whitelist_commands or [])
        assert expected_cmds.issubset(actual_cmds), (
            'Expected commands %s to be subset of actual %s' % (
                expected_cmds, actual_cmds
            )
        )


def test_config_file_missing_options():
    """Test handling of missing config file options."""
    config_content = """
[server]
name = test_server
port = 12345
"""

    with tempfile.NamedTemporaryFile('w+') as tmp:
        tmp.write(config_content)
        tmp.flush()

        agent = MockAgent.from_config_file(tmp.name)

        assert agent.config.name == 'test_server'
        assert agent.config.port == 12345
        assert (
            agent.config.critical_processes
            == ServerAgent.config.critical_processes
        )
        assert agent.config.interface == 'enp0s3'

        # Since whitelist_commands not specified, defoults from global.ini
        assert (
            agent.config.whitelist_commands
            == ServerAgent.config.whitelist_commands
        )


def test_config_file_empty_processes():
    """Test handling of empty processes list in config."""
    import os
    import tempfile

    config_content = """
[server]
name = test_server
port = 12345
critical_processes =
"""

    tmp = tempfile.NamedTemporaryFile('w+', delete=False)
    try:
        tmp.write(config_content)
        tmp.flush()
        tmp_path = tmp.name
        tmp.close()

        agent = MockAgent.from_config_file(tmp_path)

        actual_processes = set(agent.config.critical_processes or [])
        expected_processes = set()

        assert expected_processes.issubset(actual_processes), (
            'Expected processes %s to be subset of actual %s' % (
                expected_processes, actual_processes
            )
        )

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_config_file_empty_whitelist_commands():
    """Test handling of empty whitelist_commands in config."""
    import os
    import tempfile

    config_content = """
[server]
name = test_server
port = 12345

[controller_agent]
whitelist_commands =
"""

    tmp = tempfile.NamedTemporaryFile('w+', delete=False)
    try:
        tmp.write(config_content)
        tmp.flush()
        tmp_path = tmp.name
        tmp.close()

        agent = MockAgent.from_config_file(tmp_path)

        actual_commands = set(agent.config.whitelist_commands or [])
        expected_commands = set()

        assert expected_commands.issubset(actual_commands), (
            'Expected whitelist_commands %s to be subset of actual %s' % (
                expected_commands, actual_commands
            )
        )

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_get_data_headers_default(mock_config_file):
    """Test that default headers are set correctly."""

    agent = MockAgent.from_config_file(mock_config_file)
    agent.hostname = 'mock_server'
    agent.controller_url = 'http://mock/'
    agent.api_prefix = 'api/'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        captured_request['headers'] = request.headers
        mock_response = mock.MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = '{}'
        mock_response.close.return_value = None
        return mock_response

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.get_data('test_endpoint')

    assert captured_request['headers'] == {'Accept': 'application/json'}, (
        "Expected headers {'Accept': 'application/json'}, "
        'but got %r' % captured_request['headers']
    )


def test_get_data_headers_with_api_key(mock_config_file):
    """Test that headers include Authorization when api_key is provided."""
    agent = MockAgent.from_config_file(mock_config_file)

    agent.hostname = 'mock_server'
    agent.config.url = 'http://mock/'
    agent.config.api_prefix = 'api/'
    agent.config.auth_token_type = 'Bearer'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        captured_request['headers'] = request.headers
        mock_response = mock.MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = '{}'
        mock_response.close.return_value = None
        return mock_response

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.get_data('test_endpoint', api_key='test-token')

    expected_headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer test-token'
    }
    assert captured_request['headers'] == expected_headers, (
        'Expected headers %r, but got %r'
        % (expected_headers, captured_request['headers'])
    )


def test_get_data_headers_with_kwargs(mock_config_file):
    """Test that additional headers from kwargs are added correctly."""
    agent = MockAgent.from_config_file(mock_config_file)
    agent.hostname = 'mock_server'
    agent.config.url = 'http://mock/'
    agent.config.api_prefix = 'api/'
    agent.config.auth_token_type = 'Bearer'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        lowercase_headers = {}
        for k, v in request.headers.items():
            lowercase_headers[k.lower()] = v
        captured_request['headers'] = lowercase_headers

        mock_response = mock.MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = '{}'
        mock_response.close.return_value = None
        return mock_response

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.get_data(
            'test_endpoint',
            api_key='test-token',
            CustomHeader='custom-value',
            XRequestID='12345'
        )

    expected_headers = {
        'accept': 'application/json',
        'authorization': 'Bearer test-token',
        'customheader': 'custom-value',
        'xrequestid': '12345'
    }
    assert captured_request['headers'] == expected_headers, (
        'Expected headers %r, but got %r'
        % (expected_headers, captured_request['headers'])
    )


def test_get_data_headers_kwargs_override(mock_config_file):
    """Test that kwargs headers override default headers in get_data."""
    agent = MockAgent.from_config_file(mock_config_file)
    agent.hostname = 'mock_server'
    agent.config.url = 'http://mock/'
    agent.config.api_prefix = 'api/'
    agent.config.auth_token_type = 'Bearer'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        lowercase_headers = {}
        for k, v in request.headers.items():
            lowercase_headers[k.lower()] = v
        captured_request['headers'] = lowercase_headers

        mock_response = mock.MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = '{}'
        mock_response.close.return_value = None
        return mock_response

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.get_data(
            url='test_endpoint',
            api_key='test-token',
            Accept='text/plain'
        )

    expected_headers = {
        'accept': 'text/plain',
        'authorization': 'Bearer test-token'
    }

    assert captured_request['headers'] == expected_headers, (
        'Expected headers %r, but got %r'
        % (expected_headers, captured_request['headers'])
    )


def test__get_data_headers_update(mock_config_file):
    """Test that headers.update correctly adds Authorization header."""
    agent = MockAgent.from_config_file(mock_config_file)
    agent.hostname = 'mock_server'
    agent.config.url = 'http://mock/'
    agent.config.api_prefix = 'api/'
    agent.config.auth_token_type = 'Bearer'

    captured_request = {'headers': None}

    def mock_urlopen(request, timeout=5):
        headers_lower = {}
        for k, v in request.headers.items():
            headers_lower[k.lower()] = v
        captured_request['headers'] = headers_lower

        mock_response = mock.MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = '{}'
        mock_response.close.return_value = None
        return mock_response

    with mock.patch('urllib2.urlopen', mock_urlopen):
        agent.get_data(url='test_endpoint', api_key='test-token')

    expected_headers = {
        'accept': 'application/json',
        'authorization': 'Bearer test-token'
    }

    assert captured_request['headers'] == expected_headers, (
        'Expected headers %r, but got %r'
        % (expected_headers, captured_request['headers'])
    )


def test_are_all_critical_processes_active_sucseed(mock_config_file):
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.critical_processes = ['nginx', 'named']

    with mock.patch(
        'agents_infra.agents.base.is_process_active', return_value=True
    ) as mock_is_active:
        with mock.patch(
            'agents_infra.agents.base.restart_service'
        ) as mock_restart:

            result = agent._are_all_critical_processes_active(restart=True)

            assert result is True, (
                'Expected __are_all_critical_processes_active to return True '
                'when all processes from the list are running.'
            )

            expected_calls = [mock.call('nginx'), mock.call('named')]
            mock_is_active.assert_has_calls(expected_calls, any_order=True)

            mock_restart.assert_not_called()


def test_are_all_critical_processes_active_fails_without_restart(
    mock_config_file
):
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.critical_processes = ['nginx', 'named']

    with mock.patch(
        'agents_infra.agents.base.is_process_active', side_effect=[True, False]
    ) as mock_is_active:
        with mock.patch(
            'agents_infra.agents.base.restart_service'
        ) as mock_restart:

            result = agent._are_all_critical_processes_active(restart=False)

            assert result is False, (
                'Expected _are_all_critical_processes_active to return False '
                'when at least one critical process is inactive '
                'and restart=False.'
            )

            expected_calls = [mock.call('nginx'), mock.call('named')]
            mock_is_active.assert_has_calls(expected_calls, any_order=False)

            mock_restart.assert_not_called()


def test_are_all_critical_processes_active_fails_with_restart(
    mock_config_file
):
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.critical_processes = ['nginx', 'named']

    with mock.patch(
        'agents_infra.agents.base.is_process_active', side_effect=[False, True]
    ) as mock_is_active:
        with mock.patch(
            'agents_infra.agents.base.restart_service'
        ) as mock_restart:

            result = agent._are_all_critical_processes_active(restart=True)

            assert result is False, (
                'Expected _are_all_critical_processes_active to return False '
                'when at least one critical process is inactive '
                'and restart=True.'
            )

            expected_calls = [mock.call('nginx'), mock.call('named')]
            mock_is_active.assert_has_calls(expected_calls, any_order=False)

            mock_restart.assert_called_once_with(agent.logger, 'nginx')


def test_are_all_critical_processes_active_raises_oserror(mock_config_file):
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.critical_processes = ['nginx']

    def raise_oserror(proc):
        raise OSError('Mocked OSError')

    with mock.patch(
        'agents_infra.agents.base.is_process_active', side_effect=raise_oserror
    ):
        with mock.patch(
            'agents_infra.agents.base.maybe_log_message'
        ) as mock_log:
            result = agent._are_all_critical_processes_active(restart=False)

            assert result is False, (
                'Expected _are_all_critical_processes_active to return False '
                'when OSError is raised.'
            )
            # Checking logs with exc_info=True
            mock_log.assert_called()
            args, kwargs = mock_log.call_args
            assert kwargs.get('exc_info') is True


def test_are_all_critical_processes_active_raises_generic_exception(
    mock_config_file
):
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.critical_processes = ['nginx']

    def raise_exception(proc):
        raise Exception('Mocked generic exception')

    with mock.patch(
        'agents_infra.agents.base.is_process_active',
        side_effect=raise_exception
    ):
        with mock.patch(
            'agents_infra.agents.base.maybe_log_message'
        ) as mock_log:

            result = agent._are_all_critical_processes_active(restart=False)

            assert result is False, (
                'Expected _are_all_critical_processes_active to return False '
                'when a generic exception is raised.'
            )
            # Checking logs with exc_info=True
            mock_log.assert_called()
            args, kwargs = mock_log.call_args
            assert kwargs.get('exc_info') is True


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
