from monitoring.discord_bot import send_alert


def send_discord_alert(
        hostname: str,
        message: str,
        level: str = 'warning'
) -> None:
    """
    Format and send an alert message to Discord.
    """
    emoji = {
        'critical': '🚨',
        'warning': '⚠️',
        'info': 'ℹ️',
    }.get(level, '📢')
    full_message = f'{emoji} Alert from agent `{hostname}`:\n{message}'
    send_alert(full_message)


def alert_if_unhealthy(hostname: str, healthy: bool) -> None:
    """
    Send alert if agent reports unhealthy status.
    """
    if not healthy:
        send_discord_alert(
            hostname=hostname,
            message='Agent reported unhealthy status.',
            level='warning'
        )


def alert_if_command_failed(hostname: str, result: str) -> None:
    """
    Send alert if command result contains 'error' or 'failed'.
    """
    if result and ('error' in result.lower() or 'failed' in result.lower()):
        send_discord_alert(
            hostname=hostname,
            message=f'Command failed:\n```\n{result}\n```',
            level='critical'
        )
