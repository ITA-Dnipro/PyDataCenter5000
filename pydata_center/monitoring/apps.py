import threading

from django.apps import AppConfig


class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'monitoring'

    def ready(self):
        from .discord_bot import start_discord_bot
        threading.Thread(target=start_discord_bot, daemon=True).start()
