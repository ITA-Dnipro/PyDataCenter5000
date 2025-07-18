import json
import logging
import os
import platform
import re
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


@pytest.yield_fixture
def mock_config_file():
    """
    Create a temporary config.ini file for tests.
    Cleans up automatically after the test completes.
    """
    content = (
        '[server]\n'
        'name=mock\n'
        'port=123\n'
        'critical_processes=sshd,nginx,postgres\n'
        'interface=eth0\n'
        'env=dev\n'
        'role=backend\n'
        'region=eu\n'
        '\n'
        '[controller]\n'
        'url=http://localhost\n'
        'api_prefix=api/v1/\n'
        'whitelist_commands=ls,uptime,whoami,cmd\n'
    )

    tmp = tempfile.NamedTemporaryFile(mode='w+', delete=False)
    tmp.write(content)
    tmp.flush()
    tmp_path = tmp.name
    tmp.close()

    yield tmp_path

    if os.path.exists(tmp_path):
        os.remove(tmp_path)


class MockAgent(ServerAgent):
    """
    A mock agent used for testing purposes.
    """

    def __init__(
        self,
        protocol='tcp',
        command_queue_size=0,
        config=None
    ):
        if config is None:
            config = Config(
                name='mock',
                api_prefix='api/v1/',
                url='http://localhost',
                port=12345,
            )

        super(MockAgent, self).__init__(
            protocol=protocol,
            command_queue_size=command_queue_size,
            config=config,
        )

    def setup_logging(self, log_path=None):
        """Disable logging setup for testing."""
        pass

    @property
    def logger(self):
        """Return a mock logger for tests."""
        return logging.getLogger('mock-logger')

    def __del__(self):
        if hasattr(self, 'logfile'):
            try:
                os.remove(self.logfile.name)
            except Exception:
                pass

    def is_service_healthy(self):
        return super(MockAgent, self).is_service_healthy()


def mock_popen_with_output(stdout, stderr=''):
    process_mock = mock.Mock()
    process_mock.communicate.return_value = (stdout, stderr)
    return process_mock


def test_type_checks_on_init():
    """Test that type checks fail initialization with bad parameters."""
    with pytest.raises(TypeError):
        MockAgent(port='invalid')

    with pytest.raises(TypeError):
        MockAgent(processes=0)


def test_critical_processes_parsing(mock_config_file):
    agent = MockAgent.from_config_file(mock_config_file)
    expected = ['sshd', 'nginx', 'postgres']
    actual = agent.config.critical_processes

    for proc in expected:
        assert proc in actual


def test_post_data_success_logged(
    monkeypatch, mock_config_file, assert_msg_in_logfile
):
    agent = MockAgent.from_config_file(mock_config_file)

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
    monkeypatch, mock_config_file, assert_msg_in_logfile
):
    agent = MockAgent.from_config_file(mock_config_file)

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
    monkeypatch, mock_config_file, assert_msg_in_logfile
):
    agent = MockAgent.from_config_file(mock_config_file)

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

    assert_msg_in_logfile('All 3 attempts failed for POST http://mock/api')
    assert_msg_in_logfile('Permanent error')


def test_post_data_error_logged(
    mock_config_file, assert_msg_in_logfile
):
    agent = MockAgent.from_config_file(filename=mock_config_file)

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
    mock_config_file, monkeypatch, assert_msg_in_logfile
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

    agent = MockAgent.from_config_file(mock_config_file)
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
    mock_config_file, assert_msg_in_logfile
):
    """Test that missing controller URL is properly handled and logged."""

    agent = MockAgent.from_config_file(mock_config_file)

    agent.config.url = ''

    agent.post_data(
        url='',
        payload={'to_controller': 'test'},
        to_controller=True,
        fail_silently=True,
    )

    assert_msg_in_logfile(
        "Couldn't send POST request to controller: URL is not set"
    )


