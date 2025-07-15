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


def test_no_op_write_does_not_change_config(temp_config_path):
    """
    Test that writing an empty dict doesn't change the config file.
    """
    initial_content = _read_config(temp_config_path).items('server')

    write_config_options(
        temp_config_path,
        'server',
        {}
    )
    final_content = _read_config(temp_config_path).items('server')

    assert initial_content == final_content


def test_config_file_overwritten_atomically(temp_config_path):
    """
    Test that the config file is overwritten, not appended.
    """
    write_config_options(
        temp_config_path,
        'server',
        {'env': 'value1'}
    )
    first_write = _read_config(temp_config_path).get('server', 'env')

    write_config_options(
        temp_config_path,
        'server',
        {'env': 'value2'}
    )
    second_write = _read_config(temp_config_path).get('server', 'env')

    assert first_write == 'value1'
    assert second_write == 'value2'
    assert first_write != second_write


def test_creates_new_config_file_if_not_exists(tmpdir):
    """
    Test that a new config file is created if it doesn't exist.
    """
    new_config_path = tmpdir.join('new_config.ini')
    assert not new_config_path.check()

    write_config_options(
        str(new_config_path),
        'server',
        {'env': 'value'}
    )
    assert new_config_path.check()

    config = _read_config(str(new_config_path))
    assert config.has_section('server')
    assert config.get('server', 'env') == 'value'
