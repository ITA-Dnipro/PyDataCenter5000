import datetime
import hashlib
import os
import threading

import jwt
from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


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
        from .models import Agent

        @receiver(post_save, sender=Agent)
        def generate_token_for_new_agent(
            sender, instance, created, **kwargs
        ):
            if created and not instance.token_hash:
                payload = {
                    'agent_id': instance.id,
                    'name': instance.name,
                    'iat': int(
                        datetime.datetime.utcnow().timestamp()
                    ),
                }

                token = jwt.encode(
                    payload,
                    settings.SECRET_KEY,
                    algorithm='HS256'
                )

                if isinstance(token, bytes):
                    token = token.decode()

                instance.token_hash = hashlib.sha512(
                    token.encode()
                ).hexdigest()
                instance.save(update_fields=['token_hash'])
                instance._plain_token = token

        if os.environ.get('RUN_MAIN') == 'true':
            threading.Thread(
                target=safe_start_discord_bot,
                daemon=True
            ).start()
