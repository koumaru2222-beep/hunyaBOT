import threading
import discord
from discord.ext import commands
from flask import Flask

from config import BOT_TOKEN

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot running"

@app.route("/callback")
def callback():
    from flask import request
    return f"認証コード取得：{request.args.get('code')}"

def run_flask():
    app.run(host="0.0.0.0", port=5000)

@bot.event
async def on_ready():
    await bot.tree.sync()
    await bot.change_presence(activity=discord.Game(name="/help"))
    print(f"起動完了: {bot.user}")

async def load_cogs():
    for cog in [
        "moderation",
        "auth",
        "ticket",
        "role_panel",
        "global_chat",
        "help",
    ]:
        await bot.load_extension(f"cogs.{cog}")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    import asyncio
    asyncio.run(load_cogs())
    bot.run(BOT_TOKEN)
