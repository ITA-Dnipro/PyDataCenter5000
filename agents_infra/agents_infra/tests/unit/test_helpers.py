import logging
import os

import mock
import pytest

from ...utils.helpers import (get_env_or_param, is_process_active, is_valid_ip,
                              restart_service)

# TESTS FOR restart_service()


def test_restart_service_success_on_first_try():
    logger = mock.Mock()

    with mock.patch('subprocess.call') as mock_call:
        with mock.patch('time.sleep') as mock_sleep:
            with mock.patch(
                'agents_infra.utils.helpers.maybe_log_message'
            ) as mock_log:

                mock_call.return_value = 0  # Success on first try

                result = restart_service('named', logger=logger)

                assert result is True, (
                    'Expected restart_service to return True when '
                    'service restarts on first attempt.'
                )
                assert mock_call.call_count == 1, (
                    'Expected one call to subprocess.call.'
                )
                assert mock_sleep.call_count == 1, (
                    'Expected one sleep call before first restart.'
                )

                # Validate subprocess.call was called with the expected command
                expected_calls = [
                    mock.call(['sudo', 'systemctl', 'restart', 'named']),
                ]
                mock_call.assert_has_calls(expected_calls, any_order=False)

                # Checking logs
                expected_logs = [
                    mock.call(
                        'named not active. Attempting restart...',
                        logger=logger,
                    ),
                    mock.call(
                        'Attempt 1: Restarting named '
                        '(delay before restart: 2).',
                        logger=logger,
                    ),
                    mock.call(
                        'named service restarted successfully.',
                        logger=logger,
                        level=logging.INFO
                    ),
                ]

                mock_log.assert_has_calls(expected_logs, any_order=False)
                assert mock_log.call_count == 3, (
                    'Expected three log messages during successful restart.'
                )


def test_restart_service_success_on_third_try():
    logger = mock.Mock()

    with mock.patch('subprocess.call') as mock_call:
        with mock.patch('time.sleep') as mock_sleep:
            with mock.patch(
                'agents_infra.utils.helpers.maybe_log_message'
            ) as mock_log:

                # First two attempts fail (return code 1),
                # third succeeds (return code 0)
                mock_call.side_effect = [1, 1, 0]

                result = restart_service('ssh', logger=logger)

                assert result is True, (
                    'Expected restart_service to return True when '
                    'service succeeds on the third attempt.'
                )
                assert mock_call.call_count == 3, (
                    'Expected three calls to subprocess.call '
                    'for three restart attempts.'
                    )
                assert mock_sleep.call_count == 3, (
                    'Expected three delay intervals before each attempt.'
                    )

                # Validate the exact command used
                expected_calls = [
                    mock.call(['sudo', 'systemctl', 'restart', 'ssh']),
                    mock.call(['sudo', 'systemctl', 'restart', 'ssh']),
                    mock.call(['sudo', 'systemctl', 'restart', 'ssh']),
                    ]
                mock_call.assert_has_calls(expected_calls, any_order=False)

                # Validate logging
                expected_log_messages = [
                    mock.call(
                        'ssh not active. Attempting restart...',
                        logger=logger,
                    ),
                    mock.call(
                        'Attempt 1: Restarting ssh (delay before restart: 2).',
                        logger=logger,
                    ),
                    mock.call(
                        'ssh restart failed with code 1.',
                        logger=logger,
                    ),
                    mock.call(
                        'Attempt 2: Restarting ssh (delay before restart: 4).',
                        logger=logger,
                    ),
                    mock.call(
                        'ssh restart failed with code 1.',
                        logger=logger,
                    ),
                    mock.call(
                        'Attempt 3: Restarting ssh (delay before restart: 8).',
                        logger=logger,
                    ),
                    mock.call(
                        'ssh service restarted successfully.',
                        logger=logger,
                        level=logging.INFO),
                    ]
                mock_log.assert_has_calls(
                    expected_log_messages,
                    any_order=False
                )
                assert mock_log.call_count == 7, (
                    'Expected 7 log messages during 3 restart attempts.'
                    )


def test_restart_service_fails_all_attempts():
    logger = mock.Mock()

    with mock.patch('subprocess.call') as mock_call:
        with mock.patch('time.sleep') as mock_sleep:
            with mock.patch(
                'agents_infra.utils.helpers.maybe_log_message'
            ) as mock_log:

                mock_call.return_value = 1  # Always fails

                result = restart_service('ssh', logger=logger)

                assert result is False, (
                    'Expected restart_service to return False when '
                    'all attempts to restart fail.'
                )
                assert mock_call.call_count == 3, (
                    'Expected 3 retry attempts on failure.'
                )
                assert mock_sleep.call_count == 3, (
                    'Expected 3 sleep calls on retry.'
                )

                # Checking logs
                expected_logs = [
                    mock.call(
                        'ssh not active. Attempting restart...',
                        logger=logger,
                    ),
                    mock.call(
                        'Attempt 1: Restarting ssh (delay before restart: 2).',
                        logger=logger,
                    ),
                    mock.call(
                        'ssh restart failed with code 1.',
                        logger=logger,
                    ),
                    mock.call(
                        'Attempt 2: Restarting ssh (delay before restart: 4).',
                        logger=logger,
                    ),
                    mock.call(
                        'ssh restart failed with code 1.',
                        logger=logger,
                    ),
                    mock.call(
                        'Attempt 3: Restarting ssh (delay before restart: 8).',
                        logger=logger,
                    ),
                    mock.call(
                        'ssh restart failed with code 1.',
                        logger=logger,
                    ),
                ]

                mock_log.assert_has_calls(expected_logs, any_order=False)
                assert mock_log.call_count == len(expected_logs), (
                    'Expected exact number of log messages '
                    'for all failed attempts.'
                )


