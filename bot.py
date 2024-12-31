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
RPC_URL = os.environ.get('RPC_URL')
VAULT_ADDRESS = "0x8f88aE3798E8fF3D0e0DE7465A0863C9bbB577f0"  # Vault address

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL)) if RPC_URL else None
if w3:
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)

async def get_eth_price():
    """Get current ETH price from CoinGecko"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['ethereum']['usd']
    except Exception as e:
        print(f"Error fetching ETH price: {str(e)}")
    return None

async def calculate_tvl():
    """Calculate TVL by getting vault's ETH balance"""
    try:
        if not w3 or not w3.is_connected():
            return None, "RPC connection failed"

        # Get ETH balance of vault address
        balance_wei = w3.eth.get_balance(VAULT_ADDRESS)
        balance_eth = w3.from_wei(balance_wei, 'ether')
        
        # Get ETH price
        eth_price = await get_eth_price()
        if eth_price is None:
            return None, "Failed to fetch ETH price"

        tvl_usd = float(balance_eth) * eth_price
        return tvl_usd, balance_eth

    except Exception as e:
        print(f"Error calculating TVL: {str(e)}")
        return None, str(e)

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user.name} ({bot.user.id})')

@bot.command(name='tvl')
async def tvl(ctx):
    """Command to fetch and display TVL"""
    try:
        # Send initial response
        message = await ctx.send("Calculating TVL...")
        
        # Calculate TVL
        tvl_value, eth_balance = await calculate_tvl()
        
        if tvl_value is not None:
            formatted_tvl = f"${tvl_value:,.2f}"
            formatted_eth = f"{eth_balance:,.2f} ETH"
            
            embed = discord.Embed(
                title="StoneBeraVault TVL",
                color=discord.Color.blue()
            )
            embed.add_field(name="TVL (USD)", value=formatted_tvl, inline=True)
            embed.add_field(name="TVL (ETH)", value=formatted_eth, inline=True)
            embed.set_footer(text="Data fetched from vault balance")
            
            await message.edit(content=None, embed=embed)
        else:
            await message.edit(content=f"Unable to calculate TVL: {eth_balance}")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

# Run the bot
try:
    print("Starting bot...")
    bot.run(DISCORD_TOKEN)
except Exception as e:
    print(f"An unexpected error occurred: {str(e)}")
    sys.exit(1)
