import os
import discord
from discord import app_commands
from discord.ext import commands
import yfinance as yf
from threading import Thread
from flask import Flask

# --- CONFIG ---
TOKEN = os.environ['DISCORD_TOKEN']

# --- WEB SERVER ---
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
        print("✅ Synced slash commands to Discord!")

bot = LevelBot()

# --- TEST COMMAND 1: PING ---
# This tests if Discord is communicating with Render at all (No Yahoo Finance involved)
@bot.tree.command(name="ping", description="Test if the bot is responding")
async def ping(interaction: discord.Interaction):
    print("📥 Received /ping command")
    await interaction.response.send_message("🏓 Pong! The connection is perfect.")
    print("📤 Replied to /ping")

# --- TEST COMMAND 2: LEVELS (Simplified) ---
@bot.tree.command(name="levels", description="Test Yahoo Finance Data")
async def levels(interaction: discord.Interaction, ticker: str):
    print(f"📥 Received /levels command for {ticker}")
    
    # 1. Beat the 3-second rule instantly
    await interaction.response.defer()
    print("✅ Defer successful (Discord is waiting)")

    try:
        print("⏳ Reaching out to Yahoo Finance...")
        stock = yf.Ticker(ticker.upper())
        info = stock.fast_info
        current_price = info['last_price']
        
        print(f"✅ Yahoo Finance responded! Price: {current_price}")
        await interaction.followup.send(f"✅ Success! **{ticker.upper()}** is at `${current_price:,.2f}`")
        print("📤 Final message sent to Discord")

    except Exception as e:
        print(f"❌ CRASH inside Yahoo Finance block: {e}")
        await interaction.followup.send(f"❌ Could not load {ticker}.")

if __name__ == '__main__':
    Thread(target=run_server).start()
    bot.run(TOKEN)
