import json
import os
import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ui import View

from bot.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

# ===============================
# データ保存
# ===============================
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load(name, default):
    path = os.path.join(DATA_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save(name, data):
    with open(os.path.join(DATA_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

auth_data     = load("auth", {})          # {guild_id: role_id}
banned_guilds = load("banned_guilds", []) # [guild_id]
auth_codes    = load("auth_codes", {})    # {user_id: code}

# ===============================
# OAuth URL
# ===============================
def make_oauth_url(user_id: int):
    return (
        "https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        "&scope=identify%20guilds"
        f"&state={user_id}"
    )

# ===============================
# Cog
# ===============================
class AuthCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auth_loop.start()

    # ---------------------------
    # /auth
    # ---------------------------
    @discord.app_commands.command(name="auth", description="認証を開始します")
    async def auth(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        url = make_oauth_url(interaction.user.id)

        view = View(timeout=300)
        view.add_item(
            discord.ui.Button(
                label="認証する",
                style=discord.ButtonStyle.url,
                url=url
            )
        )

        await interaction.followup.send(
            "下のボタンから認証してください。",
            view=view,
            ephemeral=True
        )

    # ---------------------------
    # 自動認証ループ
    # ---------------------------
    @tasks.loop(seconds=5)
    async def auth_loop(self):
        for user_id, code in list(auth_codes.items()):
            user = self.bot.get_user(int(user_id))
            if not user:
                continue

            # token取得
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://discord.com/api/oauth2/token",
                    data={
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": REDIRECT_URI,
                    }
                ) as resp:
                    token = await resp.json()

            if "access_token" not in token:
                del auth_codes[user_id]
                save("auth_codes", auth_codes)
                continue

            access_token = token["access_token"]

            # guilds取得
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://discord.com/api/users/@me/guilds",
                    headers={"Authorization": f"Bearer {access_token}"}
                ) as resp:
                    guilds = await resp.json()

            user_guilds = {g["id"] for g in guilds}

            # 禁止サーバーチェック
            if any(b in user_guilds for b in banned_guilds):
                await user.send("❌ 禁止サーバーに参加しているため認証できません")
                del auth_codes[user_id]
                save("auth_codes", auth_codes)
                continue

            # ロール付与
            for guild in self.bot.guilds:
                member = guild.get_member(int(user_id))
                if not member:
                    continue

                role_id = auth_data.get(str(guild.id))
                role = guild.get_role(role_id) if role_id else None
                if role:
                    await member.add_roles(role)

            await user.send("✅ 認証が完了しました！")
            del auth_codes[user_id]
            save("auth_codes", auth_codes)

    # ---------------------------
    # 管理コマンド
    # ---------------------------
    @discord.app_commands.command(name="set_auth_role")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def set_auth_role(self, interaction: discord.Interaction, role: discord.Role):
        auth_data[str(interaction.guild.id)] = role.id
        save("auth", auth_data)
        await interaction.response.send_message("✅ 認証ロールを設定しました", ephemeral=True)

    @discord.app_commands.command(name="ban_server_add")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ban_server_add(self, interaction: discord.Interaction, guild_id: str):
        if guild_id not in banned_guilds:
            banned_guilds.append(guild_id)
            save("banned_guilds", banned_guilds)
        await interaction.response.send_message("✅ 禁止サーバーを追加しました", ephemeral=True)

# ===============================
# setup
# ===============================
async def setup(bot):
    await bot.add_cog(AuthCog(bot))
