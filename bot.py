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

# Contract addresses
# StakeStone Vault
STAKESTONE_VAULT = Web3.to_checksum_address("0x8f88aE3798E8fF3D0e0DE7465A0863C9bbB577f0")
STAKESTONE_WETH = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
STAKESTONE_STONE = Web3.to_checksum_address("0x7122985656e38BDC0302Db86685bb972b145bD3C")

# Ethena Vaults and Tokens
ETHENA_SUDE_VAULT = Web3.to_checksum_address("0x9DC37e4a901b1e21Bd05E75c3B9A633A17001a39")
ETHENA_USDE_VAULT = Web3.to_checksum_address("0xf80c6636F9597d6a7FC1E5182B168B71e98Fd1cB")
SUDE_TOKEN = Web3.to_checksum_address("0x9D39A5DE30e57443BfF2A8307A4256c8797A3497")
USDE_TOKEN = Web3.to_checksum_address("0x4c9EDD5852cd905f086C759E8383e09bff1E68B3")

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL)) if RPC_URL else None
if w3:
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# ERC20 ABI
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

async def get_token_prices():
    """Get token prices from CoinGecko"""
    try:
        async with aiohttp.ClientSession() as session:
            # Get ETH price
            eth_url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
            async with session.get(eth_url) as response:
                if response.status != 200:
                    return None, None, None, None
                eth_data = await response.json()
                eth_price = eth_data['ethereum']['usd']

            # Get Stone price
            stone_url = "https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses=0x7122985656e38BDC0302Db86685bb972b145bD3C&vs_currencies=usd"
            async with session.get(stone_url) as response:
                if response.status != 200:
                    return None, None, None, None
                stone_data = await response.json()
                stone_price = stone_data.get('0x7122985656e38bdc0302db86685bb972b145bd3c', {}).get('usd', 0)

            # Get USDe and sUSDe prices
            stables_url = f"https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses={USDE_TOKEN},{SUDE_TOKEN}&vs_currencies=usd"
            async with session.get(stables_url) as response:
                if response.status != 200:
                    return None, None, None, None
                stables_data = await response.json()
                usde_price = stables_data.get(USDE_TOKEN.lower(), {}).get('usd', 1.0)  # Default to 1 if not found
                sude_price = stables_data.get(SUDE_TOKEN.lower(), {}).get('usd', 1.0)  # Default to 1 if not found

            return eth_price, stone_price, usde_price, sude_price
    except Exception as e:
        print(f"Error fetching prices: {str(e)}")
        return None, None, None, None

async def get_token_balance(token_address, wallet_address):
    """Get ERC20 token balance"""
    try:
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
        balance = token_contract.functions.balanceOf(wallet_address).call()
        decimals = token_contract.functions.decimals().call()
        return float(balance) / (10 ** decimals)
    except Exception as e:
        print(f"Error getting balance for token {token_address}: {str(e)}")
        return 0

def format_value(value):
    """Format value to M/B format"""
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    return f"${value / 1_000_000:.1f}M"

async def calculate_tvl():
    """Calculate TVL for both protocols"""
    try:
        if not w3 or not w3.is_connected():
            return None, "RPC connection failed"

        # Get prices
        eth_price, stone_price, usde_price, sude_price = await get_token_prices()
        if None in [eth_price, stone_price, usde_price, sude_price]:
            return None, "Failed to fetch token prices"

        # Calculate StakeStone Vault TVL
        stakestone_weth = await get_token_balance(STAKESTONE_WETH, STAKESTONE_VAULT)
        stakestone_stone = await get_token_balance(STAKESTONE_STONE, STAKESTONE_VAULT)
        stakestone_tvl = (stakestone_weth * eth_price) + (stakestone_stone * stone_price)

        # Calculate Ethena Vault TVL
        sude_balance = await get_token_balance(SUDE_TOKEN, ETHENA_SUDE_VAULT)
        usde_balance = await get_token_balance(USDE_TOKEN, ETHENA_USDE_VAULT)
        ethena_tvl = (sude_balance * sude_price) + (usde_balance * usde_price)

        # Calculate total TVL
        total_tvl = stakestone_tvl + ethena_tvl

        return {
            'stakestone': stakestone_tvl,
            'ethena': ethena_tvl,
            'total': total_tvl
        }, None

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
        message = await ctx.send("Calculating TVL...")
        
        tvl_data, error = await calculate_tvl()
        
        if tvl_data is not None:
            # Format the message
            response = f"""```
StakeStone Vault: {format_value(tvl_data['stakestone'])}
Ethena Vault: {format_value(tvl_data['ethena'])}
TOTAL TVL: {format_value(tvl_data['total'])}```"""
            
            await message.edit(content=response)
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
