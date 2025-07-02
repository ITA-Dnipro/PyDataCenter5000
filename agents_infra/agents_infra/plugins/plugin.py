import inspect
import types
from collections import Callable

from singledispatch import singledispatch

from ..exceptions import PluginProtectedError, PluginValidationError


def _validate_plugin_module(module):
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

    return module


class Plugin(object):
    """
    Wrapper class for plugin modules. Responsible for plugin validation
    and execution.

    Attributes:
        module (Module): Plugin module containing the 'execute' callable.
    """
    def __init__(
        self, executable, name, category=None, enabled=True, built_in=False
    ):
        self.executable = executable
        self.name = name

        self.category = category or 'unknown'

        self.is_plugin = True
        self.enabled = enabled  # By default, plugin is enabled.
        self.built_in = built_in

    @classmethod
    def from_module(cls, module, **kwargs):
        """Create plugin from a module with a valid 'execute' callable."""
        module = _validate_plugin_module(module)
        name = getattr(
            module, 'PLUGIN_NAME', module.__name__.split('.')[-1]
        )

        category = getattr(module, 'PLUGIN_CATEGORY', 'unknown')

        return cls(module.execute, name, category=category, **kwargs)

    @classmethod
    def from_callable(cls, func, name=None, category=None, **kwargs):
        """Create plugin from a callable."""
        if not isinstance(func, Callable):
            raise PluginValidationError(
                'Must pass a callable to "from_callable" factory'
            )

        return cls(
            func,
            name if name else func.__name__,
            category or 'unknown',
            **kwargs
        )

    def __call__(self, parent=None, **kwargs):
        return self.executable(parent, **kwargs)


@singledispatch
def register_plugin(source, obj, **kwargs):
    """Allows to dynamically register plugins as object's methods."""
    raise NotImplementedError(
        'Plugin registration not supported for a source of type %s'
        % type(source)
    )


@register_plugin.register(types.ModuleType)
def _(source, obj, **kwargs):
    plugin = Plugin.from_module(source, **kwargs)
    setattr(obj, plugin.name, types.MethodType(plugin, None, obj))


@register_plugin.register(Callable)
def _(source, obj, **kwargs):
    plugin = Plugin.from_callable(source, **kwargs)
    setattr(obj, plugin.name, types.MethodType(plugin, None, obj))


def unregister_plugin(name, obj):
    plugin = getattr(obj, name, None)
    if not plugin:
        return

    if getattr(plugin, 'built_in', False):
        raise PluginProtectedError(
            'Plugin %s is protected from deletion' % name
        )

    delattr(obj, name)
