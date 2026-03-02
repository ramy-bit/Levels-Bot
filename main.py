import os
import discord
from discord.ext import commands, tasks
import yfinance as yf
import pandas as pd
from threading import Thread
from flask import Flask, request
import asyncio

# --- CONFIG ---
TOKEN = os.environ.get('DISCORD_TOKEN')
CHANNEL_ID = 1332824647970816041  # Your signals channel

# THE PRO WATCHLIST
WATCHLIST = [
    "BTC-USD", "ETH-USD", "SOL-USD", "MSTR", "COIN", "IBIT", 
    "PLTR", "RDDT", "TSLA", "NVDA", "AMD", "ARM", "SMCI", 
    "BA", "SMH", "AAPL", "AMZN", "META", "GOOGL", "MSFT", 
    "NFLX", "DIS", "COST", "JPM", "BAC", "WMT", "XLF", 
    "SPY", "QQQ", "IWM", "DIA"
]

# --- FLASK SERVER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Scanner is running!", 200

# ⚠️ THE TRADINGVIEW FIX
@app.route('/webhook', methods=['POST'])
def webhook():
    # This catches your old TradingView alerts so they don't cause 404 errors!
    return "Webhook ignored (Standalone mode active)", 200

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- DISCORD BOT ---
class ScannerBot(commands.Bot):
    def __init__(self):
        # We are adding "!" as a backup command prefix
        super().__init__(command_prefix='!', intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced!")
        self.market_scanner.start()

bot = ScannerBot()

# --- THE MATH ENGINE ---
def analyze_stock(ticker):
    try:
        data = yf.Ticker(ticker).history(period="1y", interval="1d")
        if data.empty or len(data) < 200:
            return None 
            
        data['SMA_9'] = data['Close'].rolling(window=9).mean()
        data['SMA_21'] = data['Close'].rolling(window=21).mean()
        data['SMA_50'] = data['Close'].rolling(window=50).mean()
        data['SMA_200'] = data['Close'].rolling(window=200).mean()
        
        current_day = data.iloc[-1]
        prev_day = data.iloc[-2]
        
        curr_bull = (current_day['SMA_9'] > current_day['SMA_21'] > 
                     current_day['SMA_50'] > current_day['SMA_200'])
                     
        prev_bull = (prev_day['SMA_9'] > prev_day['SMA_21'] > 
                     prev_day['SMA_50'] > prev_day['SMA_200'])
        
        if curr_bull and not prev_bull:
            day_high = current_day['High']
            day_low = current_day['Low']
            close_price = current_day['Close']
            
            pivot = (day_high + day_low + close_price) / 3
            r1 = (2 * pivot) - day_low
            s1 = (2 * pivot) - day_high
            
            return {"price": close_price, "r1": r1, "s1": s1}
            
        return None 
        
    except Exception as e:
        print(f"Error scanning {ticker}: {e}")
        return None

# --- BACKGROUND SCANNER ---
@tasks.loop(hours=4)
async def market_scanner():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        return
        
    print("🔄 Starting scheduled market scan...")
    
    for ticker in WATCHLIST:
        result = analyze_stock(ticker)
        if result:
            embed = discord.Embed(title=f"🚨 {ticker} Buy Signal (Daily)", color=0x00FF00)
            embed.description = f"**SMA Alignment Confirmed** (9 > 21 > 50 > 200)\n**Price:** `${result['price']:,.2f}`"
            embed.add_field(name="🛑 Resistance", value=f"`${result['r1']:,.2f}`", inline=True)
            embed.add_field(name="🟢 Support", value=f"`${result['s1']:,.2f}`", inline=True)
            await channel.send(embed=embed)
        
        await asyncio.sleep(2) 

@market_scanner.before_loop
async def before_scanner():
    await bot.wait_until_ready()


# --- THE NEW TEXT COMMAND (Foolproof Backup) ---
@bot.command(name="scan")
async def text_scan(ctx):
    await ctx.send("🕵️‍♂️ **Scanning the watchlist...** This will take about a minute.")
    found_signals = 0
    
    for ticker in WATCHLIST:
        result = analyze_stock(ticker)
        if result:
            found_signals += 1
            embed = discord.Embed(title=f"🚨 {ticker} Buy Signal (Daily)", color=0x00FF00)
            embed.description = f"**SMA Alignment Confirmed** (9 > 21 > 50 > 200)\n**Price:** `${result['price']:,.2f}`"
            embed.add_field(name="🛑 Resistance", value=f"`${result['r1']:,.2f}`", inline=True)
            embed.add_field(name="🟢 Support", value=f"`${result['s1']:,.2f}`", inline=True)
            await ctx.send(embed=embed)
            
        await asyncio.sleep(2)
            
    if found_signals == 0:
        await ctx.send("✅ Scan complete. No new alignments today.")
    else:
        await ctx.send(f"✅ Scan complete. Found {found_signals} setups!")

# --- ORIGINAL SLASH COMMAND ---
@bot.tree.command(name="scan_now", description="Force the bot to scan the watchlist")
async def scan_now(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    found_signals = 0
    channel = bot.get_channel(CHANNEL_ID)
    
    for ticker in WATCHLIST:
        result = analyze_stock(ticker)
        if result:
            found_signals += 1
            embed = discord.Embed(title=f"🚨 {ticker} Buy Signal (Daily)", color=0x00FF00)
            embed.description = f"**SMA Alignment Confirmed** (9 > 21 > 50 > 200)\n**Price:** `${result['price']:,.2f}`"
            embed.add_field(name="🛑 Resistance", value=f"`${result['r1']:,.2f}`", inline=True)
            embed.add_field(name="🟢 Support", value=f"`${result['s1']:,.2f}`", inline=True)
            await channel.send(embed=embed)
            
        await asyncio.sleep(2)
            
    if found_signals == 0:
        await interaction.followup.send("✅ Scan complete. No new alignments today.")
    else:
        await interaction.followup.send(f"✅ Scan complete. Found {found_signals} setups!")

if __name__ == '__main__':
    Thread(target=run_server).start()
    bot.run(TOKEN)
