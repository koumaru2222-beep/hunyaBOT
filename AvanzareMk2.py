import os
import threading
import asyncio
import json
import discord
from discord.ext import commands
from flask import Flask, request

from bot.config import BOT_TOKEN

app = Flask(__name__)
DATA_DIR = "data"
AUTH_CODES = os.path.join(DATA_DIR, "auth_codes.json")
os.makedirs(DATA_DIR, exist_ok=True)


def load_codes():
    if os.path.exists(AUTH_CODES):
        with open(AUTH_CODES, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_codes(data):
    with open(AUTH_CODES, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


auth_codes = load_codes()

@app.route("/")
def home():
    return "OK"


@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state:
        return "❌ 認証失敗"

    user_id, guild_id = map(int, state.split(":"))
    auth_codes[state] = code
    save_codes(auth_codes)

    cog = bot.get_cog("AuthCog")
    asyncio.run_coroutine_threadsafe(
        cog.handle_oauth(code, user_id, guild_id),
        bot.loop
    )

    return "✅ 認証完了"


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.load_extension("bot.cogs.auth")
    await bot.tree.sync()
    print("Commands synced")

threading.Thread(target=run_flask, daemon=True).start()

bot.run(BOT_TOKEN)
