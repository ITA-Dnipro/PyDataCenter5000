import json
import logging
import os
import platform
import re
import socket
import tempfile
import time
import types

import ConfigParser
import mock
import psutil
import pytest
import urllib2
from agents_infra.agents.base import ServerAgent
from agents_infra.command import CommandHistory
from agents_infra.utils.communication import AgentCommunication
from agents_infra.utils.configtools import Config

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
        'controller_urls=http://localhost1,'
        'http://localhost2,'
        'http://localhost3\n'
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
                controller_urls=[
                    'http://localhost1',
                    'http://localhost2',
                    'http://localhost3'
                ],
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


class MockAgentCommunication(AgentCommunication):
    """
    A mock implementation of AgentCommunication for unit testing.
    """

    def __init__(self, controller_urls=None, healthy_urls=None):
        # Default values for testing
        if controller_urls is None:
            controller_urls = [
                'http://mock-controller1',
                'http://mock-controller2',
                'http://mock-controller3'
            ]

        # Define which URLs are considered healthy
        self.mock_healthy_urls = set(healthy_urls or controller_urls)

        super(MockAgentCommunication, self).__init__(
            auth_token='mock-token',
            post_data_fn=None,
            logger=logging.getLogger('mock-agent-comm'),
            controller_urls=controller_urls
        )

        self.last_success_time = 0

    def _ping_controller(self, url, api_key, timeout=3):
        """
        Simulate a health check.
        """
        return url in self.mock_healthy_urls

    def ensure_active_controller(self, api_key):
        """
        Override to disable revert and simplify testing logic.
        """
        if self._ping_controller(self.current_controller, api_key):
            return self.current_controller

        for url in self.controller_urls:
            if self._ping_controller(url, api_key):
                self._switch_controller(url)
                return url

        self.logger.error('No mock controller available.')
        return None

    def try_revert_primary_controller(self, api_key):
        """
        Override to simulate immediate revert logic.
        """
        primary = self.controller_urls[0]
        if primary in self.mock_healthy_urls:
            self._switch_controller(primary)
        return self.current_controller


@pytest.yield_fixture
def agent_with_temp_config():
    """
    Pytest fixture to create a MockAgent with a temporary config file.
    """
    agent = MockAgent(config={'name': 'tag_test_agent'})

    temp_config = tempfile.NamedTemporaryFile(mode='w', delete=False)
    config_path = temp_config.name
    temp_config.write('[server]\nenv = dev\n')
    temp_config.close()

    agent.config.path = config_path
    agent.tags = {'env': 'dev'}

    yield agent, config_path

    os.remove(config_path)


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
    agent.config.current_controller = 'http://mock-controller'

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

    agent.post_data('/api', {'test': 'data'})

    assert_msg_in_logfile('POST request status: 200')
    assert_msg_in_logfile(
        'POST request succeeded on attempt 1: %s' % b'{"message":"received"}'
    )


def test_post_data_retry(
    monkeypatch, mock_config_file, assert_msg_in_logfile
):
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.current_controller = 'http://mock-controller'
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
        '/endpoint', {'retry': 'test'}, max_retries=3, delay=0
    )

    assert_msg_in_logfile(
        'POST request succeeded on attempt 2: %s' % b'{"message":"received"}'
    )

    assert call_count['count'] == 2


def test_post_data_max_retries_fail(
    monkeypatch, mock_config_file, assert_msg_in_logfile
):
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.current_controller = 'http://mock-controller'

    monkeypatch.setattr(
        urllib2,
        'urlopen',
        lambda req, timeout=None: (
            _ for _ in ()
        ).throw(urllib2.URLError('Permanent error'))
    )

    with pytest.raises(RuntimeError, match='POST failed after 3 attempts'):
        agent.post_data(
            '/api',
            {'fail': True},
            max_retries=3,
            delay=0,
            fail_silently=False,
        )

    assert_msg_in_logfile('All 3 attempts failed. Data not sent.')
    assert_msg_in_logfile('Permanent error')


def test_post_data_error_logged(
    mock_config_file, assert_msg_in_logfile
):
    agent = MockAgent.from_config_file(filename=mock_config_file)
    agent.config.current_controller = 'http://mock-controller'

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
    agent.config.current_controller = 'http://mock/controller/'

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

    # Set controller's URL explicitly to be independent of changes
    # of default values in agent.py/
    agent = MockAgentCommunication()

    agent.controller_urls = []
    agent.current_controller = ''

    agent.post_data(
        url='',
        payload={'to_controller': 'test'},
        to_controller=True,
        fail_silently=True,
    )

    assert_msg_in_logfile(
        "Couldn't send POST request to controller: controller URL is not set"
    )


