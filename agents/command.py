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
    pass


@attr.attributes
class LinuxCommand(Command):
    shell = attr.attr(validator=attr.validators.instance_of(basestring))

    def __str__(self):
        return 'Linux shell command: %s' % self.shell


@attr.attributes
class CheckServiceCommand(Command):
    service = attr.attr(validator=attr.validators.instance_of(basestring))


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
    cmd, input=None, timeout=None, encoding='utf-8', **kwargs
):
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
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
