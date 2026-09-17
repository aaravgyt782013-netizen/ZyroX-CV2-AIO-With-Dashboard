from __future__ import annotations

import discord
from discord.ext import commands

from utils.Tools import blacklist_check, ignore_check


class Purge(commands.Cog):
    """Reliable purge command for prefix and slash usage."""

    def __init__(self, bot):
        self.bot = bot
        # The old Message cog registered `purge` only as an alias of `clear`.
        # Replace that alias with this dedicated command.
        bot.remove_command("purge")

    @commands.hybrid_command(name="purge", description="Delete recent messages from this channel.")
    @commands.guild_only()
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        """Delete up to 2000 recent messages."""
        if amount < 1:
            return await ctx.send("❌ Amount must be at least **1**.", delete_after=5)
        if amount > 2000:
            return await ctx.send("❌ You can purge a maximum of **2000 messages** at once.", delete_after=5)

        # Prefix commands have a real trigger message; slash commands do not.
        before = ctx.message if ctx.message is not None else None

        try:
            deleted = await ctx.channel.purge(limit=amount, before=before)
        except discord.Forbidden:
            return await ctx.send("❌ I need the **Manage Messages** permission to purge messages.")
        except discord.HTTPException:
            return await ctx.send("❌ Discord rejected the purge request. Try a smaller amount.")

        await ctx.send(
            f"✅ Successfully deleted **{len(deleted)}** message{'s' if len(deleted) != 1 else ''}.",
            delete_after=5,
        )


async def setup(bot):
    await bot.add_cog(Purge(bot))
