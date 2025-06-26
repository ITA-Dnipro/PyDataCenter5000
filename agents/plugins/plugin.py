import types
from typing import Callable

from ..exceptions import PluginValidationError


def _validate_module(module):
    if (
        not hasattr(module, 'execute')
        or not isinstance(module.execute, Callable)
    ):
        raise PluginValidationError('Plugin must contain execute callable')

    try:
        result = module.execute()
    except TypeError:
        raise PluginValidationError(
            'execute only supports optional arguments'
        )

    if not isinstance(result, dict):
        raise PluginValidationError(
            'execute callable must return a dict, not %s' % type(result)
        )

    return module


class Plugin(object):
    def __init__(self, module):
        self.module = _validate_module(module)

    def __call__(self):
        return self.module.execute()


def register_plugin(func):
    """Allows to dynamically register instance methods."""
    def wrapped(obj):
        setattr(obj, func.__name__, types.MethodType(func, None, obj))
        return obj
    return wrapped
