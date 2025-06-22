import attr
from dateutil import parser
from singledispatch import singledispatchmethod


class Command(object):
    pass


@attr.attributes
class LinuxCommand(Command):
    shell = attr.attr(validator=attr.validators.instance_of(basestring))

    def __str__(self):
        return 'Linux shell command: %s' % self.shell


@attr.attributes
class ProcessCheckCommand(Command):
    process = attr.attr(validator=attr.validators.instance_of(basestring))


COMMAND_TYPE_MAP = {
    'linux': LinuxCommand,
    'process_check': ProcessCheckCommand,
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


class CommandDispatcher(object):
    @singledispatchmethod
    def dispatch(self, command, **kwargs):
        pass

    @dispatch.register(LinuxCommand)
    def _(self, command, **kwargs):
        pass

    @dispatch.register(ProcessCheckCommand)
    def _(self, command, **kwargs):
        pass
