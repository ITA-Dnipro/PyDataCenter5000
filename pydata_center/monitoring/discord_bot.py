import asyncio
import os

import discord
from discord.ext import commands

# Load bot credentials from environment variables
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# Queue for pending alerts
alert_queue = asyncio.Queue()


@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')
    bot.loop.create_task(alert_worker())


async def alert_worker():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print('Failed to get channel. Check DISCORD_CHANNEL_ID.')
        return

    while True:
        message = await alert_queue.get()
        try:
            await channel.send(message)
        except Exception as e:
            print(f'Failed to send message: {e}')


async def enqueue_alert(message: str):
    await alert_queue.put(message)


def send_alert(message: str):
    """
    Puts message into alert queue from sync Django context.
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(enqueue_alert(message))
    else:
        loop.run_until_complete(enqueue_alert(message))


if __name__ == '__main__':
    if not DISCORD_TOKEN or not CHANNEL_ID:
        raise RuntimeError('Missing DISCORD_BOT_TOKEN '
                           'or DISCORD_CHANNEL_ID in environment')
    bot.run(DISCORD_TOKEN)
