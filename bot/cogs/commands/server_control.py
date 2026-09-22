import os
import sys
import discord
from discord.ext import commands
from utils.config import OWNER_IDS


class ServerControl(commands.Cog):
    """Owner-only process controls for the bot service."""

    def __init__(self, bot):
        self.bot = bot

    async def _owner_only(self, ctx):
        if ctx.author.id not in OWNER_IDS:
            await ctx.reply("❌ This command is owner-only.", mention_author=False)
            return False
        return True

    @commands.command(name="botrestart", help="Restart the LightCore bot service (owner only).")
    @commands.guild_only()
    async def restart(self, ctx):
        if not await self._owner_only(ctx):
            return

        await ctx.reply("🔄 Restarting LightCore...", mention_author=False)
        # Render/other process managers will start the process again after exit.
        await self.bot.close()
        os._exit(0)

    @commands.command(name="botstop", help="Stop the LightCore bot process (owner only).")
    @commands.guild_only()
    async def stop(self, ctx):
        if not await self._owner_only(ctx):
            return

        await ctx.reply("🛑 Stopping LightCore...", mention_author=False)
        await self.bot.close()
        os._exit(0)


async def setup(bot):
    await bot.add_cog(ServerControl(bot))
