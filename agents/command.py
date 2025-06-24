import abc
import subprocess
from enum import Enum

import attr
from dateutil import parser
from singledispatch import singledispatchmethod

from .exceptions import BadProcessReturnCode


class ProcessStatus(Enum):
    ACTIVE = 'active'
    ENABLED = 'enabled'
    FAILED = 'failed'


class CommandStatus(Enum):
    PENDING = 'pending'
    DONE = 'done'
    FAILED = 'failed'


class Command(object):
    """Base class for all commands."""
    __metaclass__ = abc.ABCMeta

    @property
    @abc.abstractmethod
    def tag(self):
        pass


@attr.attributes
class LinuxCommand(Command):
    """Linux shell command."""
    shell = attr.attr(validator=attr.validators.instance_of(basestring))

    def __str__(self):
        return 'Linux shell command: %s' % self.shell

    @property
    def tag(self):
        return self.shell


@attr.attributes
class CheckServiceCommand(Command):
    """Command for check the status of a system service."""
    service = attr.attr(validator=attr.validators.instance_of(basestring))

    @property
    def tag(self):
        return '-'.join([self.service, 'service', 'check'])


COMMAND_TYPE_MAP = {
    'linux': LinuxCommand,
    'service_check': CheckServiceCommand,
}


@attr.attributes
class CommandHistory(object):
    """Helper class used to validate command fields."""
    command = attr.attr(validator=attr.validators.instance_of(Command))

    hostname = attr.attr(validator=attr.validators.instance_of(basestring))
    timestamp = attr.attr(
        validator=lambda instance, attribute, value: parser.parse(value)
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

        command_factory = COMMAND_TYPE_MAP.get(command_type)
        if not command_factory:
            raise ValueError(
                'Unknown command type: %s' % str(command_factory)
            )

        params = data.pop('params', None)
        if params:
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


def check_service_status(proc, status=ProcessStatus.ACTIVE, **kwargs):
    """
    Check status of system process.

    Parameters:
        proc (str): Process name.
        status (ProcessStatus): Process status (ACTIVE, ENABLED, or FAILEd).
            Default is ACTIVE.

    Returns:
        tuple: Whether process has requested status, stderr.
    """
    stdout, stderr = execute_shell_command(
        ['systemctl', '-'.join('is', status.value), proc], **kwargs
    )
    return status in stdout, stderr


class CommandDispatcher(object):
    """
    Class responsible for dispatching command execution via an appropriate
    utility function.
    """
    @singledispatchmethod
    def dispatch(self, command, **kwargs):
        pass

    @dispatch.register(LinuxCommand)
    def _(self, command, **kwargs):
        return execute_shell_command(command.shell, **kwargs)

    @dispatch.register(CheckServiceCommand)
    def _(self, command, status=ProcessStatus.ACTIVE, **kwargs):
        return check_service_status(command.proc, status)
