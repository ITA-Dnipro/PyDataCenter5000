"""
Discord alert bot for sending monitoring messages to a specific channel.
"""
import asyncio
import logging
import os

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

_bot_instance = None


class AlertBot(commands.Bot):
    """
    A custom Bot class that encapsulates all state and logic for alerting.
    """

    def __init__(self, channel_id: int, **kwargs):
        intents = discord.Intents.default()
        super().__init__(command_prefix='!', intents=intents, **kwargs)
        self.channel_id = channel_id

        # State attributes are initialized here but populated in on_ready.
        self.alert_queue = None
        self.alert_ready_event = None

    async def on_ready(self):
        """
        Called when the bot logs in and is ready.
        This is the correct place to initialize asyncio-dependent objects
        as the event loop is running at this point.
        """
        logger.info(f'Discord bot logged in as {self.user}')

        self.alert_queue = asyncio.Queue()
        self.alert_ready_event = asyncio.Event()

        channel = self.get_channel(self.channel_id)
        if not channel:
            logger.warning(
                'Discord channel not found (ID: %s)',
                self.channel_id
            )
            return

        self.alert_ready_event.set()
        self.loop.create_task(self.alert_worker(channel))

    async def alert_worker(self, channel: discord.TextChannel):
        """
        Background task that pulls messages from the queue and sends them.
        """
        logger.info(f'Alert worker started for channel #{channel.name}')
        while True:
            message = await self.alert_queue.get()
            try:
                await channel.send(message)
            except Exception as e:
                logger.exception('Failed to send Discord message: %s', str(e))
            finally:
                self.alert_queue.task_done()

    async def enqueue_alert(self, message: str):
        """
        Puts a message into the internal queue if the bot is ready.
        """
        if not self.alert_ready_event or not self.alert_ready_event.is_set():
            logger.warning('Bot is not ready, alert cannot be enqueued.')
            return

        await self.alert_ready_event.wait()
        await self.alert_queue.put(message)


def send_alert(message: str):
    """
    Thread-safe function to send an alert from synchronous Django code.
    """
    if (
            _bot_instance
            and _bot_instance.loop
            and _bot_instance.loop.is_running()
    ):
        asyncio.run_coroutine_threadsafe(
            _bot_instance.enqueue_alert(message), _bot_instance.loop
        )
    else:
        logger.warning('Discord bot loop not running — alert not sent.')


def start_discord_bot():
    """
    Entry point to initialize and start the bot. Called from apps.py.
    """
    global _bot_instance
    token = os.getenv('DISCORD_BOT_TOKEN')
    channel_id_str = os.getenv('DISCORD_CHANNEL_ID')

    if not token or not channel_id_str:
        logger.warning(
            'DISCORD_BOT_TOKEN or DISCORD_CHANNEL_ID not set. '
            'Bot will not start.'
        )
        return

    logger.info('Initializing Discord bot...')
    _bot_instance = AlertBot(channel_id=int(channel_id_str))

    try:
        logger.info('Starting Discord bot...')
        _bot_instance.run(token)
    except Exception as e:
        logger.exception('Discord bot failed to start: %s', str(e))
