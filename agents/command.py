import subprocess

import attr
from dateutil import parser
from singledispatch import singledispatchmethod


class ProcessStatus(object):
    ACTIVE = 'active'
    ENABLED = 'enabled'
    FAILED = 'failed'


class Command(object):
    pass


@attr.attributes
class LinuxCommand(Command):
    shell = attr.attr(validator=attr.validators.instance_of(basestring))

    def __str__(self):
        return 'Linux shell command: %s' % self.shell


@attr.attributes
class CheckSystemProcessCommand(Command):
    process = attr.attr(validator=attr.validators.instance_of(basestring))


COMMAND_TYPE_MAP = {
    'linux': LinuxCommand,
    'process_check': CheckSystemProcessCommand,
}


@attr.attributes
class CommandHistory(object):
    """Helper class used to validate command fields."""
    command = attr.attr(validator=attr.validators.instance_of(Command))

    hostname = attr.attr(validator=attr.validators.instance_of(basestring))
    status = attr.attr(validator=attr.validators.instance_of(basestring))
    timestamp = attr.attr(
        validator=lambda instance, attribute, value: parser.parse(value)
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

        return cls(command=command, **data)


def execute_shell_command(
    cmd, input=None, timeout=None, encoding='utf-8', **kwargs
):
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
    )

    stdout, stderr = proc.communicate(input=input)
    if encoding:
        stdout, stderr = stdout.decode(encoding), stderr.decode(encoding)

    return stdout, stderr


def check_system_process_status(proc, status=ProcessStatus.ACTIVE, **kwargs):
    stdout, stderr = execute_shell_command(
        ['systemctl', '-'.join('is', status), proc], **kwargs
    )


class CommandDispatcher(object):
    @singledispatchmethod
    def dispatch(self, command, **kwargs):
        pass

    @dispatch.register(LinuxCommand)
    def _(self, command, **kwargs):
        return execute_shell_command(command.shell, **kwargs)

    @dispatch.register(CheckSystemProcessCommand)
    def _(self, command, status=ProcessStatus.ACTIVE, **kwargs):
        return check_system_process_status(command.proc, status)
