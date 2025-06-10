from unittest.mock import patch

from monitoring.alerts import alert_if_command_failed, alert_if_unhealthy


@patch('monitoring.alerts.send_discord_alert')
def test_alert_if_command_failed_triggers(mock_send):
    alert_if_command_failed('agent-1', 'Failed to restart service')
    mock_send.assert_called_once_with(
        'agent-1',
        'Command failed:\n```\nFailed to restart service\n```'
    )


@patch('monitoring.alerts.send_discord_alert')
def test_alert_if_command_failed_ignores_clean_result(mock_send):
    alert_if_command_failed('agent-1', 'Command completed successfully')
    mock_send.assert_not_called()


@patch('monitoring.alerts.send_discord_alert')
def test_alert_if_unhealthy_triggers(mock_send):
    alert_if_unhealthy('agent-1', healthy=False)
    mock_send.assert_called_once_with(
        'agent-1',
        'Agent reported unhealthy status.'
    )


@patch('monitoring.alerts.send_discord_alert')
def test_alert_if_unhealthy_ignores_healthy(mock_send):
    alert_if_unhealthy('agent-1', healthy=True)
    mock_send.assert_not_called()
