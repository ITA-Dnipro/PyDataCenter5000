import abc
import datetime
import subprocess
from enum import Enum

import attr
from dateutil import parser
from singledispatch import singledispatch

from .exceptions import BadProcessReturnCode


class ProcessStatus(Enum):
    ACTIVE = 'active'
    ENABLED = 'enabled'
    FAILED = 'failed'


class CommandStatus(Enum):
    PENDING = 'pending'
    DONE = 'done'
    FAILED = 'failed'


COMMAND_REGISTRY = {}  # Dynamic command registry


def register_command(name):
    """
    Decorator function for flexible mapping of command names to
    corresponding classes.
    """
    def wrapped(cls):
        COMMAND_REGISTRY[name] = cls
        return cls
    return wrapped


class Command(object):
    """Base class for all commands."""
    __metaclass__ = abc.ABCMeta

    @property
    @abc.abstractmethod
    def tag(self):
        pass


@register_command('linux')
@attr.attributes
class LinuxCommand(Command):
    """Linux shell command."""
    shell = attr.attr(validator=attr.validators.instance_of(basestring))

    def __str__(self):
        return 'Linux shell command: %s' % self.shell

    @property
    def tag(self):
        return self.shell


@register_command('agent')
@attr.attributes
class AgentCommand(Command):
    """Command for executing agent's method."""
    method = attr.attr(validator=attr.validators.instance_of(basestring))
    args = attr.attr(default=lambda: ())
    kwargs = attr.attr(default=lambda: {})

    @property
    def tag(self):
        return self.method


@attr.attributes
class CommandHistory(object):
    """Helper class used to validate command fields."""
    command = attr.attr(validator=attr.validators.instance_of(Command))

    hostname = attr.attr(validator=attr.validators.instance_of(basestring))
    timestamp = attr.attr(
        validator=lambda instance, attribute, value: parser.parse(value),
    )
    status = attr.attr(
        validator=attr.validators.instance_of(CommandStatus),
        default=CommandStatus.PENDING,
    )
    result = attr.attr(default=None)

    id = attr.attr(default=None)

    notify_on_success = attr.attr(default=False)

    @classmethod
    def from_dict(cls, data):
        command_type = data.pop('type', None)
        if not command_type:
            raise ValueError('Must provide a valid command type')

        command_factory = COMMAND_REGISTRY.get(command_type)
        if not command_factory:
            raise ValueError(
                'Unknown command type: %s' % str(command_type)
            )

        params = data.pop('params', None)
        if not params:
            raise ValueError('Must provide valid command parameters')

        command = command_factory(**params)

        data['status'] = CommandStatus(data.get('status', 'pending'))

        return cls(command=command, **data)


def execute_shell_command(
    cmd, shell=False, input=None, encoding='utf-8', **kwargs
):
    """
    Execute Linux shell command.

    Parameters:
        cmd (Any): Shell command to execute.
        shell (bool, optional): Whether to execute command through shell.
            Default is False.
        input (str, optional): Data to send to command's standard input
            (stdin).
        encoding (str, optional): If specified, decode the output using
            this encoding.

    Returns:
        tuple: stdout, stderr

    Raises:
        BadProcessReturnCode: If shell command fails with return code
            different from 0.
    """
    # Always capture command output with PIPE.
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=shell,
        **kwargs
    )

    stdout, stderr = proc.communicate(input=input)

    if proc.returncode != 0:
        raise BadProcessReturnCode(
            'Shell command failed with return code %d' % proc.returncode
        )

    if encoding:
        stdout, stderr = stdout.decode(encoding), stderr.decode(encoding)

    return stdout, stderr


@singledispatch
def dispatch_command(command, agent, **kwargs):
    raise TypeError('Unknown command type: %s' % type(command))


@dispatch_command.register(LinuxCommand)
def _(command, agent, **kwargs):
    return execute_shell_command(command.shell, **kwargs)


@dispatch_command.register(AgentCommand)
def _(command, agent, **kwargs):
    method = getattr(agent, command.method, None)
    if not method:
        raise AttributeError('Agent does not have method %s' % command.method)

    args = command.args or []
    kwargs = command.kwargs or {}

    if command.method == 'set_tags':
        return method(kwargs)
    return method(*args, **kwargs)
