from __future__ import annotations

import asyncio
import os
import discord
from discord.ext import commands
from utils.config import OWNER_IDS


class ServerControl(commands.Cog):
    """Owner-only controls for the LightCore bot process."""

    def __init__(self, bot):
        self.bot = bot

    async def _owner_only(self, ctx: commands.Context) -> bool:
        if ctx.author.id in OWNER_IDS:
            return True
        await ctx.reply("Only the bot owner can use this command.", mention_author=False)
        return False

    @commands.command(name="restart")
    @commands.guild_only()
    async def restart(self, ctx: commands.Context):
        if not await self._owner_only(ctx):
            return
        await ctx.reply("♻️ Restarting LightCore...", mention_author=False)
        await asyncio.sleep(1)
        await self.bot.close()

    @commands.command(name="shutdown", aliases=["stopbot"])
    @commands.guild_only()
    async def shutdown(self, ctx: commands.Context):
        if not await self._owner_only(ctx):
            return
        await ctx.reply("🛑 Shutting down LightCore...", mention_author=False)
        await asyncio.sleep(1)
        await self.bot.close()


async def setup(bot):
    await bot.add_cog(ServerControl(bot))
