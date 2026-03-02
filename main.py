import os
import discord
from discord.ext import commands, tasks
import yfinance as yf
import pandas as pd
from threading import Thread
from flask import Flask

# --- CONFIG ---
TOKEN = os.environ.get('DISCORD_TOKEN')
CHANNEL_ID = 1332824647970816041  # Your signals channel

# ⚠️ THE PRO WATCHLIST (Formatted perfectly for Yahoo Finance)
WATCHLIST = [
    "BTC-USD", "ETH-USD", "SOL-USD", "MSTR", "COIN", "IBIT", 
    "PLTR", "RDDT", "TSLA", "NVDA", "AMD", "ARM", "SMCI", 
    "BA", "SMH", "AAPL", "AMZN", "META", "GOOGL", "MSFT", 
    "NFLX", "DIS", "COST", "JPM", "BAC", "WMT", "XLF", 
    "SPY", "QQQ", "IWM", "DIA"
]

# --- FLASK SERVER (Keeps Render Awake) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Scanner is running!", 200

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- DISCORD BOT ---
class ScannerBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced!")
        # Start the background scanner when the bot boots up
        self.market_scanner.start()

bot = ScannerBot()

# --- THE MATH & LOGIC ENGINE ---
def analyze_stock(ticker):
    """Downloads data, calculates SMAs, and checks for the signal."""
    try:
        # Download 1 year of daily data
        data = yf.Ticker(ticker).history(period="1y", interval="1d")
        if data.empty or len(data) < 200:
            return None # Not enough data for a 200 SMA
            
        # Calculate SMAs
        data['SMA_9'] = data['Close'].rolling(window=9).mean()
        data['SMA_21'] = data['Close'].rolling(window=21).mean()
        data['SMA_50'] = data['Close'].rolling(window=50).mean()
        data['SMA_200'] = data['Close'].rolling(window=200).mean()
        
        # Look at the most recent completed day, and the day before it
        current_day = data.iloc[-1]
        prev_day = data.iloc[-2]
        
        # 1. Define the "Stacked" Condition (Bullish)
        curr_bull = (current_day['SMA_9'] > current_day['SMA_21'] > 
                     current_day['SMA_50'] > current_day['SMA_200'])
                     
        prev_bull = (prev_day['SMA_9'] > prev_day['SMA_21'] > 
                     prev_day['SMA_50'] > prev_day['SMA_200'])
        
        # 2. Check for FIRST candle alignment (Current is true, Previous was false)
        if curr_bull and not prev_bull:
            
            # Calculate Support/Resistance using standard Pivot Points
            day_high = current_day['High']
            day_low = current_day['Low']
            close_price = current_day['Close']
            
            pivot = (day_high + day_low + close_price) / 3
            r1 = (2 * pivot) - day_low
            s1 = (2 * pivot) - day_high
            
            return {
                "price": close_price,
                "r1": r1,
                "s1": s1
            }
            
        return None # No new signal today
        
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")
        return None

# --- THE BACKGROUND SCANNER ---
# This loop runs automatically every 4 hours. 
@tasks.loop(hours=4)
async def market_scanner():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
        
    print("🔄 Starting scheduled market scan...")
    
    for ticker in WATCHLIST:
        result = analyze_stock(ticker)
        
        if result:
            # We found a signal! Build the message.
            embed = discord.Embed(title=f"🚨 {ticker} Buy Signal (Daily Chart)", color=0x00FF00)
            embed.description = f"**SMA Alignment Confirmed** (9 > 21 > 50 > 200)\n**Current Price:** `${result['price']:,.2f}`"
            
            embed.add_field(name="🛑 Overhead Resistance", value=f"`${result['r1']:,.2f}`", inline=True)
            embed.add_field(name="🟢 Support Level", value=f"`${result['s1']:,.2f}`", inline=True)
            
            embed.set_footer(text="Automated Python Scanner")
            await channel.send(embed=embed)
            print(f"✅ Sent signal for {ticker}")

@market_scanner.before_loop
async def before_scanner():
    await bot.wait_until_ready()

# --- MANUAL TRIGGER COMMAND ---
@bot.tree.command(name="scan_now", description="Force the bot to scan the watchlist right now")
async def scan_now(interaction: discord.Interaction):
    # Defer the response so Discord doesn't timeout while we scan 30+ stocks
    await interaction.response.defer(ephemeral=True)
    
    found_signals = 0
    channel = bot.get_channel(CHANNEL_ID)
    
    for ticker in WATCHLIST:
        result = analyze_stock(ticker)
        if result:
            found_signals += 1
            embed = discord.Embed(title=f"🚨 {ticker} Buy Signal (Daily Chart)", color=0x00FF00)
            embed.description = f"**SMA Alignment Confirmed** (9 > 21 > 50 > 200)\n**Current Price:** `${result['price']:,.2f}`"
            embed.add_field(name="🛑 Overhead Resistance", value=f"`${result['r1']:,.2f}`", inline=True)
            embed.add_field(name="🟢 Support Level", value=f"`${result['s1']:,.2f}`", inline=True)
            await channel.send(embed=embed)
            
    if found_signals == 0:
        await interaction.followup.send("✅ Scan complete. No new SMA alignments found today.")
    else:
        await interaction.followup.send(f"✅ Scan complete. Found {found_signals} new setups!")

if __name__ == '__main__':
    Thread(target=run_server).start()
    bot.run(TOKEN)
