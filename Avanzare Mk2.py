import threading
import discord
from discord.ext import commands
from bot.web import app
from bot.config import BOT_TOKEN

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Login: {bot.user}")

async def load_cogs():
    import os
    for f in os.listdir("cogs"):
        if f.endswith(".py"):
            await bot.load_extension(f"cogs.{f[:-3]}")

def run_flask():
    app.run(host="0.0.0.0")

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.loop.create_task(load_cogs())
    bot.run(BOT_TOKEN)