def test_config_file_whitelist_commands_extends_default():
    """Test that config whitelist_commands extends default list."""
    MockAgent.whitelist_commands = ['default_cmd1', 'default_cmd2']

    config_content = """
[server]
name = test_server
port = 12345

[controller]
whitelist_commands = config_cmd1,config_cmd2
"""
    agent = load_agent_from_config(config_content)

    assert 'default_cmd1' in agent.whitelist_commands
    assert 'default_cmd2' in agent.whitelist_commands
    assert 'config_cmd1' in agent.whitelist_commands
    assert 'config_cmd2' in agent.whitelist_commands

    MockAgent.whitelist_commands = None


def test_post_data_headers_update(mock_config_file):
    """Test that post_data correctly adds Authorization header."""
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.auth_token_type = 'Bearer'
    agent.config.current_controller = 'http://mock/api'
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
        agent.config.current_controller = 'http://mock/'

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
    agent.config.current_controller = 'http://mock/'

    result = agent.get_data('server/command/', to_controller=True)

    assert result.strip() == '', 'Expected empty string result'

    assert_msg_in_logfile('GET request status: 200')
    assert_msg_in_logfile('GET request succeeded on attempt 1')


def test_get_data_missing_data(mock_config_file, assert_msg_in_logfile):
    """
    Test proper handling and logging when controller URL is missing.
    """

    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.current_controller = ''

    result = agent.get_data('server/status/', to_controller=True)

    assert result is None

    assert_msg_in_logfile(
        "Couldn't send GET request to controller: controller URL is not set"
    )


def test_get_data_error_logged(
    monkeypatch, mock_config_file, assert_msg_in_logfile
):
    """
    Test proper handling and logging of different GET request errors.
    """
    agent = MockAgent.from_config_file(mock_config_file)
    agent.config.current_controller = 'http://mock/'

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
        'controller_urls': [
            'http://localhost1',
            'http://localhost2',
            'http://localhost3'
        ],
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
        'controller_urls': [
            'http://localhost1',
            'http://localhost2',
            'http://localhost3'
        ],
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
    assert agent.config.controller_urls == [
        'http://localhost1',
        'http://localhost2',
        'http://localhost3'
    ]

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
    agent.current_controller = 'http://mock/'
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
    agent.config.current_controller = 'http://mock/'
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
    agent.config.current_controller = 'http://mock/'
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
    agent.config.current_controller = 'http://mock/'
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
    agent.config.current_controller = 'http://mock/'
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


def test_ping_controller_success():
    """
    Test _ping_controller when the controller is healthy.
    Simulates connection and response from the controller.
    """
    agent = MockAgentCommunication()

    class MockResponse(object):
        def read(self):
            return json.dumps({'status': 'healthy'})

    mock_socket = mock.MagicMock()
    mock_socket.close = mock.MagicMock()

    with mock.patch('socket.create_connection', return_value=mock_socket):
        with mock.patch('urllib2.urlopen', return_value=MockResponse()):
            result = agent._ping_controller(
                'http://mock-controller1',
                api_key=None
            )

    assert result is True


def test_ping_controller_tcp_fail():
    """
    Test that _ping_controller returns False when
    TCP connection to the controller fails.
    """
    agent = MockAgentCommunication()
    with mock.patch(
            'socket.create_connection',
            side_effect=socket.error()
    ):
        with mock.patch(
            'urllib2.urlopen',
            side_effect=Exception('Should not be called')
        ):
            result = agent._ping_controller(
                'http://mock',
                api_key=None
            )
    assert result is False


def test_ping_controller_health_check_fail():
    """
    Test that _ping_controller returns False
    when the HTTP health check fails, even though
    the TCP connection succeeds.
    """
    agent = MockAgentCommunication()

    # TCP succeeds
    with mock.patch(
            'socket.create_connection',
            return_value=mock.Mock()
    ):
        # Health check fails
        def mock_urlopen(req, timeout=3):
            raise urllib2.HTTPError(
                req.get_full_url(),
                500,
                'Internal Server Error',
                hdrs=None,
                fp=None
            )

        with mock.patch(
                'urllib2.urlopen',
                side_effect=mock_urlopen
        ):
            result = agent._ping_controller(
                'http://mock',
                api_key=None
            )

    assert result is False


