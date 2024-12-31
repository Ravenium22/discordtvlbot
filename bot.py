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

# ABI with Deposit and Withdraw events
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
    },
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
        "name": "Withdraw",
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
    """Calculate TVL by tracking all deposits and withdrawals"""
    try:
        if not w3 or not w3.is_connected():
            return None, "RPC connection failed"

        contract = w3.eth.contract(
            address=Web3.to_checksum_address(CONTRACT_ADDRESS),
            abi=CONTRACT_ABI
        )

        # Get contract deploy block (you'll need to set this)
        deploy_block = 21458185  # Replace with actual deploy block
        latest_block = w3.eth.block_number

        # Track balances by address
        balances = {}

        # Process in chunks to handle large number of events
        chunk_size = 50000
        for start_block in range(deploy_block, latest_block + 1, chunk_size):
            end_block = min(start_block + chunk_size - 1, latest_block)
            
            # Get deposits
            deposit_events = contract.events.Deposit.get_logs(fromBlock=start_block, toBlock=end_block)
            for event in deposit_events:
                user = event['args']['user']
                amount = event['args']['amount']
                balances[user] = balances.get(user, 0) + amount

            # Get withdrawals
            withdraw_events = contract.events.Withdraw.get_logs(fromBlock=start_block, toBlock=end_block)
            for event in withdraw_events:
                user = event['args']['user']
                amount = event['args']['amount']
                balances[user] = balances.get(user, 0) - amount

        # Calculate total TVL
        total_balance_wei = sum(balance for balance in balances.values() if balance > 0)
        total_balance_eth = w3.from_wei(total_balance_wei, 'ether')

        # Get ETH price
        eth_price = await get_eth_price()
        if eth_price is None:
            return None, "Failed to fetch ETH price"

        tvl_usd = float(total_balance_eth) * eth_price
        return tvl_usd, None

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
        message = await ctx.send("Calculating TVL (this might take a minute as we process all historical data)...")
        
        # Calculate TVL
        tvl_value, error = await calculate_tvl()
        
        if tvl_value is not None:
            formatted_tvl = f"${tvl_value:,.2f}"
            
            embed = discord.Embed(
                title="StoneBeraVault TVL",
                color=discord.Color.blue()
            )
            embed.add_field(name="Current TVL", value=formatted_tvl)
            embed.set_footer(text="Calculated from all historical deposits and withdrawals")
            
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
