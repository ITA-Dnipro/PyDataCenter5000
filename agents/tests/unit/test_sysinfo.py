import datetime
import socket

import mock
import psutil
import pytest

from agents.utils.sysinfo import (generate_report, get_cpu_usage,
                                  get_disk_usage, get_ip_from_interface,
                                  get_linux_uptime, get_load_average,
                                  get_ram_usage)

# TESTS FOR get_ip_from_interface()


@mock.patch('psutil.net_if_addrs')
def test_valid_interface_with_ipv4(mock_addrs):
    mock_addrs.return_value = {
        'eth0': [
            mock.Mock(address='127.0.0.1', family=socket.AF_INET),
            mock.Mock(address='192.168.0.10', family=socket.AF_INET)
        ]
    }

    result = get_ip_from_interface('eth0')
    assert result == '192.168.0.10', (
        'Expected to return valid non-loopback IPv4 address'
    )


@mock.patch('psutil.net_if_addrs')
def test_interface_with_only_loopback(mock_addrs):
    mock_addrs.return_value = {
        'eth0': [
            mock.Mock(address='127.0.0.1', family=socket.AF_INET)
        ]
    }

    result = get_ip_from_interface('eth0')
    assert result is None, (
        'Expected None when only loopback address is present'
        )


@mock.patch('psutil.net_if_addrs')
def test_interface_with_no_ipv4(mock_addrs):
    mock_addrs.return_value = {
        'eth0': [
            mock.Mock(address='::1', family=socket.AF_INET6)
        ]
    }

    result = get_ip_from_interface('eth0')
    assert result is None, 'Expected None when interface has no IPv4 address'


@mock.patch('psutil.net_if_addrs')
def test_interface_not_found(mock_addrs):
    mock_addrs.return_value = {
        'lo': [
            mock.Mock(address='127.0.0.1', family=socket.AF_INET)
        ]
    }

    result = get_ip_from_interface('eth1')
    assert result is None, 'Expected None when interface does not exist'


@mock.patch('psutil.net_if_addrs')
def test_multiple_addresses_prioritize_ipv4(mock_addrs):
    """Test that the first non-loopback IPv4 is returned among mixed types."""
    mock_addrs.return_value = {
        'eth0': [
            mock.Mock(address='127.0.0.1', family=socket.AF_INET),
            mock.Mock(address='192.168.1.100', family=socket.AF_INET),
            mock.Mock(address='fe80::1', family=socket.AF_INET6),
        ]
    }

    result = get_ip_from_interface('eth0')
    assert result == '192.168.1.100', (
        'Expected to skip loopback and return valid IPv4 address'
    )


# TESTS FOR get_linux_uptime()

@mock.patch('__builtin__.open')
def test_get_linux_uptime_valid(mock_open):
    mock_file = mock.Mock()
    mock_file.readline.return_value = '12345.67 54321.00\n'
    mock_open.return_value.__enter__.return_value = mock_file

    result = get_linux_uptime()
    assert isinstance(result, float), 'Expected uptime to be float'
    assert result == 12345.67, 'Expected parsed uptime value to be 12345.67'


@mock.patch('__builtin__.open')
def test_get_linux_uptime_malformed_data(mock_open):
    mock_file = mock.Mock()
    mock_file.readline.return_value = 'not_a_number something_else\n'
    mock_open.return_value.__enter__.return_value = mock_file

    with pytest.raises(ValueError):
        get_linux_uptime()


@mock.patch('__builtin__.open', side_effect=IOError('Cannot open file'))
def test_get_linux_uptime_file_missing(mock_open):
    with pytest.raises(IOError):
        get_linux_uptime()


# TESTS FOR get_ram_usage()

def test_get_ram_usage_success():
    with mock.patch('psutil.virtual_memory') as mock_vm:
        mock_vm.return_value.percent = 42.5
        logger = mock.Mock()
        usage = get_ram_usage(logger)
        assert usage == 42.5, 'Expected RAM usage to be 42.5'