def test_restart_service_raises_exception():
    logger = mock.Mock()

    with mock.patch(
        'agents_infra.utils.helpers.subprocess.call',
        side_effect=OSError('boom')
    ):
        with mock.patch('time.sleep'):
            with mock.patch(
                'agents_infra.utils.helpers.maybe_log_message'
            ) as mock_log:

                result = restart_service('named', logger=logger)

                assert result is False, (
                    'Expected restart_service to return False when an '
                    'exception is raised.'
                )

                # Checking logs
                expected_logs = [
                    mock.call(
                        'named not active. Attempting restart...',
                        logger=logger,
                    ),
                    mock.call(
                        'Attempt 1: Restarting named '
                        '(delay before restart: 2).',
                        logger=logger,
                    ),
                    mock.call(
                        'Error during named service restart: boom',
                        logger=logger,
                        exc_info=True
                    )
                ]

                mock_log.assert_has_calls(expected_logs, any_order=False)
                assert mock_log.call_count == 3, (
                    'Expected exactly 3 log messages: '
                    'starting, restarting, and exception.'
                )


# TESTS FOR get_env_or_param()

def test_web_agent_get_env_or_param():
    """Test environment variable handling in get_env_or_param fucntion."""
    original_value = os.environ.get('TEST_VAR')

    try:
        os.environ['TEST_VAR'] = 'env_value'
        assert get_env_or_param(None, 'TEST_VAR') == 'env_value', (
            'Should return the environment variable value when param is None.'
        )

        assert get_env_or_param('mock_val', 'TEST_VAR') == 'mock_val', (
            'Should return the provided param value when it is not None.'
        )

        del os.environ['TEST_VAR']
        with pytest.raises(ValueError):
            get_env_or_param(None, 'MISSING_VAR')

    finally:
        # Clean up
        if original_value is not None:
            os.environ['TEST_VAR'] = original_value
        elif 'TEST_VAR' in os.environ:
            del os.environ['TEST_VAR']


# TESTS FOR is_valid_ip()

def test_valid_ipv4():
    assert is_valid_ip('192.168.1.1'), "Expected '192.168.1.1' to be valid"
    assert is_valid_ip('8.8.8.8'), "Expected '8.8.8.8' to be valid"
    assert is_valid_ip(' 10.0.0.1 '), (
        "Expected ' 10.0.0.1 ' (with spaces) to be valid"
        )


def test_invalid_ipv4():
    assert not is_valid_ip('999.999.999.999'), (
        "Expected '999.999.999.999' to be invalid"
        )
    assert not is_valid_ip('256.0.0.1'), "Expected '256.0.0.1' to be invalid"
    assert not is_valid_ip('abcd'), "Expected 'abcd' to be invalid"
    assert not is_valid_ip('1234'), "Expected '1234' to be invalid"
    assert not is_valid_ip(''), 'Expected empty string to be invalid'
    assert not is_valid_ip('192.168.1.'), "Expected '192.168.1.' to be invalid"


def test_ipv6_not_supported():
    assert not is_valid_ip('::1'), "Expected IPv6 address '::1' to be invalid"
    assert not is_valid_ip('2001:db8::1'), (
        "Expected IPv6 address '2001:db8::1' to be invalid"
        )

# TESTS FOR is_process_active()


@mock.patch('subprocess.Popen')
def test_service_active(mock_popen):
    process_mock = mock.Mock()
    process_mock.communicate.return_value = ('active\n', '')
    process_mock.returncode = 0
    mock_popen.return_value = process_mock

    assert is_process_active('ssh') is True, (
        'Expected True for active service "ssh"'
        )


@mock.patch('subprocess.Popen')
def test_service_inactive(mock_popen):
    process_mock = mock.Mock()
    process_mock.communicate.return_value = ('inactive\n', '')
    process_mock.returncode = 3
    mock_popen.return_value = process_mock

    assert is_process_active('cron') is False, (
        'Expected False for inactive service "cron"'
    )


@mock.patch('subprocess.Popen')
def test_service_failed_status(mock_popen):
    process_mock = mock.Mock()
    process_mock.communicate.return_value = ('unknown\n', 'some error')
    process_mock.returncode = 1  # unexpected return code
    mock_popen.return_value = process_mock

    with pytest.raises(Exception) as exc:
        is_process_active('nginx')

    assert "Failed to check service status for 'nginx'" in str(exc.value), (
        'Expected exception with service name in error message'
    )


@mock.patch('subprocess.Popen')
def test_service_decodes_output(mock_popen):
    process_mock = mock.Mock()
    process_mock.communicate.return_value = (b'active\n', b'')
    process_mock.returncode = 0
    mock_popen.return_value = process_mock

    assert is_process_active('networking') is True, (
        'Expected True after decoding  output for active service "networking"'
    )
