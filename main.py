import os
import discord
from discord.ext import commands
from flask import Flask, request
from threading import Thread
import yfinance as yf
import logging

# --- CONFIG ---
TOKEN = os.environ['DISCORD_TOKEN']
ladder_memory = {}

# --- WEB SERVER ---
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
        level_list = sorted([float(x.strip()) for x in raw_levels.split(',') if x.strip()])

        ladder_memory[ticker] = level_list
        print(f"✅ UPDATED: {ticker} -> {level_list}")
        return "Success", 200
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return "Error", 400

def run_server():
    # Render assigns a random port, we must read it from Environment
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- DISCORD BOT ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def ladder(ctx, ticker: str):
    ticker = ticker.strip().upper()
    if ticker not in ladder_memory:
        await ctx.send(f"⚠️ No levels for **{ticker}**. Please trigger TradingView alert.")
        return

    msg = await ctx.send(f"🔄 Checking {ticker}...")
    y_ticker = f"{ticker}-USD" if ticker in ['BTC', 'ETH', 'SOL'] else ticker

    try:
        current_price = yf.Ticker(y_ticker).fast_info['last_price']
    except:
        await msg.edit(content="❌ Error fetching price.")
        return

    levels = ladder_memory[ticker]
    supports = sorted([x for x in levels if x < current_price], reverse=True)[:3]
    resistances = sorted([x for x in levels if x > current_price])[:3]

    embed = discord.Embed(title=f"Levels for {ticker}", color=0x2b2d31)
    embed.description = f"**Price:** `{current_price:,.2f}`"
    embed.add_field(name="🔴 Resistance", value="\n".join([f"`{r:,.2f}`" for r in resistances]) or "-", inline=True)
    embed.add_field(name="🟢 Support", value="\n".join([f"`{s:,.2f}`" for s in supports]) or "-", inline=True)

    await msg.delete()
    await ctx.send(embed=embed)

if __name__ == '__main__':
    Thread(target=run_server).start()
    bot.run(TOKEN)