def test_get_ram_usage_handles_psutil_error_and_logs():
    logger = mock.Mock()

    def raise_error():
        raise psutil.Error('Mocked psutil error')

    with mock.patch('psutil.virtual_memory', side_effect=raise_error):
        with mock.patch('agents.utils.sysinfo.maybe_log_message') as mock_log:
            usage = get_ram_usage(logger)
            assert usage == -1.0, 'Expected RAM usage to be -1.0 on error'
            mock_log.assert_called_once()
            log_args, log_kwargs = mock_log.call_args
            assert 'Error getting RAM usage' in log_args[0], (
                'Log message should mention error'
            )
            assert log_kwargs.get('logger') == logger, (
                'Logger should be passed to maybe_log_message'
            )


# TESTS FOR get_cpu_usage()

def test_get_cpu_usage_success():
    """Test that CPU usage is returned correctly."""
    with mock.patch('psutil.cpu_percent') as mock_cpu:
        mock_cpu.return_value = 37.0
        logger = mock.Mock()
        usage = get_cpu_usage(logger, interval=1)
        assert usage == 37.0, 'Expected CPU usage to be 37.0'


def test_get_cpu_usage_psutil_error_logged():
    """Test that psutil.Error is handled and logged properly."""
    logger = mock.Mock()

    def raise_error(*args, **kwargs):
        raise psutil.Error('Mocked error')

    with mock.patch('psutil.cpu_percent', side_effect=raise_error):
        with mock.patch('agents.utils.sysinfo.maybe_log_message') as mock_log:
            usage = get_cpu_usage(logger)
            assert usage == -1.0, 'Expected -1.0 on psutil error'
            mock_log.assert_called_once()
            log_args, log_kwargs = mock_log.call_args
            assert 'Error getting CPU usage' in log_args[0], (
                'Expected error log message'
            )
            assert log_kwargs.get('logger') == logger, (
                'Expected logger to be passed to maybe_log_message'
            )


def test_get_cpu_usage_value_error_logged():
    """Test that ValueError is handled and logged properly."""
    logger = mock.Mock()

    def raise_value_error(*args, **kwargs):
        raise ValueError('Invalid interval')

    with mock.patch('psutil.cpu_percent', side_effect=raise_value_error):
        with mock.patch('agents.utils.sysinfo.maybe_log_message') as mock_log:
            usage = get_cpu_usage(logger)
            assert usage == -1.0, 'Expected -1.0 on ValueError'
            mock_log.assert_called_once()
            log_args, log_kwargs = mock_log.call_args
            assert 'Error getting CPU usage' in log_args[0], (
                'Expected ValueError to be logged'
            )
            assert log_kwargs.get('logger') == logger, (
                'Expected logger to be passed to maybe_log_message'
            )


# TESTS FOR get_load_average()

def test_get_load_average_success():
    """Test that load average is returned correctly."""
    logger = mock.Mock()
    with mock.patch('os.getloadavg') as mock_getloadavg:
        mock_getloadavg.return_value = (0.75, 0.5, 0.25)
        result = get_load_average(logger)
        assert result == 0.75, 'Expected load average to be 0.75'


def test_get_load_average_oserror_logged():
    """Test that OSError is handled and logged properly."""
    logger = mock.Mock()

    def raise_oserror(*args, **kwargs):
        raise OSError('Mocked OSError')

    with mock.patch('os.getloadavg', side_effect=raise_oserror):
        with mock.patch('agents.utils.sysinfo.maybe_log_message') as mock_log:
            result = get_load_average(logger)
            assert result == -1.0, 'Expected -1.0 on OSError'
            mock_log.assert_called_once()
            log_args, log_kwargs = mock_log.call_args
            assert 'Error getting load average' in log_args[0], (
                'Expected OSError log message'
            )
            assert log_kwargs.get('logger') == logger, (
                'Expected logger to be passed to maybe_log_message'
            )


def test_get_load_average_attributeerror_logged():
    """Test that AttributeError is handled and logged properly."""
    logger = mock.Mock()

    def raise_attribute_error(*args, **kwargs):
        raise AttributeError('Mocked AttributeError')

    with mock.patch('os.getloadavg', side_effect=raise_attribute_error):
        with mock.patch('agents.utils.sysinfo.maybe_log_message') as mock_log:
            result = get_load_average(logger)
            assert result == -1.0, 'Expected -1.0 on AttributeError'
            mock_log.assert_called_once()
            log_args, log_kwargs = mock_log.call_args
            assert 'Error getting load average' in log_args[0], (
                'Expected AttributeError log message'
            )
            assert log_kwargs.get('logger') == logger, (
                'Expected logger to be passed to maybe_log_message'
            )


