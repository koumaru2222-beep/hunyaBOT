import threading
import os
import discord
from discord.ext import commands
from flask import Flask, request

from bot.config import BOT_TOKEN
from bot.cogs.auth import auth_codes, save

# -----------------
# Flask
# -----------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")  # Discord user_id

    if not code or not state:
        return "認証に失敗しました"

    auth_codes[state] = code
    save("auth_codes", auth_codes)

    return "✅ 認証完了しました。Discordに戻ってください。"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# -----------------
# Discord Bot
# -----------------
class AvanzareMk2(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.load_extension("bot.cogs.auth")
        await self.tree.sync()

    async def on_ready(self):
        print(f"Login: {self.user}")

# -----------------
# Entry point
# -----------------
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot = AvanzareMk2()
    bot.run(BOT_TOKEN)
