import re, json, os
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands

DATA_DIR = "data"
INVITE_REGEX = r"(discord\.gg|discord\.com\/invite)\/\S+"
URL_REGEX = r"https?://[^\s]+"

def load(name, d):
    p = f"{DATA_DIR}/{name}.json"
    return json.load(open(p,"r",encoding="utf-8")) if os.path.exists(p) else d

def save(name, d):
    json.dump(d, open(f"{DATA_DIR}/{name}.json","w",encoding="utf-8"), indent=2, ensure_ascii=False)

invite_cfg = load("invite", {})

class InviteWatch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        gid = str(message.guild.id)
        cfg = invite_cfg.setdefault(gid, {"enabled":False,"ignore":[],"url_watch":False})

        if message.channel.id in cfg["ignore"]:
            return

        if cfg["enabled"] and re.search(INVITE_REGEX, message.content):
            await message.delete()
            await message.author.timeout(
                datetime.now(timezone.utc)+timedelta(minutes=10),
                reason="招待リンク送信"
            )

        if cfg["url_watch"] and re.search(URL_REGEX, message.content):
            await message.delete()
            await message.author.send("URLは禁止されています")

    @discord.app_commands.command(name="invite_watch")
    async def invite_watch(self, interaction: discord.Interaction, enabled: bool):
        cfg = invite_cfg.setdefault(str(interaction.guild.id), {"enabled":False,"ignore":[],"url_watch":False})
        cfg["enabled"] = enabled
        save("invite", invite_cfg)
        await interaction.response.send_message("設定しました", ephemeral=True)

async def setup(bot):
    await bot.add_cog(InviteWatch(bot))
