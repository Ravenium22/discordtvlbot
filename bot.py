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
VAULT_ADDRESS = Web3.to_checksum_address("0x8f88aE3798E8fF3D0e0DE7465A0863C9bbB577f0")
WETH_ADDRESS = Web3.to_checksum_address("0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
STONE_ADDRESS = Web3.to_checksum_address("0x7122985656e38BDC0302Db86685bb972b145bD3C")

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
    """Get both ETH and Stone prices from CoinGecko"""
    try:
        async with aiohttp.ClientSession() as session:
            # Get ETH price
            eth_url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
            async with session.get(eth_url) as response:
                if response.status != 200:
                    return None, None
                eth_data = await response.json()
                eth_price = eth_data['ethereum']['usd']

            # Get Stone price
            stone_url = "https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses=0x7122985656e38BDC0302Db86685bb972b145bD3C&vs_currencies=usd"
            async with session.get(stone_url) as response:
                if response.status != 200:
                    return None, None
                stone_data = await response.json()
                stone_price = stone_data.get('0x7122985656e38bdc0302db86685bb972b145bd3c', {}).get('usd', 0)

            return eth_price, stone_price
    except Exception as e:
        print(f"Error fetching prices: {str(e)}")
        return None, None

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

async def calculate_tvl():
    """Calculate TVL using actual token prices"""
    try:
        if not w3 or not w3.is_connected():
            return None, "RPC connection failed"

        # Get balances
        weth_balance = await get_token_balance(WETH_ADDRESS, VAULT_ADDRESS)
        stone_balance = await get_token_balance(STONE_ADDRESS, VAULT_ADDRESS)
        print(f"WETH balance: {weth_balance}")
        print(f"Stone balance: {stone_balance}")

        # Get prices
        eth_price, stone_price = await get_token_prices()
        print(f"ETH price: ${eth_price}")
        print(f"Stone price: ${stone_price}")
        
        if eth_price is None or stone_price is None:
            return None, "Failed to fetch token prices"

        # Calculate total TVL in USD
        weth_value = weth_balance * eth_price
        stone_value = stone_balance * stone_price
        total_tvl = weth_value + stone_value

        print(f"WETH value: ${weth_value:,.2f}")
        print(f"Stone value: ${stone_value:,.2f}")
        print(f"Total TVL: ${total_tvl:,.2f}")

        return total_tvl, None

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
        
        tvl_value, error = await calculate_tvl()
        
        if tvl_value is not None:
            if tvl_value >= 1_000_000_000:
                formatted_tvl = f"${tvl_value / 1_000_000_000:.1f}B"
            else:
                formatted_tvl = f"${tvl_value / 1_000_000:.1f}M"
            
            embed = discord.Embed(
                title="StoneBeraVault TVL",
                description=formatted_tvl,
                color=discord.Color.blue()
            )
            
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
