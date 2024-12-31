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
CONTRACT_ADDRESS = os.environ.get('CONTRACT_ADDRESS')

# Validate token exists
if not DISCORD_TOKEN:
    print("Error: No Discord token provided.")
    sys.exit(1)

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL)) if RPC_URL else None
if w3:
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# ABI for Deposit event
CONTRACT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "name": "user",
                "type": "address"
            },
            {
                "indexed": False,
                "name": "amount",
                "type": "uint256"
            }
        ],
        "name": "Deposit",
        "type": "event"
    }
]

# Discord bot setup with minimal intents
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
    """Calculate TVL by summing all deposits"""
    try:
        if not w3 or not w3.is_connected():
            return None

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS),
            abi=CONTRACT_ABI
        )
        
        # Get latest block
        latest_block = w3.eth.block_number
        from_block = latest_block - 10000  # Look back ~24 hours (assuming ~15s block time)
        
        # Get deposit events
        deposit_filter = contract.events.Deposit.create_filter(fromBlock=from_block)
        events = deposit_filter.get_all_entries()
        
        # Sum all deposits
        total_deposits = sum(event['args']['amount'] for event in events)
        total_deposits_eth = w3.from_wei(total_deposits, 'ether')
        
        # Get current ETH price
        eth_price = await get_eth_price()
        if eth_price is None:
            return None
            
        # Calculate TVL in USD
        tvl_usd = float(total_deposits_eth) * eth_price
        return tvl_usd
        
    except Exception as e:
        print(f"Error calculating TVL: {str(e)}")
        return None

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user.name} ({bot.user.id})')

@bot.command(name='tvl')
async def tvl(ctx):
    """Command to fetch and display TVL"""
    try:
        # Send initial response to show the bot is working
        message = await ctx.send("Calculating TVL...")
        
        # Calculate TVL
        tvl_value = await calculate_tvl()
        
        if tvl_value is not None:
            formatted_tvl = f"${tvl_value:,.2f}"
            
            embed = discord.Embed(
                title="StoneBeraVault TVL",
                color=discord.Color.blue()
            )
            embed.add_field(name="Current TVL", value=formatted_tvl)
            embed.set_footer(text="Data calculated from deposit events")
            
            await message.edit(content=None, embed=embed)
        else:
            await message.edit(content="Unable to calculate TVL. Please check RPC connection and contract address.")
    except Exception as e:
        await ctx.send(f"An error occurred: {str(e)}")

# Run the bot
try:
    print("Starting bot...")
    bot.run(DISCORD_TOKEN)
except Exception as e:
    print(f"An unexpected error occurred: {str(e)}")
    sys.exit(1)
