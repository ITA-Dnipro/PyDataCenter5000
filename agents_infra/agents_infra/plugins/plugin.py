import functools
import inspect
import types
from collections import Callable

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
    Wrapper class for plugin modules. Responsible for plugin creation,
    validation, and execution.

    Attributes:
        callable (Callable): Plugin's callable.
        name (str): Plugin name by which it will be registered within a
            class.
        category (str): Plugin category. If not provided, defaults to
            'unknown'.
        enabled (bool): Whether the plugin is enabled. If False, the plugin
            is ignored by `aggregate_reports`.
        built_in (bool): Whether the plugin is protected from deletion.
    """
    def __init__(
        self, callable, name, category=None, enabled=True, built_in=False
    ):
        self.callable = callable
        self.name = name

        self.category = category or 'unknown'

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
        return self.callable(parent, **kwargs)


def register_plugin(source, obj, **kwargs):
    """Allows to dynamically register plugins as object's methods."""
    if isinstance(source, types.ModuleType):
        plugin = Plugin.from_module(source, **kwargs)
    elif isinstance(source, Callable):
        plugin = Plugin.from_callable(source, **kwargs)
    else:
        raise TypeError(
            'Plugin registration not supported for a source of type %s'
            % type(source)
        )

    if not hasattr(obj, plugin.name):
        setattr(obj, plugin.name, types.MethodType(plugin, None, obj))

        if obj._plugins is None:
            obj._plugins = []

        obj._plugins.append(plugin)


def unregister_plugin(name, obj):
    """
    Unregister plugin from class.

    Parameters:
        name (str): Plugin name.
        obj (Any): Target class.

    Raises:
        PluginProtectedError: If deletion of a built-in plugin is attempted.
    """
    plugin = getattr(obj, name, None)
    if not plugin:
        return

    if getattr(plugin, 'built_in', False):
        raise PluginProtectedError(
            'Plugin %s is protected from deletion' % name
        )

    delattr(obj, name)


def plugin(obj, name=None, category=None, enabled=True, built_in=False):
    """
    Decorator function to register plugins from callables upon creation.

    Usage:
        @plugin(<TargetClass>)
        def my_plugin(parent, ...):
            ...

        @plugin(<TargetClass>, ...):
        def another_plugin(parent, ...):
            ...

    Parameters:
        obj (type): Class to which the plugin will be registered as a
            method.
        name (str, optional): Name the plugin will be registered under.
            Defaults to function's name.
        category (str, optional): Plugin category. Defaults to 'unknown'.
        enabled (bool, optional): Whether the plugin is enabled upon
            registration. Defaults to True.
        built_in (bool, optional): Whether the plugin is protected from
            deletion. Defaults to False.

    Note:
        This decorator is meant for function-based plugins only. For
        module-based plugins use `register_plugin` dispatcher directly.
    """
    if not inspect.isclass(obj):
        raise TypeError('First argument to @plugin must be a class')

    def wrapper(func):
        @functools.wraps(func)
        def inner(*args, **kwargs):
            return func(*args, **kwargs)

        register_plugin(
            func,
            obj,
            name=name,
            category=category,
            enabled=enabled,
            built_in=built_in,
        )
        return inner
    return wrapper