def test_find_healthy_controller_returns_first_healthy():
    agent = MockAgentCommunication()
    urls = [
        'http://mock-controller1',
        'http://mock-controller2',
        'http://mock-controller3'
    ]

    def mock_ping(url, api_key):
        return url == 'http://mock-controller2'

    agent._ping_controller = mock_ping

    result = agent._find_healthy_controller(urls, api_key=None)
    assert result == 'http://mock-controller2'


def test_switch_controller_sets_state_and_logs():
    agent = MockAgentCommunication()
    agent.current_controller = 'http://mock-controller2'
    agent.last_success_time = 0

    agent._switch_controller('http://mock-controller1')

    assert agent.current_controller == 'http://mock-controller1'
    assert agent.last_success_time > 0


def test_try_revert_primary_controller_success(monkeypatch):
    """
        Test that try_revert_primary_controller successfully
        reverts to the higher-priority (primary) controller
        if it becomes healthy.
    """

    fixed_time = 100000
    agent = MockAgentCommunication()
    agent.controller_urls = [
        'http://mock-controller1',
        'http://mock-controller2',
    ]
    agent.current_controller = 'http://mock-controller2'
    agent.last_success_time = fixed_time - 1000
    agent.revert_interval = 1

    def mock_ping(url, api_key):
        return url == 'http://mock-controller1'

    monkeypatch.setattr(agent, '_ping_controller', mock_ping)

    reverted = agent.try_revert_primary_controller(api_key=None)

    assert reverted == 'http://mock-controller1'
    assert agent.current_controller == 'http://mock-controller1'


def test_try_revert_primary_controller_fail_due_to_time():
    """
    Test that try_revert_primary_controller does not attempt
    to revert if the revert interval has not passed.
    """
    agent = MockAgentCommunication()
    agent.controller_urls = [
        'http://mock',
        'http://mock-controller2'
    ]
    agent.current_controller = 'http://mock-controller2'
    agent.last_success_time = time.time()
    agent.revert_interval = 1000  # big number

    reverted = agent.try_revert_primary_controller(api_key=None)

    assert reverted == 'http://mock-controller2'


def test_ensure_active_controller_switches_to_healthy():
    """
    Test that ensure_active_controller switches to
    the next healthy controller when the current
    controller is unresponsive.
    """
    agent = MockAgentCommunication()
    agent.controller_urls = [
        'http://mock-controller1',
        'http://mock-controller2'
    ]
    agent.current_controller = 'http://mock-controller1'

    with mock.patch.object(
            agent,
            'try_revert_primary_controller',
            return_value='http://mock-controller1'
    ):
        with mock.patch.object(
                agent,
                '_ping_controller',
                side_effect=lambda url,
                api_key: url == 'http://mock-controller2'
        ):
            result = agent.ensure_active_controller(api_key=None)

    assert result == 'http://mock-controller2'


def test_attempt_revert_to_primary_detects_change():
    agent = MockAgentCommunication()
    agent.current_controller = 'http://mock-controller2'

    def fake_try_revert(api_key):
        agent.current_controller = 'http://mock-controller1'
        return 'http://mock-controller1'

    with mock.patch.object(
            agent,
            'try_revert_primary_controller',
            fake_try_revert
    ):
        result = agent._attempt_revert_to_primary(
            api_key=None
        )

    assert result is True


def test_ensure_active_controller_success_current(monkeypatch):
    """
        Test that ensure_active_controller returns the current
        controller if it is healthy.
    """
    agent = MockAgentCommunication()
    agent.controller_urls = ['http://mock-controller1']
    agent.current_controller = 'http://mock-controller1'

    monkeypatch.setattr(agent, '_ping_controller', lambda url, api_key: True)

    result = agent.ensure_active_controller(api_key=None)
    assert result == 'http://mock-controller1'


