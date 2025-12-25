import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ui import View
import json
import os

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# ===============================
# データ管理
# ===============================
def load(name, default):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save(name, data):
    with open(os.path.join(DATA_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

auth_data     = load("auth", {})
banned_guilds = load("banned_guilds", [])
auth_codes    = load("auth_codes", {})

# ===============================
# Cog
# ===============================
class AuthCog(commands.Cog):
    def __init__(self, bot, public_url):
        self.bot = bot
        self.public_url = public_url
        self.bot.session = aiohttp.ClientSession()
        self.auth_loop.start()

    def make_oauth_url(self, user_id):
        from bot.config import CLIENT_ID
        redirect_uri = f"{self.public_url}/callback"
        return (
            "https://discord.com/api/oauth2/authorize"
            f"?client_id={CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            "&response_type=code"
            "&scope=identify%20guilds"
            f"&state={user_id}"
        )

    @commands.Cog.listener()
    async def on_ready(self):
        print("AuthCog is ready")

    @commands.hybrid_command(name="auth", description="認証を開始します")
    async def auth(self, ctx):
        url = self.make_oauth_url(ctx.author.id)
        view = View(timeout=300)
        view.add_item(discord.ui.Button(label="認証する", style=discord.ButtonStyle.url, url=url))
        await ctx.send("下のボタンから認証してください。", view=view, ephemeral=True)

    # ---------------------------
    # 自動認証ループ
    # ---------------------------
    @tasks.loop(seconds=5)
    async def auth_loop(self):
        from bot.config import CLIENT_ID, CLIENT_SECRET
        for user_id, code in list(auth_codes.items()):
            user = self.bot.get_user(int(user_id))
            if not user:
                continue

            async with self.bot.session.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": f"{self.public_url}/callback",
                }
            ) as resp:
                token = await resp.json()

            if "access_token" not in token:
                del auth_codes[user_id]
                save("auth_codes", auth_codes)
                continue

            access_token = token["access_token"]

            # guilds取得
            async with self.bot.session.get(
                "https://discord.com/api/users/@me/guilds",
                headers={"Authorization": f"Bearer {access_token}"}
            ) as resp:
                guilds = await resp.json()

            user_guilds = {g["id"] for g in guilds}

            if any(b in user_guilds for b in banned_guilds):
                try:
                    await user.send("❌ 禁止サーバーに参加しているため認証できません")
                except discord.Forbidden:
                    pass
                del auth_codes[user_id]
                save("auth_codes", auth_codes)
                continue

            # ロール付与
            for guild in self.bot.guilds:
                try:
                    member = await guild.fetch_member(int(user_id))
                except discord.NotFound:
                    continue

                role_id = auth_data.get(str(guild.id))
                if not role_id:
                    continue

                role = guild.get_role(role_id)
                if role:
                    try:
                        await member.add_roles(role)
                    except discord.Forbidden:
                        print(f"権限不足: {guild.name} の {role.name}")
                    except discord.HTTPException as e:
                        print(f"ロール付与失敗: {e}")

            try:
                await user.send("✅ 認証が完了しました！")
            except discord.Forbidden:
                pass

            del auth_codes[user_id]
            save("auth_codes", auth_codes)

    @auth_loop.before_loop
    async def before_auth_loop(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.bot.loop.create_task(self.bot.session.close())
