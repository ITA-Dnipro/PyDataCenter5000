import inspect
import types
from collections import Callable

from singledispatch import singledispatch

from ..exceptions import PluginValidationError


def _validate_module(module):
    if (
        not hasattr(module, 'execute')
        or not isinstance(module.execute, Callable)
    ):
        raise PluginValidationError('Plugin must contain execute callable')

    argspec = inspect.getargspec(module.execute)
    if (
        len(argspec.args) - (
            len(argspec.defaults) if argspec.defaults else 0
        ) > 0
    ):
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

    Attributes:
        module (Module): Plugin module containing the 'execute' callable.
    """
    def __init__(self, executable, name):
        self.executable = executable
        self.name = name

        self.enabled = True  # By default, plugin is enabled.

    @classmethod
    def from_module(cls, module):
        """Create plugin from a module with a valid 'execute' callable."""
        module = _validate_module(module)
        name = getattr(
            module, 'PLUGIN_NAME', module.__name__.split('.')[-1]
        )

        return cls(module.execute, name)

    @classmethod
    def from_callable(cls, func, name=None):
        """Create plugin from a callable."""
        if not isinstance(func, Callable):
            raise PluginValidationError(
                'Must pass a callable to "from_callable" factory'
            )

        return cls(func, name if name else func.__name__)

    def __call__(self, parent=None, **kwargs):
        return self.executable(parent, **kwargs)


@singledispatch
def register_plugin(source, obj):
    """Allows to dynamically register plugins as object's methods."""
    raise NotImplementedError(
        'Plugin registration not supported for a source of type %s'
        % type(source)
    )


@register_plugin.register(types.ModuleType)
def _(source, obj):
    plugin = Plugin.from_module(source)
    setattr(obj, plugin.name, types.MethodType(plugin, None, obj))


@register_plugin.register(Callable)
def _(source, obj):
    plugin = Plugin.from_callable(source)
    setattr(obj, plugin.name, types.MethodType(plugin, None, obj))
