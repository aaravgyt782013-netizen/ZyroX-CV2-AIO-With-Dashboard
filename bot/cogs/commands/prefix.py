from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.Tools import getConfig, updateConfig


class Prefix(commands.Cog):
    """Per-server prefix management."""

    def __init__(self, bot):
        self.bot = bot

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
            await interaction.response.send_message(
                "❌ The prefix cannot be empty.", ephemeral=True
            )
            return

        if len(new_prefix) > 5:
            await interaction.response.send_message(
                "❌ The prefix must be between **1 and 5 characters**.", ephemeral=True
            )
            return

        if new_prefix.isspace():
            await interaction.response.send_message(
                "❌ The prefix cannot contain only spaces.", ephemeral=True
            )
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


async def setup(bot):
    await bot.add_cog(Prefix(bot))
