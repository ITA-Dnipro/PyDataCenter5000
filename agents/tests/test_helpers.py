import logging

import mock

from agents.utils.helpers import restart_service


def test_restart_service_success_on_first_try():
    logger = mock.Mock()
    fallback_logger = mock.Mock()

    with mock.patch('subprocess.call') as mock_call:
        with mock.patch('time.sleep') as mock_sleep:
            with mock.patch(
                'agents.utils.helpers.maybe_log_message'
            ) as mock_log:

                mock_call.return_value = 0  # Success on first try

                result = restart_service(logger, fallback_logger, 'named')

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

                # Checking logs
                expected_logs = [
                    mock.call(
                        'named not active. Attempting restart...',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'Restarting named (delay before restart: 2).',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'named service restarted successfully.',
                        logger,
                        fallback_logger=fallback_logger,
                        level=logging.INFO
                    ),
                ]

                mock_log.assert_has_calls(expected_logs, any_order=False)
                assert mock_log.call_count == 3, (
                    'Expected three log messages during successful restart.'
                )


def test_restart_service_fails_all_attempts():
    logger = mock.Mock()
    fallback_logger = mock.Mock()

    with mock.patch('subprocess.call') as mock_call:
        with mock.patch('time.sleep') as mock_sleep:
            with mock.patch(
                'agents.utils.helpers.maybe_log_message'
            ) as mock_log:

                mock_call.return_value = 1  # Always fails

                result = restart_service(logger, fallback_logger, 'ssh')

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
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'Restarting ssh (delay before restart: 2).',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'ssh restart failed with code 1.',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'Restarting ssh (delay before restart: 4).',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'ssh restart failed with code 1.',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'Restarting ssh (delay before restart: 8).',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'ssh restart failed with code 1.',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                ]

                mock_log.assert_has_calls(expected_logs, any_order=False)
                assert mock_log.call_count == len(expected_logs), (
                    'Expected exact number of log messages '
                    'for all failed attempts.'
                )


def test_restart_service_raises_exception():
    logger = mock.Mock()
    fallback_logger = mock.Mock()

    with mock.patch(
        'agents.utils.helpers.subprocess.call',
        side_effect=OSError('boom')
    ):
        with mock.patch('time.sleep'):
            with mock.patch(
                'agents.utils.helpers.maybe_log_message'
            ) as mock_log:

                result = restart_service(logger, fallback_logger, 'named')

                assert result is False, (
                    'Expected restart_service to return False when an '
                    'exception is raised.'
                )

                # Checking logs
                expected_logs = [
                    mock.call(
                        'named not active. Attempting restart...',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'Restarting named (delay before restart: 2).',
                        logger,
                        fallback_logger=fallback_logger
                    ),
                    mock.call(
                        'Error during named service restart: boom',
                        logger,
                        fallback_logger=fallback_logger,
                        exc_info=True
                    )
                ]

                mock_log.assert_has_calls(expected_logs, any_order=False)
                assert mock_log.call_count == 3, (
                    'Expected exactly 3 log messages: '
                    'starting, restarting, and exception.'
                )
