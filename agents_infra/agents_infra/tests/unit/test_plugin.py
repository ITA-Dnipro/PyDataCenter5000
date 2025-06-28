import types

import pytest

from agents_infra.exceptions import PluginValidationError
from agents_infra.plugins.plugin import Plugin, _validate_plugin_module


@pytest.fixture
def dummy_module():
    return types.ModuleType('dummy_module')


def test_validate_plugin_module_success(dummy_module):
    """Test validation of properly implemented plugin module."""
    dummy_module.execute = lambda *args, **kwargs: {}
    assert _validate_plugin_module(dummy_module) is dummy_module


def test_validate_plugin_module_no_execute_error(dummy_module):
    """
    Test that the error is raised in the absence of an 'execute' callable
    in the plugin module.
    """
    with pytest.raises(
        PluginValidationError, match='Plugin must contain execute callable'
    ):
        _validate_plugin_module(dummy_module)


def test_validate_plugin_module_invalid_execute_type_error(dummy_module):
    """
    Test that the error is raised on invalid 'execute' callable in the
    plugin module.
    """
    dummy_module.execute = 'invalid'

    with pytest.raises(
        PluginValidationError, match='Plugin must contain execute callable'
    ):
        _validate_plugin_module(dummy_module)


def test_validate_plugin_module_invalid_execute_arguments_error(dummy_module):
    """
    Test that the error is raised on invalid 'execute' callable's arguments.
    """
    dummy_module.execute = lambda arg: None

    with pytest.raises(
        PluginValidationError,
        match='"execute" does not support required positional arguments',
    ):
        _validate_plugin_module(dummy_module)


def test_validate_plugin_module_invalid_execute_return_type_error(
    dummy_module
):
    """
    Test that the error is raised on invalid 'execute' callable's return
    type in the plugin module.
    """
    dummy_module.execute = lambda: None

    with pytest.raises(
        PluginValidationError,
        match='execute callable must return a dict, not %s' % type(None),
    ):
        _validate_plugin_module(dummy_module)


def test_plugin_creation_from_module(dummy_module):
    """Test that the plugin is properly created via from_module factory."""
    dummy_module.execute = lambda: {}
    dummy_module.PLUGIN_NAME = 'dummy_plugin'
    dummy_module.PLUGIN_CATEGORY = 'dummy_category'

    plugin = Plugin.from_module(dummy_module)

    assert plugin.name == 'dummy_plugin'
    assert plugin.category == 'dummy_category'

    assert plugin.is_plugin
    assert plugin.enabled


def test_plugin_creation_from_callable():
    """Test that the plugin is properly created via from_callable factory."""
    plugin = Plugin.from_callable(
        lambda: {}, name='dummy_plugin', category='dummy_category'
    )

    assert plugin.name == 'dummy_plugin'
    assert plugin.category == 'dummy_category'

    assert plugin.is_plugin
    assert plugin.enabled
