import ConfigParser
import pytest

from ...utils.configtools import write_config_options


@pytest.fixture
def temp_config_path(tmpdir):
    """
    Creates a temporary .ini file with initial content for tests.
    """
    config_file = tmpdir.join('test_config.ini')
    config_file.write('[server]\nenv = dev\nrole = db\n')
    return str(config_file)


def _read_config(path):
    """
    Helper to read the current state of the config file.
    """
    config = ConfigParser.ConfigParser()
    config.read(path)
    return config


def test_updates_existing_value(temp_config_path):
    """
    Test that an existing value is correctly updated.
    """
    write_config_options(
        temp_config_path,
        'server',
        {'env': 'production'}
    )
    config = _read_config(temp_config_path)
    assert config.get('server', 'env') == 'production'


def test_adds_new_value(temp_config_path):
    """
    Test that a new key-value pair is added.
    """
    write_config_options(
        temp_config_path,
        'server',
        {'region': 'us-east'}
    )
    config = _read_config(temp_config_path)
    assert config.get('server', 'region') == 'us-east'
    assert config.get('server', 'role') == 'db'


def test_removes_option_on_empty_string(temp_config_path):
    """
    Test that an empty string removes an existing option.
    """
    write_config_options(
        temp_config_path,
        'server',
        {'role': ''}
    )
    config = _read_config(temp_config_path)
    assert not config.has_option('server', 'role')


def test_removes_option_on_none(temp_config_path):
    """
    Test that None removes an existing option.
    """
    write_config_options(
        temp_config_path,
        'server',
        {'role': None}
    )
    config = _read_config(temp_config_path)
    assert not config.has_option('server', 'role')


def test_creates_section_if_not_exists(temp_config_path):
    """
    Test that a new section is created if it does not exist.
    """
    write_config_options(
        temp_config_path,
        'new_section',
        {'key': 'value'}
    )
    config = _read_config(temp_config_path)
    assert config.has_section('new_section')
    assert config.get('new_section', 'key') == 'value'
