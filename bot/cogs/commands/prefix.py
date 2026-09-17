from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.Tools import updateConfig


class Prefix(commands.Cog):
    """Per-server prefix management and prefix moderation commands."""

    def __init__(self, bot):
        self.bot = bot
        # Remove the old purge alias from the Message cog so this command is authoritative.
        bot.remove_command("purge")

    prefix = app_commands.Group(
        name="prefix",
        description="Manage the bot prefix for this server.",
        guild_only=True,
    )

    @prefix.command(name="set", description="Set the bot's prefix for this server.")
    @app_commands.describe(new_prefix="The new prefix to use (1-5 characters).")
    @app_commands.checks.has_permissions(administrator=True)
    async def prefix_set(self, interaction: discord.Interaction, new_prefix: str):
        new_prefix = new_prefix.strip()

        if not new_prefix:
            await interaction.response.send_message("❌ The prefix cannot be empty.", ephemeral=True)
            return
        if len(new_prefix) > 5:
            await interaction.response.send_message("❌ The prefix must be between **1 and 5 characters**.", ephemeral=True)
            return
        if new_prefix.isspace():
            await interaction.response.send_message("❌ The prefix cannot contain only spaces.", ephemeral=True)
            return

        await updateConfig(interaction.guild.id, {"prefix": new_prefix})
        await interaction.response.send_message(
            f"✅ Prefix updated successfully.\n\n"
            f"This server's prefix is now: **`{new_prefix}`**\n"
            f"Use **`{new_prefix}help`** to see the bot's commands."
        )

    @prefix_set.error
    async def prefix_set_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            message = "❌ You need the **Administrator** permission to change the server prefix."
        else:
            message = "❌ I couldn't change the server prefix. Please try again."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    async def _purge_access(self, ctx: commands.Context):
        """Allow the bot owner to purge in any server, or staff with Manage Messages."""
        if await self.bot.is_owner(ctx.author):
            return True
        return ctx.author.guild_permissions.manage_messages

    @commands.command(name="purge", aliases=["clear"])
    @commands.guild_only()
    @commands.check(_purge_access)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def purge(self, ctx: commands.Context, amount: int):
        """Delete recent messages using the server's configured prefix.

        The bot owner can use this command in any server. Other users need
        the Manage Messages permission.
        """
        if amount < 1:
            await ctx.send("❌ Amount must be at least **1**.", delete_after=5)
            return
        if amount > 2000:
            await ctx.send("❌ You can purge a maximum of **2000 messages** at once.", delete_after=5)
            return

        try:
            # Include the user's `.purge 10` command message when possible.
            deleted = await ctx.channel.purge(limit=amount + 1)
        except discord.Forbidden:
            await ctx.send("❌ I need the **Manage Messages** permission to purge messages.")
            return
        except discord.HTTPException:
            await ctx.send("❌ Discord rejected the purge request. Try a smaller amount.")
            return

        # The command message is included in the deletion count.
        count = max(0, len(deleted) - 1)
        await ctx.send(
            f"✅ Successfully purged **{count}** message{'s' if count != 1 else ''}.",
            delete_after=5,
        )

    @purge.error
    async def purge_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(
                "❌ You need the **Manage Messages** permission to use purge.",
                delete_after=5,
            )
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need the **Manage Messages** permission to use purge.", delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Usage: `{ctx.prefix}purge <amount>`", delete_after=5)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Amount must be a number. Usage: `{ctx.prefix}purge <amount>`", delete_after=5)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏳ Try again in **{error.retry_after:.1f}s**.", delete_after=5)
        else:
            await ctx.send("❌ I couldn't run the purge command. Please try again.", delete_after=5)


async def setup(bot):
    await bot.add_cog(Prefix(bot))
