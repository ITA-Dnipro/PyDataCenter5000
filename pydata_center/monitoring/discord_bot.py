"""
Discord alert bot for sending monitoring messages to a specific channel.
Used by alerts.py via send_alert().
"""

import asyncio
import logging
import os

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

alert_queue = None
alert_ready = asyncio.Event()
bot_loop = None


@bot.event
async def on_ready():
    global alert_queue, bot_loop
    alert_queue = asyncio.Queue()
    bot_loop = asyncio.get_running_loop()
    alert_ready.set()
    bot.loop.create_task(alert_worker())


async def alert_worker():
    """
    Background task that continuously sends messages from the queue to Discord.
    """
    await bot.wait_until_ready()
    await alert_ready.wait()
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        logger.warning('Discord channel not found (ID: %s)', CHANNEL_ID)
        return
    while True:
        message = await alert_queue.get()
        try:
            await channel.send(message)
        except Exception as e:
            logger.exception('Failed to send Discord message: %s', str(e))


async def enqueue_alert(message: str):
    """
    Enqueue a message to be sent to Discord.
    """
    await alert_ready.wait()
    if alert_queue is not None:
        await alert_queue.put(message)


def send_alert(message: str):
    """
    Send an alert message to Discord.
    Can be safely called from any Django context (sync or async).
    """
    global bot_loop
    if bot_loop and bot_loop.is_running():
        asyncio.run_coroutine_threadsafe(enqueue_alert(message), bot_loop)


def start_discord_bot():
    """
    Start the bot once at Django startup.
    """
    if not DISCORD_TOKEN or not CHANNEL_ID:
        return
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.exception('Discord bot failed to start: %s', str(e))
