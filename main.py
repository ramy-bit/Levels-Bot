import os
import discord
from discord.ext import commands, tasks
import yfinance as yf
import asyncio
from threading import Thread
from flask import Flask

# --- CONFIG ---
TOKEN = os.environ.get('DISCORD_TOKEN')
CHANNEL_ID = 1332824647970816041 

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
def home(): return "OK", 200
@app.route('/webhook', methods=['POST'])
def webhook(): return "OK", 200

def run_server():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)

# --- THE MATH ENGINE ---
def analyze_stock(ticker):
    try:
        data = yf.Ticker(ticker).history(period="1y", interval="1d")
        if data.empty or len(data) < 200: return None 
        
        data['SMA_9'] = data['Close'].rolling(window=9).mean()
        data['SMA_21'] = data['Close'].rolling(window=21).mean()
        data['SMA_50'] = data['Close'].rolling(window=50).mean()
        data['SMA_200'] = data['Close'].rolling(window=200).mean()
        
        current_day = data.iloc[-1]
        prev_day = data.iloc[-2]
        
        curr_bull = (current_day['SMA_9'] > current_day['SMA_21'] > current_day['SMA_50'] > current_day['SMA_200'])
        prev_bull = (prev_day['SMA_9'] > prev_day['SMA_21'] > prev_day['SMA_50'] > prev_day['SMA_200'])
        
        if curr_bull and not prev_bull:
            day_high, day_low, close_price = current_day['High'], current_day['Low'], current_day['Close']
            pivot = (day_high + day_low + close_price) / 3
            return {"price": close_price, "r1": (2 * pivot) - day_low, "s1": (2 * pivot) - day_high}
        return None 
    except Exception:
        return None

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("✅ Slash commands re-enabled and synced successfully!")
    except Exception as e:
        print(f"⚠️ Could not sync slash commands: {e}")
        
    if not market_scanner.is_running():
        market_scanner.start()

# 🕵️‍♂️ THE TRACKER: This prints every message the bot sees to Render
@bot.event
async def on_message(message):
    if message.author == bot.user: return
    print(f"👀 Bot saw a message: {message.content}")
    await bot.process_commands(message)

# --- COMMANDS ---
@bot.command(name="scan")
async def text_scan(ctx):
    print("🚀 Executing !scan...")
    await ctx.send("🕵️‍♂️ **Scanning the watchlist...** This will take about a minute.")
    found = 0
    for ticker in WATCHLIST:
        res = analyze_stock(ticker)
        if res:
            found += 1
            embed = discord.Embed(title=f"🚨 {ticker} Buy Signal (Daily)", color=0x00FF00, description=f"**Price:** `${res['price']:,.2f}`")
            embed.add_field(name="🛑 Resistance", value=f"`${res['r1']:,.2f}`")
            embed.add_field(name="🟢 Support", value=f"`${res['s1']:,.2f}`")
            await ctx.send(embed=embed)
        await asyncio.sleep(2)
    await ctx.send(f"✅ Scan complete. Found {found} setups!" if found else "✅ Scan complete. No new alignments today.")

@bot.tree.command(name="scan", description="Scan the market for SMA alignments")
async def slash_scan(interaction: discord.Interaction):
    print("🚀 Executing /scan...")
    await interaction.response.defer()
    found = 0
    for ticker in WATCHLIST:
        res = analyze_stock(ticker)
        if res:
            found += 1
            embed = discord.Embed(title=f"🚨 {ticker} Buy Signal (Daily)", color=0x00FF00, description=f"**Price:** `${res['price']:,.2f}`")
            embed.add_field(name="🛑 Resistance", value=f"`${res['r1']:,.2f}`")
            embed.add_field(name="🟢 Support", value=f"`${res['s1']:,.2f}`")
            await interaction.followup.send(embed=embed)
        await asyncio.sleep(2)
    await interaction.followup.send(f"✅ Scan complete. Found {found} setups!" if found else "✅ Scan complete. No new alignments today.")

# --- BACKGROUND SCANNER ---
@tasks.loop(hours=4)
async def market_scanner():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel: return
    for ticker in WATCHLIST:
        res = analyze_stock(ticker)
        if res:
            embed = discord.Embed(title=f"🚨 {ticker} Buy Signal (Daily)", color=0x00FF00, description=f"**Price:** `${res['price']:,.2f}`")
            embed.add_field(name="🛑 Resistance", value=f"`${res['r1']:,.2f}`")
            embed.add_field(name="🟢 Support", value=f"`${res['s1']:,.2f}`")
            await channel.send(embed=embed)
        await asyncio.sleep(2)

if __name__ == '__main__':
    Thread(target=run_server).start()
    bot.run(TOKEN)
