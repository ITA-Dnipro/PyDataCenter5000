import mock
import pytest

from agents.command import (COMMAND_REGISTRY, AgentCommand, CommandHistory,
                            CommandStatus, LinuxCommand, dispatch_command,
                            execute_shell_command, register_command)
from agents.exceptions import BadProcessReturnCode


def test_linux_command_created():
    """Test proper creation of a linux command."""
    cmd = LinuxCommand(shell='cmd')
    assert cmd.shell == cmd.tag == 'cmd'


def test_agent_command_created():
    """Test proper creation of an agent command."""
    cmd = AgentCommand(
        method='agent_method',
        args=('arg1', 'arg2'),
        kwargs={'kwarg1': 1, 'kwarg2': 2}
    )

    assert cmd.method == cmd.tag == 'agent_method'
    assert cmd.args == ('arg1', 'arg2')
    assert cmd.kwargs == {'kwarg1': 1, 'kwarg2': 2}


def test_command_registry_contains():
    """Test that command registry contains LinuxCommand and AgentCommand."""
    assert 'linux' in COMMAND_REGISTRY
    assert COMMAND_REGISTRY['linux'] is LinuxCommand
    assert 'agent' in COMMAND_REGISTRY
    assert COMMAND_REGISTRY['agent'] is AgentCommand


def test_command_history_valid_data():
    """Test that command history is properly instantiated."""
    data = {
        'type': 'linux',
        'params': {'shell': 'ls'},
        'hostname': 'test-server',
        'status': 'pending',
        'timestamp': '2025-06-03T18:25:35.418746Z',
        'result': 'ok',
        'id': 1,
    }

    command_history = CommandHistory.from_dict(data)

    assert command_history.command == LinuxCommand('ls')
    assert command_history.hostname == 'test-server'
    assert command_history.status == CommandStatus.PENDING
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
            'type': 'linux',
            'status': 'pending',
            'timestamp': '2025-06-03T18:25:35.418746Z',
        },
    ]

    for data in parameters:
        with pytest.raises((TypeError, ValueError)):
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


def test_execute_shell_command_success():
    """Test successful exection of shell command."""
    with mock.patch('subprocess.Popen') as mock_popen:
        mock_proc = mock.MagicMock()
        mock_proc.communicate.return_value = (u'hello\n', u'')
        mock_proc.returncode = 0

        mock_popen.return_value = mock_proc

        out, err = execute_shell_command(['echo', 'hello'])
        assert out == u'hello\n'
        assert err == u''


def test_execute_shell_command_raises_bad_return_code():
    """
    Test that bad input command is properly handled in execute_shell_command.
    """
    with mock.patch('subprocess.Popen') as mock_popen:
        mock_proc = mock.MagicMock()
        mock_proc.communicate.return_value = (u'', u'Unknown shell command\n')
        mock_proc.returncode = 1

        mock_popen.return_value = mock_proc

        with pytest.raises(
            BadProcessReturnCode,
            match='Shell command failed with return code 1'
        ):
            execute_shell_command(['bad command'])


def test_dispatch_command_success():
    """Test that commands are properly dispatched via dispatch_command."""
    mock_agent = mock.MagicMock()
    mock_agent.agent_method.return_value = 'agent output'

    cases = [
        (LinuxCommand(shell='cmd'), None, (u'linux output', u'')),
        (
            AgentCommand(
                method='agent_method', args=('arg',), kwargs={'kwargs': 1}
            ),
            mock_agent,
            'agent output',
        )
    ]

    with mock.patch(
        'agents.command.execute_shell_command'
    ) as mock_execute_shell_command:
        mock_execute_shell_command.return_value = (u'linux output', u'')

        for command, agent, expected in cases:
            result = dispatch_command(command, agent)
            assert result == expected
