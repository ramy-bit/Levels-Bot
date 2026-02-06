import os
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, request
from threading import Thread
import yfinance as yf
import logging

# --- CONFIG ---
TOKEN = os.environ['DISCORD_TOKEN']
ladder_memory = {}

# --- WEB SERVER (TradingView Receiver) ---
app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def home():
    return "Bot is alive!", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        ticker = data.get('ticker', 'UNKNOWN').strip().upper()
        raw_levels = data.get('levels', '')
        # Convert "490, 495" -> [490.0, 495.0]
        level_list = sorted([float(x.strip()) for x in raw_levels.split(',') if x.strip()])
        
        ladder_memory[ticker] = level_list
        print(f"✅ UPDATED: {ticker} -> {level_list}")
        return "Success", 200
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return "Error", 400

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- DISCORD BOT (Slash Commands) ---
class LevelBot(commands.Bot):
    def __init__(self):
        # We don't need a prefix for slash commands, but we set one anyway
        super().__init__(command_prefix='!', intents=discord.Intents.default())

    async def setup_hook(self):
        # This syncs the slash commands with Discord when the bot starts
        await self.tree.sync()
        print("Synced slash commands!")

bot = LevelBot()

# --- AUTOCOMPLETE FUNCTION ---
# This creates the dropdown list based on what is in memory
async def ticker_autocomplete(interaction: discord.Interaction, current: str):
    tickers = list(ladder_memory.keys())
    return [
        app_commands.Choice(name=ticker, value=ticker)
        for ticker in tickers if current.lower() in ticker.lower()
    ][:25] # Limit to 25 choices

# --- COMMAND: /LADDER ---
@bot.tree.command(name="ladder", description="Get support/resistance levels for a stock")
@app_commands.autocomplete(ticker=ticker_autocomplete)
async def ladder(interaction: discord.Interaction, ticker: str):
    ticker = ticker.strip().upper()
    
    # 1. Acknowledge (Show "Thinking...") so the bot doesn't time out
    await interaction.response.defer()

    # 2. Check Memory
    if ticker not in ladder_memory:
        await interaction.followup.send(f"⚠️ I don't have levels for **{ticker}** yet. Please trigger the TradingView alert.")
        return

    # 3. Get Price
    y_ticker = f"{ticker}-USD" if ticker in ['BTC', 'ETH', 'SOL', 'XRP'] else ticker
    try:
        current_price = yf.Ticker(y_ticker).fast_info['last_price']
    except:
        await interaction.followup.send(f"❌ Could not fetch price for {ticker}.")
        return

    # 4. Logic
    levels = ladder_memory[ticker]
    supports = sorted([x for x in levels if x < current_price], reverse=True)[:3]
    resistances = sorted([x for x in levels if x > current_price])[:3]

    # 5. Reply
    embed = discord.Embed(title=f"Levels for {ticker}", color=0x2b2d31)
    embed.description = f"**Price:** `{current_price:,.2f}`"
    embed.add_field(name="🔴 Resistance", value="\n".join([f"`{r:,.2f}`" for r in resistances]) or "-", inline=True)
    embed.add_field(name="🟢 Support", value="\n".join([f"`{s:,.2f}`" for s in supports]) or "-", inline=True)
    
    await interaction.followup.send(embed=embed)

# --- COMMAND: /SHOW_LIST ---
@bot.tree.command(name="show_list", description="See all tickers currently stored in memory")
async def show_list(interaction: discord.Interaction):
    if not ladder_memory:
        await interaction.response.send_message("📭 Memory is empty.")
    else:
        keys = ", ".join(ladder_memory.keys())
        await interaction.response.send_message(f"**Tracked Tickers:** {keys}")

if __name__ == '__main__':
    Thread(target=run_server).start()
    bot.run(TOKEN)
