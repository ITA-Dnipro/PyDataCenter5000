import os
import threading

from django.apps import AppConfig


def safe_start_discord_bot():
    try:
        from .discord_bot import start_discord_bot
        start_discord_bot()
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception(
            'Discord bot failed to start: %s', str(e)
        )


class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoring'

    def ready(self):
        if os.environ.get('RUN_MAIN') == 'true':
            threading.Thread(
                target=safe_start_discord_bot,
                daemon=True
            ).start()
