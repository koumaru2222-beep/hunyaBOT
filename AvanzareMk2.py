import os
import json
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from urllib.parse import quote

from bot.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

OWNER_ID = 123456789012345678  # ←自分のID

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

BANNED_GUILDS_PATH = os.path.join(DATA_DIR, "banned_guilds.json")
AUTO_ROLES_PATH = os.path.join(DATA_DIR, "auto_roles.json")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class AuthCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ========= data =========
    def load_banned_guilds(self):
        return set(load_json(BANNED_GUILDS_PATH, []))

    def save_banned_guilds(self, data):
        save_json(BANNED_GUILDS_PATH, list(data))

    def load_auto_roles(self):
        return load_json(AUTO_ROLES_PATH, {})

    def save_auto_roles(self, data):
        save_json(AUTO_ROLES_PATH, data)

    # ========= OAuth =========
    def make_oauth_url(self, user_id: int, guild_id: int):
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

    @app_commands.command(name="auth", description="OAuth認証を行います")
    async def auth(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("❌ サーバー内で実行してください", ephemeral=True)
            return

        url = self.make_oauth_url(interaction.user.id, interaction.guild.id)
        await interaction.followup.send(f"🔐 認証URL\n{url}", ephemeral=True)

    # ========= OAuth handler =========
    async def handle_oauth(self, code: str, user_id: int, guild_id: int):
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
            token = await token_resp.json()
            access_token = token.get("access_token")
            if not access_token:
                return

            guilds_resp = await session.get(
                "https://discord.com/api/users/@me/guilds",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_guilds = await guilds_resp.json()

        banned = self.load_banned_guilds()
        if any(str(g["id"]) in banned for g in user_guilds):
            await self.ban_user(user_id, guild_id)
            return

        await self.give_auto_role(user_id, guild_id)

    async def ban_user(self, user_id: int, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        member = guild.get_member(user_id)
        if member:
            await member.ban(reason="禁止サーバー参加")

    async def give_auto_role(self, user_id: int, guild_id: int):
        roles = self.load_auto_roles()
        role_id = roles.get(str(guild_id))
        if not role_id:
            return

        guild = self.bot.get_guild(guild_id)
        member = guild.get_member(user_id) if guild else None
        role = guild.get_role(int(role_id)) if guild else None

        if member and role:
            await member.add_roles(role, reason="OAuth認証完了")

    # ========= 禁止サーバー管理 =========
    banned = app_commands.Group(name="banned", description="禁止サーバー管理")

    @banned.command(name="add")
    async def banned_add(self, interaction: discord.Interaction, guild_id: str):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ 権限なし", ephemeral=True)
            return
        data = self.load_banned_guilds()
        data.add(guild_id)
        self.save_banned_guilds(data)
        await interaction.response.send_message("✅ 追加しました", ephemeral=True)

    @banned.command(name="remove")
    async def banned_remove(self, interaction: discord.Interaction, guild_id: str):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ 権限なし", ephemeral=True)
            return
        data = self.load_banned_guilds()
        data.discard(guild_id)
        self.save_banned_guilds(data)
        await interaction.response.send_message("✅ 削除しました", ephemeral=True)

    # ========= ★ここが問題だった部分 =========
    @app_commands.command(
        name="set_auth_role",
        description="認証後に付与するロールを設定（管理者専用）"
    )
    async def set_auth_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ 管理者権限が必要です", ephemeral=True)
            return

        data = self.load_auto_roles()
        data[str(interaction.guild.id)] = str(role.id)
        self.save_auto_roles(data)

        await interaction.followup.send(
            f"✅ 認証後ロールを **{role.name}** に設定しました",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AuthCog(bot))
