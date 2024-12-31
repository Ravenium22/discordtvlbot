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

# Ethena Tokens and their correct vaults
SUDE_TOKEN = Web3.to_checksum_address("0x9D39A5DE30e57443BfF2A8307A4256c8797A3497")  # sUSDe token
USDE_TOKEN = Web3.to_checksum_address("0x4c9EDD5852cd905f086C759E8383e09bff1E68B3")   # USDe token
SUDE_VAULT = Web3.to_checksum_address("0xf80c6636F9597d6a7FC1E5182B168B71e98Fd1cB")  # Vault for sUSDe
USDE_VAULT = Web3.to_checksum_address("0x9DC37e4a901b1e21Bd05E75c3B9A633A17001a39")  # Vault for USDe

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

async def get_eth_price():
    """Get ETH price from CoinGecko"""
    try:
        headers = {'accept': 'application/json'}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['ethereum']['usd']
    except Exception as e:
        print(f"Error fetching ETH price: {str(e)}")
    return None

async def get_token_balance(token_address, wallet_address):
    """Get ERC20 token balance with detailed logging"""
    try:
        token_contract = w3.eth.contract(address=token_address, abi=ERC20_ABI)
        balance = token_contract.functions.balanceOf(wallet_address).call()
        decimals = token_contract.functions.decimals().call()
        balance_formatted = float(balance) / (10 ** decimals)
        print(f"Balance for token {token_address} in wallet {wallet_address}: {balance_formatted}")
        return balance_formatted
    except Exception as e:
        print(f"Error getting balance for token {token_address} in wallet {wallet_address}: {str(e)}")
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

        eth_price = await get_eth_price()
        if eth_price is None:
            return None, "Failed to fetch ETH price"

        # StakeStone TVL calculation
        stakestone_weth = await get_token_balance(STAKESTONE_WETH, STAKESTONE_VAULT)
        stakestone_stone = await get_token_balance(STAKESTONE_STONE, STAKESTONE_VAULT)
        stakestone_tvl = (stakestone_weth * eth_price) + (stakestone_stone * eth_price)
        
        # Ethena TVL calculation
        usde_balance = await get_token_balance(USDE_TOKEN, USDE_VAULT)
        sude_balance = await get_token_balance(SUDE_TOKEN, SUDE_VAULT)
        ethena_tvl = usde_balance + sude_balance  # Both are stablecoins so using $1
        
        total_tvl = stakestone_tvl + ethena_tvl

        print(f"""
TVL Breakdown:
-------------
StakeStone:
WETH: {stakestone_weth} (${stakestone_weth * eth_price:,.2f})
Stone: {stakestone_stone} (${stakestone_stone * eth_price:,.2f})
Total: ${stakestone_tvl:,.2f}

Ethena:
USDe: ${usde_balance:,.2f}
sUSDe: ${sude_balance:,.2f}
Total: ${ethena_tvl:,.2f}

Total TVL: ${total_tvl:,.2f}
""")

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