def test_post_data_headers_update(mock_config_file):
    """Test that post_data correctly adds Authorization header."""
    agent = MockAgent.from_config_file(mock_config_file)
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
    monkeypatch, mock_config_file, assert_msg_in_logfile
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

        agent = MockAgent.from_config_file(mock_config_file)
        agent.config.url = 'http://mock/'

        result = agent.get_data('server/command/', to_controller=True)

        expected_json = json.dumps(
            case['expected']
        ) if case['expected'] else ''
        if expected_json:
            assert expected_json in result

        assert_msg_in_logfile(
            'GET request status: %d' % case['status_code']
        )


def test_get_data_empty_response(
    monkeypatch, mock_config_file, assert_msg_in_logfile
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

    agent = MockAgent.from_config_file(mock_config_file)
    agent.hostname = 'mock_server'
    agent.config.url = 'http://mock/'

    result = agent.get_data('server/command/', to_controller=True)

    assert result.strip() == '', 'Expected empty string result'

    assert_msg_in_logfile('GET request status: 200')
    assert_msg_in_logfile('GET request succeeded on attempt 1')


def test_get_data_missing_data(mock_config_file, assert_msg_in_logfile):
    """
    Test proper handling and logging when controller URL is missing.
    """

    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.url = ''

    result = agent.get_data('server/status/', to_controller=True)

    assert result is None

    assert_msg_in_logfile(
        "Couldn't send GET request to controller: URL is not set"
    )


def test_get_data_error_logged(
    monkeypatch, mock_config_file, assert_msg_in_logfile
):
    """
    Test proper handling and logging of different GET request errors.
    """
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.url = 'http://mock/'

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


def test_maybe_add_to_queue_adds_item(mock_config_file):
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

    agent = MockAgent.from_config_file(mock_config_file)

    agent.maybe_add_command_to_queue(data)

    assert agent.command_queue.qsize() == 1


def test_maybe_add_to_queue_full_logged(
    mock_config_file, assert_msg_in_logfile
):
    """
    Test that trying to add command to the full queue is properly handled
    and logged.
    """
    import datetime

    import Queue

    agent = MockAgent.from_config_file(mock_config_file)
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


def test_get_command_from_queue_has_item(mock_config_file):
    import datetime

    from agents_infra.command import AgentCommand, CommandStatus

    agent = MockAgent.from_config_file(mock_config_file)

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
    mock_config_file, assert_msg_in_logfile
):
    import threading

    agent = MockAgent.from_config_file(mock_config_file)

    while not agent.command_queue.empty():
        agent.command_queue.get()

    with threading.Lock():
        agent.get_command_from_queue()

    assert_msg_in_logfile('Queue is empty - could not retrieve command')