# TESTS FOR get_disk_usage()

def test_get_disk_usage_success():
    """Test that disk usage is returned correctly."""
    logger = mock.Mock()
    mock_usage = mock.Mock()
    mock_usage.percent = 55.5

    with mock.patch('psutil.disk_usage', return_value=mock_usage):
        result = get_disk_usage(logger)
        assert result == 55.5, 'Expected disk usage to be 55.5%'


def test_get_disk_usage_error_logged():
    """Test that psutil.Error is handled and logged properly."""
    logger = mock.Mock()

    def raise_psutil_error(*args, **kwargs):
        raise psutil.Error('Mocked psutil error')

    with mock.patch('psutil.disk_usage', side_effect=raise_psutil_error):
        with mock.patch('agents.utils.sysinfo.maybe_log_message') as mock_log:
            result = get_disk_usage(logger)
            assert result == -1.0, 'Expected -1.0 on psutil error'
            mock_log.assert_called_once()
            log_args, log_kwargs = mock_log.call_args
            assert 'Error getting disk usage' in log_args[0], (
                'Expected error log message for disk usage'
            )
            assert log_kwargs.get('logger') == logger, (
                'Expected logger to be passed to maybe_log_message'
            )


# TESTS FOR generate_report()

def test_generate_report_success():
    """Test that generate_report returns all expected keys with valid data."""
    logger = mock.Mock()

    with mock.patch('agents.utils.sysinfo.get_cpu_usage', return_value=42.0):
        with mock.patch(
            'agents.utils.sysinfo.get_ram_usage', return_value=65.5
        ):
            with mock.patch(
                'agents.utils.sysinfo.get_disk_usage', return_value=78.2
            ):
                with mock.patch(
                    'agents.utils.sysinfo.get_load_average', return_value=0.98
                ):
                    with mock.patch(
                        'agents.utils.sysinfo.datetime'
                    ) as mock_datetime:

                        mock_datetime.datetime.now.return_value = (
                            datetime.datetime(2025, 1, 1, 12, 0, 0)
                        )
                        report = generate_report(logger)

                        assert report['cpu'] == 42.0, (
                            'Expected CPU usage to be 42.0'
                        )
                        assert report['ram'] == 65.5, (
                            'Expected RAM usage to be 65.5'
                        )
                        assert report['disk'] == 78.2, (
                            'Expected disk usage to be 78.2'
                        )
                        assert report['load_avg'] == 0.98, (
                            'Expected load average to be 0.98'
                        )
                        assert report['timestamp'] == '2025-01-01T12:00:00', (
                            'Expected correct ISO timestamp'
                        )


def test_generate_report_with_errors():
    """Test generate_report returns fallback values when functions fail."""
    logger = mock.Mock()

    with mock.patch('agents.utils.sysinfo.get_cpu_usage', return_value=-1.0):
        with mock.patch(
            'agents.utils.sysinfo.get_ram_usage', return_value=-1.0
        ):
            with mock.patch(
                'agents.utils.sysinfo.get_disk_usage', return_value=-1.0
            ):
                with mock.patch(
                    'agents.utils.sysinfo.get_load_average', return_value=-1.0
                ):
                    with mock.patch(
                        'agents.utils.sysinfo.datetime'
                    ) as mock_datetime:

                        mock_datetime.datetime.now.return_value = (
                            datetime.datetime(2025, 1, 1, 0, 0, 0)
                            )
                        report = generate_report(logger)

                        assert report['cpu'] == -1.0, (
                            'Expected CPU fallback value -1.0'
                        )
                        assert report['ram'] == -1.0, (
                            'Expected RAM fallback value -1.0'
                        )
                        assert report['disk'] == -1.0, (
                            'Expected disk fallback value -1.0'
                        )
                        assert report['load_avg'] == -1.0, (
                            'Expected load_avg fallback value -1.0'
                        )
                        assert report['timestamp'] == '2025-01-01T00:00:00', (
                            'Expected fallback timestamp'
                        )
