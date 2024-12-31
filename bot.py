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
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"  # WETH contract
STONE_ADDRESS = "0x7E1E303cA1923Cadb6F312425235e284d965c8f6"  # Stone token address

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL)) if RPC_URL else None
if w3:
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# ERC20 ABI for balanceOf
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

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

async def get_token_balance(token_address, wallet_address):
    """Get ERC20 token balance"""
    token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
    balance = token_contract.functions.balanceOf(wallet_address).call()
    decimals = token_contract.functions.decimals().call()
    return float(balance) / (10 ** decimals)

async def calculate_tvl():
    """Calculate TVL by getting WETH and Stone balances"""
    try:
        if not w3 or not w3.is_connected():
            return None, None, None, "RPC connection failed"

        # Get WETH balance
        weth_balance = await get_token_balance(WETH_ADDRESS, VAULT_ADDRESS)
        
        # Get Stone balance
        stone_balance = await get_token_balance(STONE_ADDRESS, VAULT_ADDRESS)
        
        # Get ETH price
        eth_price = await get_eth_price()
        if eth_price is None:
            return None, None, None, "Failed to fetch ETH price"

        # Calculate TVL in USD (assuming WETH = ETH price)
        tvl_usd = weth_balance * eth_price

        return tvl_usd, weth_balance, stone_balance, None

    except Exception as e:
        print(f"Error calculating TVL: {str(e)}")
        return None, None, None, str(e)

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
        tvl_value, weth_balance, stone_balance, error = await calculate_tvl()
        
        if tvl_value is not None:
            formatted_tvl = f"${tvl_value:,.2f}"
            formatted_weth = f"{weth_balance:,.4f} WETH"
            formatted_stone = f"{stone_balance:,.4f} STONE"
            
            embed = discord.Embed(
                title="StoneBeraVault TVL",
                color=discord.Color.blue()
            )
            embed.add_field(name="TVL (USD)", value=formatted_tvl, inline=True)
            embed.add_field(name="WETH Balance", value=formatted_weth, inline=True)
            embed.add_field(name="STONE Balance", value=formatted_stone, inline=True)
            embed.set_footer(text="Data fetched from token balances")
            
            await message.edit(content=None, embed=embed)
        else:
            await message.edit(content=f"Unable to calculate TVL: {error}")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

# Run the bot
try:
    print("Starting bot...")
    bot.run(DISCORD_TOKEN)
except Exception as e:
    print(f"An unexpected error occurred: {str(e)}")
    sys.exit(1)
