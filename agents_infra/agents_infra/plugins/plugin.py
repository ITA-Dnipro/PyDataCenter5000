import inspect
import types
from collections import Callable

from ..exceptions import PluginValidationError


def _validate_module(module):
    if (
        not hasattr(module, 'execute')
        or not isinstance(module.execute, Callable)
    ):
        raise PluginValidationError('Plugin must contain execute callable')

    argspec = inspect.getargspec(module.execute)
    if len(argspec.args) - len(argspec.defaults) > 0:
        raise PluginValidationError(
            '"execute" does not support required positional arguments'
        )

    result = module.execute()
    if not isinstance(result, dict):
        raise PluginValidationError(
            'execute callable must return a dict, not %s' % type(result)
        )

    return module


class Plugin(object):
    """
    Wrapper class for plugin modules. Responsible for plugin validation
    and execution.
    """
    def __init__(self, module):
        self.module = _validate_module(module)

    def __call__(self, parent):
        return self.module.execute()


def register_plugin(obj, module):
    """Allows to dynamically register plugins as instance methods."""
    plugin = Plugin(module)

    name = plugin.module.__name__.split('.')[-1]

    setattr(obj, name, types.MethodType(plugin, None, obj))
