from monitoring.discord_bot import send_alert


def send_discord_alert(hostname: str, message: str) -> None:
    """
    Format and send an alert message to Discord.
    """
    full_message = f'🚨 Alert from agent `{hostname}`:\n{message}'
    send_alert(full_message)


def alert_if_unhealthy(hostname: str, healthy: bool) -> None:
    """
    Send alert if agent reports unhealthy status.
    """
    if not healthy:
        send_discord_alert(hostname, 'Agent reported unhealthy status.')


def alert_if_command_failed(hostname: str, result: str) -> None:
    """
    Send alert if command result contains 'error' or 'failed'.
    """
    if result and ('error' in result.lower() or 'failed' in result.lower()):
        send_discord_alert(hostname, f'Command failed:\n```\n{result}\n```')
