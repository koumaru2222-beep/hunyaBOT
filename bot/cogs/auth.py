import os
import json
import asyncio
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
from urllib.parse import quote

from bot.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

OWNER_ID = 123456789012345678  # ← 自分のDiscord IDに変更
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

AUTO_ROLES_PATH = os.path.join(DATA_DIR, "auto_roles.json")

# --------------------------
# JSONユーティリティ
# --------------------------
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --------------------------
# AuthCog
# --------------------------
class AuthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------- 自動ロール管理 ----------
    def load_auto_roles(self) -> dict[str, str]:
        return load_json(AUTO_ROLES_PATH, {})

    def save_auto_roles(self, data: dict[str, str]):
        save_json(AUTO_ROLES_PATH, data)

    # ---------- OAuth URL ----------
    def make_oauth_url(self, user_id: int, guild_id: int) -> str:
        redirect_uri = quote(f"{REDIRECT_URI}/callback", safe="")
        state = f"{user_id}:{guild_id}"
        return (
            "https://discord.com/api/oauth2/authorize"
            f"?client_id={CLIENT_ID}"
            f"&redirect_uri={redirect_uri}"
            "&response_type=code"
            "&scope=identify%20guilds"
            f"&state={state}"
        )

    # ---------- ボタン認証 ----------
    @app_commands.command(name="auth_button", description="ボタンで認証")
    async def auth_button(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        role_id = self.load_auto_roles().get(str(interaction.guild.id))
        if not role_id:
            await interaction.followup.send("⚠️ このサーバーに認証後付与ロールが設定されていません", ephemeral=True)
            return

        role = interaction.guild.get_role(int(role_id))
        if not role:
            await interaction.followup.send("⚠️ ロールが見つかりません", ephemeral=True)
            return

        # ボタン作成
        class AuthView(View):
            def __init__(self):
                super().__init__(timeout=None)

            @discord.ui.button(label="認証", style=discord.ButtonStyle.primary)
            async def auth_button(self, button: Button, btn_interaction: discord.Interaction):
                await btn_interaction.response.defer(ephemeral=True)

                member = btn_interaction.user
                # まずロール付与
                await member.add_roles(role, reason="ボタン認証開始")
                await btn_interaction.followup.send(f"✅ 認証用ロールを付与しました。60秒以内に認証されない場合は解除されます", ephemeral=True)
                print(f"[auth_button] {member} にロール {role.name} 付与")

                # 60秒待って認証済みか確認
                await asyncio.sleep(60)
                # 認証確認（ここでは簡易的にロールが残っていればOKとする）
                # 実際は OAuth 完了フラグを別途管理するのがベスト
                if role in member.roles:
                    try:
                        await member.remove_roles(role, reason="認証未完了のため自動解除")
                        print(f"[auth_button] {member} に付与したロールを自動解除")
                    except Exception as e:
                        print(f"[auth_button] ロール解除失敗: {e}")

        await interaction.followup.send("🔐 認証ボタンを押してください", view=AuthView(), ephemeral=True)

    # ---------- OAuth認証完了処理（Flaskなどから呼ぶ） ----------
    async def handle_oauth(self, code: str, user_id: int, guild_id: int):
        # アクセストークン取得
        async with aiohttp.ClientSession() as session:
            token_resp = await session.post(
                "https://discord.com/api/oauth2/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": f"{REDIRECT_URI}/callback",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_data = await token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                print(f"[handle_oauth] access_token取得失敗: {token_data}")
                return

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        try:
            member = await guild.fetch_member(user_id)
        except discord.NotFound:
            return

        role_id = self.load_auto_roles().get(str(guild_id))
        if not role_id:
            return

        role = guild.get_role(int(role_id))
        if not role:
            return

        # 認証完了 → ロール付与を確定（ここでは既に付与されていればそのまま維持）
        if role not in member.roles:
            await member.add_roles(role, reason="OAuth認証完了")
        print(f"[handle_oauth] {member} の認証完了、ロール維持/付与完了")

    # ---------- 管理コマンド ----------
    @app_commands.command(name="set_auth_role", description="認証後に付与するロールを設定")
    async def set_auth_role(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        data = self.load_auto_roles()
        data[str(interaction.guild.id)] = str(role.id)
        self.save_auto_roles(data)
        await interaction.followup.send(f"✅ 認証後ロールを **{role.name}** に設定しました", ephemeral=True)
        print(f"[set_auth_role] ギルド {interaction.guild.id} にロール {role.id} 設定完了")

# --------------------------
# setup
# --------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(AuthCog(bot))
