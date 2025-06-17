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
    Send alert if command result contains failure keywords.
    """
    keywords = ['error', 'failed', 'exception', 'traceback']
    if result and any(keyword in result.lower() for keyword in keywords):
        cleaned_result = result.strip()[:500]
        send_discord_alert(
            hostname=hostname,
            message=f'Command failed:\n```\n{cleaned_result}\n```',
            level='critical'
        )