def test_ensure_active_controller_fails_all():
    """
    Test that ensure_active_controller returns None when
    all controllers are unresponsive.
    """
    agent = MockAgentCommunication()
    agent.controller_urls = [
        'http://mock-controller1',
        'http://mock-controller2'
    ]

    agent.current_controller = 'http://mock-controller1'

    with mock.patch.object(
            agent,
            'try_revert_primary_controller',
            return_value='http://mock-controller1'
    ):
        with mock.patch.object(
                agent,
                '_ping_controller',
                return_value=False
        ):
            result = agent.ensure_active_controller(api_key=None)

    assert result is None


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
        'region': 'eu-central'
    }
    assert agent.tags == expected_tags, \
        ('All expected tags (env, role, region) '
         'should be correctly parsed from config.')


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
        'role': 'db'
    }
    assert agent.tags == expected_tags, \
        'Only explicitly defined tags should be parsed from config.'
    assert 'region' not in agent.tags,  \
        'Missing tags should not be present in the result.'


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
        'region': 'us-east'
    }
    assert agent.tags == expected_tags, \
        'Tags with empty values in config should be ignored during parsing.'
    assert 'role' not in agent.tags, \
        "The 'role' tag with an empty value should not be included."


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
        'role': 'web'
    }
    assert agent.tags == expected_tags, \
        ('Tag values should be normalized '
         'by stripping whitespace and lowercasing.')


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

    assert 'tags' in status, \
        ("The 'tags' key should be included in the status dict "
         'when tags are configured.')
    assert status['tags'] == {'env': 'production', 'role': 'web'}, \
        'The tags in the status dictionary should match the parsed tags.'


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

    assert agent.tags == {}, \
        'Agent.tags should be empty if no tags are defined in the config.'
    assert 'tags' not in status, \
        ("The 'tags' key should be omitted in the status dict "
         'to ensure backward compatibility.')


@mock.patch('agents_infra.agents.base.maybe_log_message')
def test_set_tags_updates_config_and_reloads_state(
        mock_log,
        agent_with_temp_config
):
    """
    Test that set_tags correctly updates/adds tags and reloads agent state.
    """
    agent, config_path = agent_with_temp_config
    assert agent.tags == {'env': 'dev'}, \
        'Initial agent tags should be correctly parsed from config.'

    new_tags = {'env': 'production', 'role': 'web'}
    agent.set_tags(new_tags)

    mock_log.assert_any_call(
        'Tags updated successfully. Current tags are now: %s' % new_tags,
        logger=agent.logger,
        level=logging.INFO
    )
    assert agent.tags == new_tags, \
        "Agent's tags should match newly set tags after set_tags() and reload"

    config = ConfigParser.ConfigParser()
    config.read(config_path)
    assert config.get('server', 'env') == 'production', \
        "Config file 'env' tag should be updated."
    assert config.get('server', 'role') == 'web', \
        "Config file 'role' tag should be added."


@mock.patch('agents_infra.agents.base.maybe_log_message')
def test_set_tags_removes_tag_with_empty_string(
        mock_log,
        agent_with_temp_config
):
    """
    Test that set_tags removes a tag when an empty string value is provided.
    """
    agent, config_path = agent_with_temp_config
    assert 'env' in agent.tags, \
        "Initial state should contain 'env' tag."

    tags_to_remove = {'env': ''}
    agent.set_tags(tags_to_remove)

    mock_log.assert_any_call(
        'Tags updated successfully. Current tags are now: %s' % {},
        logger=agent.logger,
        level=logging.INFO
    )
    assert 'env' not in agent.tags, \
        "Tag 'env' should be removed from agent's state."

    config = ConfigParser.ConfigParser()
    config.read(config_path)
    assert not config.has_option('server', 'env'), \
        "Tag 'env' should be removed from config file."


@mock.patch('agents_infra.agents.base.maybe_log_message')
def test_set_tags_handles_empty_dict(
        mock_log,
        agent_with_temp_config
):
    """
    Test that set_tags performs a no-op when an empty dict is passed.
    """
    agent, config_path = agent_with_temp_config
    initial_tags = agent.tags.copy()

    agent.set_tags({})
    mock_log.assert_called_with(
        "Command 'set_tags' received empty tags. No action taken.",
        logger=agent.logger,
        level=logging.WARNING
    )
    assert agent.tags == initial_tags, \
        'Tags should not change when an empty dict is passed'


@mock.patch('agents_infra.agents.base.maybe_log_message')
def test_set_tags_with_invalid_type(
        mock_log,
        agent_with_temp_config
):
    """
    Test that passing a non-dict to set_tags is handled correctly.
    """
    agent, config_path = agent_with_temp_config

    agent.set_tags('this is not a dictionary')

    mock_log.assert_called_with(
        "Command 'set_tags' failed: expected a dictionary of tags.",
        logger=agent.logger,
        level=logging.ERROR
    )
