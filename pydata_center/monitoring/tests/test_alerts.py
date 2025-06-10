"""
Unit tests for the alert triggering functions.
"""
from unittest.mock import patch

import pytest
from monitoring.alerts import alert_if_command_failed, alert_if_unhealthy


class TestAlertIfCommandFailed:
    """Tests for the `alert_if_command_failed` function."""

    @pytest.mark.parametrize(
        'failed_result_string',
        [
            'An error occurred during execution.',
            'Service deployment failed.',
            'ERROR: process not found',
        ],
    )
    @patch('monitoring.alerts.send_discord_alert')
    def test_triggers_on_failure_keywords(
            self,
            mock_send,
            failed_result_string
    ):
        """
        Test that an alert is triggered
        if the result contains failure keywords.
        """
        alert_if_command_failed('agent-1', failed_result_string)

        expected_message = f'Command failed:\n```\n{failed_result_string}\n```'

        mock_send.assert_called_once_with('agent-1', expected_message)

    @patch('monitoring.alerts.send_discord_alert')
    def test_ignores_clean_result(self, mock_send):
        """Test that no alert is sent for a successful command result."""
        alert_if_command_failed('agent-1', 'Command completed successfully')
        mock_send.assert_not_called()


class TestAlertIfUnhealthy:
    """Tests for the `alert_if_unhealthy` function."""

    @patch('monitoring.alerts.send_discord_alert')
    def test_triggers_on_unhealthy_status(self, mock_send):
        """Test that an alert is triggered when healthy=False."""
        alert_if_unhealthy('agent-1', healthy=False)
        mock_send.assert_called_once_with(
            'agent-1', 'Agent reported unhealthy status.'
        )

    @patch('monitoring.alerts.send_discord_alert')
    def test_ignores_healthy_status(self, mock_send):
        """Test that no alert is sent when healthy=True."""
        alert_if_unhealthy('agent-1', healthy=True)
        mock_send.assert_not_called()
