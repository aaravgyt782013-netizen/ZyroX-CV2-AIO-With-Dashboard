# ╔══════════════════════════════════════════════════════════════════╗
# ║                         LIGHTCORE                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import discord
from utils.emoji import ZSAFE
from discord.ext import commands


class _antinuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    """Antinuke commands"""

    def help_custom(self):
        emoji = ZSAFE
        label = "Antinuke"
        description = "Show you commands for Antinuke and server security"
        return emoji, label, description

    @commands.group()
    async def __Antinuke__(self, ctx: commands.Context):
        """Antinuke security commands."""
        pass
