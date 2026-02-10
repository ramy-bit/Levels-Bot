import os
import discord
from discord import app_commands
from discord.ext import commands
import yfinance as yf
from threading import Thread
from flask import Flask

# --- CONFIG ---
TOKEN = os.environ['DISCORD_TOKEN']

# --- WEB SERVER (To keep Render awake) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!", 200

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- DISCORD BOT ---
class LevelBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync()
        print("Synced slash commands!")

bot = LevelBot()

# --- THE NEW LOGIC (Direct API Call) ---
@bot.tree.command(name="levels", description="Get today's High and Low for a stock")
async def levels(interaction: discord.Interaction, ticker: str):
    ticker = ticker.strip().upper()
    await interaction.response.defer() # Show "Thinking..."

    try:
        # 1. Get Data from Yahoo Finance (Free API)
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        
        # 2. Extract Key Levels
        current_price = info['last_price']
        day_high = info['day_high']
        day_low = info['day_low']
        prev_close = info['previous_close']
        
        # 3. Calculate Pivot Points (Optional but cool)
        pivot = (day_high + day_low + current_price) / 3
        r1 = (2 * pivot) - day_low
        s1 = (2 * pivot) - day_high

        # 4. Create the Message
        embed = discord.Embed(title=f"📊 Levels for {ticker}", color=0x00ff00)
        embed.description = f"**Current Price:** `{current_price:,.2f}`"
        
        embed.add_field(name="🚀 Day High", value=f"`{day_high:,.2f}`", inline=True)
        embed.add_field(name="🔻 Day Low", value=f"`{day_low:,.2f}`", inline=True)
        embed.add_field(name="⚖️ Pivot", value=f"`{pivot:,.2f}`", inline=True)
        
        embed.add_field(name="🛑 Resistance (R1)", value=f"`{r1:,.2f}`", inline=True)
        embed.add_field(name="🟢 Support (S1)", value=f"`{s1:,.2f}`", inline=True)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Could not find data for **{ticker}**. Try a valid symbol like AAPL or BTC-USD.")
        print(e)

if __name__ == '__main__':
    Thread(target=run_server).start()
    bot.run(TOKEN)
