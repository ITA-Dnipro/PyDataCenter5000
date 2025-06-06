import asyncio

from django.core.management.base import BaseCommand
from monitoring.discord_bot import DISCORD_TOKEN, bot


class Command(BaseCommand):
    """Starts the Discord bot for sending alerts"""

    def handle(self, *args, **kwargs):
        if not DISCORD_TOKEN:
            self.stderr.write('DISCORD_BOT_TOKEN not found in environment')
            return

        self.stdout.write('Starting Discord bot...')
        try:
            asyncio.run(bot.start(DISCORD_TOKEN))
        except KeyboardInterrupt:
            self.stdout.write('Bot stopped manually')
