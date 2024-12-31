import discord
from discord.ext import commands
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import os
from dotenv import load_dotenv
import aiohttp
import sys

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')

# Validate token exists
if not DISCORD_TOKEN:
    print("Error: No Discord token provided. Please set the DISCORD_TOKEN environment variable.")
    sys.exit(1)

print("Token validation: Token exists and is", len(DISCORD_TOKEN), "characters long")

# Discord bot setup with minimal intents
intents = discord.Intents.default()
intents.message_content = True  # We only need message content intent for commands

# Initialize bot with minimal requirements
bot = commands.Bot(
    command_prefix='?',
    intents=intents,
    description='A bot to check TVL'
)

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user.name} ({bot.user.id})')

@bot.command(name='tvl')
async def tvl(ctx):
    """Simple command to check if bot is working"""
    await ctx.send("TVL command received! Bot is working.")

try:
    print("Starting bot...")
    bot.run(DISCORD_TOKEN)
except discord.errors.LoginFailure as e:
    print("Error: Failed to log in to Discord. Token may be invalid.")
    print(f"Error details: {str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred: {str(e)}")
    sys.exit(1)
