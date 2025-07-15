import types

import mock
import pytest

from agents_infra.exceptions import PluginProtectedError, PluginValidationError
from agents_infra.plugins.plugin import (Plugin, _validate_plugin_module,
                                         register_plugin, unregister_plugin)


@pytest.fixture
def dummy_module():
    return types.ModuleType('dummy_module')


def test_validate_plugin_module_success(dummy_module):
    """Test validation of properly implemented plugin module."""
    dummy_module.execute = lambda parent, *args, **kwargs: {}
    assert _validate_plugin_module(dummy_module) is dummy_module


def test_validate_plugin_module_no_execute_error(dummy_module):
    """
    Test that the error is raised in the absence of an 'execute' callable
    in the plugin module.
    """
    with pytest.raises(
        PluginValidationError,
        match='Plugin must contain a valid "execute" callable'
    ):
        _validate_plugin_module(dummy_module)


def test_validate_plugin_module_invalid_execute_type_error(dummy_module):
    """
    Test that the error is raised on invalid 'execute' callable in the
    plugin module.
    """
    dummy_module.execute = 'invalid'

    with pytest.raises(
        PluginValidationError,
        match=(
            'Plugin can only be created from a valid callable, got %s'
            % type(dummy_module.execute)
        ),
    ):
        _validate_plugin_module(dummy_module)


def test_validate_plugin_module_invalid_execute_arguments_error(dummy_module):
    """
    Test that the error is raised on invalid 'execute' callable's arguments.
    """
    dummy_module.execute = lambda: None

    with pytest.raises(
        PluginValidationError,
        match=(
            'Plugin callable must have a required positional argument to be '
            'called by the parent'
        ),
    ):
        _validate_plugin_module(dummy_module)


def test_plugin_creation_from_module(dummy_module):
    """Test that the plugin is properly created via from_module factory."""
    dummy_module.execute = lambda parent: {}
    dummy_module.PLUGIN_NAME = 'dummy_plugin'
    dummy_module.PLUGIN_CATEGORY = 'dummy_category'

    plugin = Plugin.from_module(dummy_module)

    assert plugin.name == 'dummy_plugin'
    assert plugin.category == 'dummy_category'
    assert plugin.enabled


def test_plugin_creation_from_callable():
    """Test that the plugin is properly created via from_callable factory."""
    plugin = Plugin.from_callable(
        lambda parent: {}, name='dummy_plugin', category='dummy_category'
    )

    assert plugin.name == 'dummy_plugin'
    assert plugin.category == 'dummy_category'
    assert plugin.enabled


def test_plugin_call():
    """Test that calling the plugin works as expected."""
    status = {'called': 0}

    def func(parent):
        status['called'] += 1

    plugin = Plugin.from_callable(func, name='mock_callable')
    plugin()

    assert status['called'] == 1


def test_register_plugin_from_module_success(dummy_module):
    """Test that plugin is properly registered from module for object."""
    class DummyObject(object):
        pass

    dummy_module.execute = lambda parent: {}

    register_plugin(dummy_module, DummyObject)

    assert hasattr(DummyObject, 'dummy_module')


def test_register_plugin_from_callable_success():
    """Test that plugin is properly registered from callable for object."""
    class DummyObject(object):
        pass

    def dummy_callable(parent):
        return {}

    register_plugin(dummy_callable, DummyObject)

    assert hasattr(DummyObject, 'dummy_callable')


def test_register_plugin_invalid_type_raises():
    """Test that plugin registration with invalid type raises an error."""
    class DummyObject(object):
        pass

    with pytest.raises(
        TypeError,
        match='Plugin registration not supported for a source of type %s'
        % str
    ):
        register_plugin('invalid', DummyObject)


def test_unregister_plugin_success():
    """"""
    class DummyObject(object):
        _plugins = None

    def dummy_plugin(parent):
        pass

    register_plugin(dummy_plugin, DummyObject, built_in=False)
    assert (
        hasattr(DummyObject, 'dummy_plugin')
        and len(DummyObject._plugins) == 1
        and all(
            name == 'dummy_plugin' for name in DummyObject._plugins
        )
    )

    unregister_plugin('dummy_plugin', DummyObject)
    assert not hasattr(DummyObject, 'dummy_plugin')
    assert len(DummyObject._plugins) == 0


def test_unregister_plugin_raises_protected_error():
    """Test that built-in plugins are protected from being unregistered."""
    class DummyObject(object):
        pass

    def dummy_plugin(parent):
        return {'status': 'ok'}

    register_plugin(dummy_plugin, DummyObject, built_in=True)

    with pytest.raises(
        PluginProtectedError,
        match='Plugin dummy_plugin is protected from deletion',
    ):
        unregister_plugin('dummy_plugin', DummyObject)
