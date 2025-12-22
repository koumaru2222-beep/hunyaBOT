import discord
from discord.ext import commands
from discord.ui import View, Button

class RolePanelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ===============================
    # ロールパネル View
    # ===============================
    class RolePanelView(View):
        def __init__(self, roles):
            super().__init__(timeout=None)

            for role in roles:
                button = Button(label=role.name)

                async def callback(interaction: discord.Interaction, r=role):
                    if r in interaction.user.roles:
                        await interaction.user.remove_roles(r)
                    else:
                        await interaction.user.add_roles(r)

                    await interaction.response.send_message(
                        "✅ ロールを更新しました",
                        ephemeral=True
                    )

                button.callback = callback
                self.add_item(button)

    # ===============================
    # /role_panel コマンド
    # ===============================
    @discord.app_commands.command(name="role_panel")
    async def role_panel(
        self,
        interaction: discord.Interaction,
        r1: discord.Role,
        r2: discord.Role = None,
        r3: discord.Role = None,
        r4: discord.Role = None,
        r5: discord.Role = None,
    ):
        roles = [r for r in [r1, r2, r3, r4, r5] if r]

        await interaction.response.send_message(
            "ロールを選択してください",
            view=self.RolePanelView(roles)
        )

async def setup(bot):
    await bot.add_cog(RolePanelCog(bot))
