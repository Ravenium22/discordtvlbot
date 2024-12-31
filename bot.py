import discord
from discord.ext import commands
from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
import os
from dotenv import load_dotenv
import aiohttp
import sys

# Load environment variables - try both methods
load_dotenv()  # For local development
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')  # Changed from os.getenv to os.environ.get

# Validate token exists
if not DISCORD_TOKEN:
    print("Error: No Discord token provided. Please set the DISCORD_TOKEN environment variable.")
    sys.exit(1)

print("Token validation: Token exists and is", len(DISCORD_TOKEN), "characters long")  # Debug line

# Rest of your imports and setup
RPC_URL = os.environ.get('RPC_URL')
CONTRACT_ADDRESS = os.environ.get('CONTRACT_ADDRESS')

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL)) if RPC_URL else None
if w3:
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user.name} ({bot.user.id})')
    print('Connected to guilds:', [guild.name for guild in bot.guilds])

@bot.command(name='tvl')
async def tvl(ctx):
    """
    Command to fetch and display TVL
    Usage: ?tvl
    """
    await ctx.send("TVL command received! Bot is working.")
    # Rest of TVL logic will be added back once basic functionality is confirmed

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
