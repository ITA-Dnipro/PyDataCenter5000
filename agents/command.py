import attr
from dateutil import parser
from singledispatch import singledispatchmethod


class Command(object):
    pass


@attr.attributes
class LinuxCommand(Command):
    shell = attr.attr(validator=attr.validators.instance_of(str))


@attr.attributes
class ProcessCheckCommand(Command):
    process = attr.attr(validator=attr.validators.instance_of(str))


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

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


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