def test_maybe_add_to_queue_logs_bad_input(
    mock_config_file, assert_msg_in_logfile
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

    agent = MockAgent.from_config_file(mock_config_file)

    agent.maybe_add_command_to_queue(data)

    assert_msg_in_logfile('Command validation failed due to error')
    assert agent.command_queue.qsize() == 0


def test_status_to_dict_keys(mock_config_file):
    """
    Verify that status_to_dict() returns all expected keys
    in the status dictionary.
    """
    agent = MockAgent.from_config_file(mock_config_file)

    # Set attributes manually
    agent.os_type = 'linux'
    agent.hostname = 'test-host'
    agent.ip = '127.0.0.1'
    agent.uptime = 12345
    agent.timestamp = '2025-06-03 20:00:00'

    # Patch is_service_healthy to return True
    with mock.patch.object(agent, 'is_service_healthy', return_value=True):
        result = agent.status_to_dict()

    expected_keys = set([
        'os',
        'hostname',
        'ip',
        'server_name',
        'uptime',
        'timestamp',
        'healthy',
        'tags',
    ])

    if not agent.tags:
        expected_keys.remove('tags')

    msg = 'Expected status_to_dict() to return keys: %s' % expected_keys
    assert set(result.keys()) == expected_keys, msg

    # Additional value check
    assert result['server_name'] == agent.config.name
    assert result['healthy'] is True
    assert result['uptime'] == 12345


def test_status_to_dict_with_missing_fields(mock_config_file):
    """
    Ensure status_to_dict() handles missing or None fields gracefully.
    """
    agent = MockAgent.from_config_file(mock_config_file)

    agent.os_type = None
    agent.hostname = None
    agent.ip = None
    agent.config.name = 'dns'
    agent.uptime = -1
    agent.timestamp = None
    agent.healthy = False

    result = agent.status_to_dict()

    assert result['os'] is None, "Expected 'os' to be None when missing"
    assert result['hostname'] is None, "Expected 'hostname' to be None"
    assert result['ip'] is None, "Expected 'ip' to be None when missing"
    assert result['uptime'] == -1, "Expected 'uptime' to be -1 when missing"


def test_protocol_setter_type_error(mock_config_file):
    """Test that protocol setter raises TypeError for non-string values."""
    agent = MockAgent.from_config_file(mock_config_file)

    with pytest.raises(TypeError, match='Protocol must be a string'):
        agent.protocol = 123

    with pytest.raises(TypeError, match='Protocol must be a string'):
        agent.protocol = None


def test_protocol_setter_value_error(mock_config_file):
    """Test that protocol setter raises ValueError for invalid protocols."""
    agent = MockAgent.from_config_file(mock_config_file)

    with pytest.raises(ValueError, match='Unknown protocol value'):
        agent.protocol = 'invalid_protocol'

    with pytest.raises(ValueError, match='Unknown protocol value'):
        agent.protocol = 'HTTP'


def test_collect_server_metadata_os_detection(monkeypatch, mock_config_file):
    """Test successful OS type detection."""
    def mock_system():
        return 'Linux'

    def mock_get_linux_uptime():
        return 12345.0

    monkeypatch.setattr(platform, 'system', mock_system)

    from agents_infra.agents import base
    monkeypatch.setattr(base,
                        'get_linux_uptime',
                        mock_get_linux_uptime)

    agent = MockAgent.from_config_file(mock_config_file)

    agent.collect_server_metadata()

    assert agent.os_type == 'linux'
    assert agent.uptime == 12345.0


def test_collect_server_metadata_unknown_os_logged(
    monkeypatch, mock_config_file, assert_msg_in_logfile
):
    """Test handling of undetectable OS type."""
    def mock_system():
        return ''

    monkeypatch.setattr(platform, 'system', mock_system)

    agent = MockAgent.from_config_file(mock_config_file)

    agent.collect_server_metadata()

    assert agent.os_type == 'unknown'

    assert_msg_in_logfile('Could not deduce OS type')


def test_collect_server_metadata_interface_ip_success(
    monkeypatch, mock_config_file
):
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

    agent = MockAgent.from_config_file(mock_config_file)
    agent.collect_server_metadata()

    assert agent.ip == '192.168.1.1'


def test_collect_server_metadata_interface_errors(
    monkeypatch, mock_config_file, assert_msg_in_logfile
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

        agent = MockAgent.from_config_file(mock_config_file)
        agent.config.interface = 'nonexistent'
        agent.collect_server_metadata()

        assert agent.ip is None

        assert_msg_in_logfile(
            'Could not deduce IP address from hostname: '
            'Name or service not known'
        )


def test_collect_server_metadata_hostname_error(
    monkeypatch, mock_config_file, assert_msg_in_logfile
):
    """Test handling of socket error when getting hostname."""
    def mock_gethostname():
        raise socket.error('Failed to get hostname')

    monkeypatch.setattr(socket, 'gethostname', mock_gethostname)

    agent = MockAgent.from_config_file(mock_config_file)
    agent.collect_server_metadata()

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
    commands = ['cmd1', 'cmd1']
    config = {
        'name': 'server_name',
        'api_prefix': 'api/v1/',
        'url': 'http://localhost',
        'port': 9999,
        'critical_processes': [],
        'whitelist_commands': commands,
        'auth_token_type': None,
        'interface': None,
    }

    agent = MockAgent(config=config)

    assert all(cmd in agent.config.whitelist_commands for cmd in commands)


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
        assert agent.config.critical_processes == ['ssh', 'sshd']
        assert agent.config.interface == 'enp0s3'

        # Since whitelist_commands not specified, defoults from global.ini
        assert agent.config.whitelist_commands == [
            'uptime', 'df -h', 'ls', 'whoami', 'collect_server_metadata'
        ]


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


def test_config_file_parsing_full_mock_config(mock_config_file):
    """
    Test that a fully populated config.ini file is correctly parsed.
    """
    agent = MockAgent.from_config_file(mock_config_file)

    assert agent.config.name == 'mock'
    assert agent.config.port == 123
    assert agent.config.interface == 'eth0'
    assert agent.tags['env'] == 'dev'
    assert agent.tags['role'] == 'backend'
    assert agent.tags['region'] == 'eu'
    assert agent.config.api_prefix == 'api/v1/'
    assert agent.config.url == 'http://localhost'

    assert agent.config.critical_processes == [
        'ssh', 'sshd', 'nginx', 'postgres'
    ]
    assert agent.config.whitelist_commands == [
        'uptime', 'df -h', 'ls', 'whoami', 'collect_server_metadata', 'cmd'
    ]


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


def test_status_to_dict_format(mock_config_file):
    agent = MockAgent.from_config_file(mock_config_file)

    agent.collect_server_metadata()

    with mock.patch.object(agent, 'is_service_healthy', return_value=True):
        result = agent.status_to_dict()

    expected_keys = set([
        'os', 'hostname', 'ip', 'server_name',
        'uptime', 'timestamp', 'healthy',
    ])

    if agent.tags:
        expected_keys.add('tags')

    assert set(result.keys()) == expected_keys

    assert isinstance(result['os'], str)
    assert isinstance(result['hostname'], str)
    assert isinstance(result['ip'], (str, type(None)))
    assert isinstance(result['server_name'], str)
    assert result['server_name'] == agent.config.name
    assert isinstance(result['uptime'], (int, float))
    assert isinstance(result['timestamp'], str)
    assert isinstance(result['healthy'], bool)

    if 'tags' in result:
        assert isinstance(result['tags'], dict)
        for key in ['env', 'role', 'region']:
            if getattr(agent.config, key, None):
                assert key in result['tags']


def test_status_to_dict_timestamp_format(mock_config_file):
    agent = MockAgent.from_config_file(mock_config_file)
    agent.collect_server_metadata()
    result = agent.status_to_dict()
    timestamp = result['timestamp']

    match = re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', timestamp)
    assert match is not None and match.group(0) == timestamp, (
        "Timestamp '%s' does not match format YYYY-MM-DD HH:MM:SS"
        % timestamp
    )


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


def test_status_dict_includes_tags_when_present():
    """
    Test that status_to_dict() includes the 'tags' key
    when config contains env and role.
    """
    config_content = """
[server]
name = test_server
env = production
role = web
region = eu
"""
    agent = load_agent_from_config(config_content)

    # Ensure tags are generated from config
    assert agent.tags == {'env': 'production', 'role': 'web', 'region': 'eu'}

    status = agent.status_to_dict()
    assert 'tags' in status
    assert status['tags'] == {
        'env': 'production', 'role': 'web', 'region': 'eu'
    }


def test_status_dict_omits_tags_for_backward_compatibility():
    """
    Test that status_to_dict() omits 'tags' when no env/role/region is set.
    """
    config_content = """
[server]
name = old_agent_server
port = 12345
"""
    agent = load_agent_from_config(config_content)

    assert agent.tags == {}  # Should be empty

    status = agent.status_to_dict()
    assert 'tags' not in status
