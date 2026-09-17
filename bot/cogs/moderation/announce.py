import re
import discord
from discord.ext import commands

from utils.Tools import blacklist_check, ignore_check
from utils.emoji import CROSS, TICK, ZWARNING


async def _announce(self, ctx, title: str, description: str, channel: discord.TextChannel, ping: str = "none"):
    """Send a rich announcement to a selected text channel.

    Prefix usage: .announce "Title" "Description" #channel @role
    The active per-server prefix is handled by the bot's normal prefix resolver.
    """
    if not ctx.guild:
        return await ctx.reply(f"{ZWARNING} This command can only be used in a server.", mention_author=False)
    if not ctx.author.guild_permissions.manage_messages:
        return await ctx.reply(f"{ZWARNING} You need **Manage Messages** to use announce.", mention_author=False)
    if not ctx.guild.me.guild_permissions.send_messages:
        return await ctx.reply(f"{ZWARNING} I cannot send messages in this server.", mention_author=False)

    ping_text = (ping or "none").strip()
    content = None
    allowed = discord.AllowedMentions.none()

    if ping_text.lower() in {"@everyone", "everyone"}:
        content = "@everyone"
        allowed = discord.AllowedMentions(everyone=True)
    elif ping_text.lower() in {"@here", "here"}:
        content = "@here"
        allowed = discord.AllowedMentions(everyone=True)
    else:
        role = None
        role_match = re.fullmatch(r"<@&?(\d+)>", ping_text)
        if role_match:
            role = ctx.guild.get_role(int(role_match.group(1)))
        elif ping_text.isdigit():
            role = ctx.guild.get_role(int(ping_text))
        if role is not None:
            content = role.mention
            allowed = discord.AllowedMentions(roles=[role])
        elif ping_text.lower() not in {"", "none", "no", "false", "off", "0"}:
            return await ctx.reply(f"{CROSS} Invalid ping. Use `none`, `@everyone`, `@here`, or a role mention/ID.", mention_author=False)

    if not title.strip():
        return await ctx.reply(f"{CROSS} The announcement title cannot be empty.", mention_author=False)
    if not description.strip():
        return await ctx.reply(f"{CROSS} The announcement description cannot be empty.", mention_author=False)

    embed = discord.Embed(title=title[:256], description=description[:4096], color=0xFF0000, timestamp=discord.utils.utcnow())
    if ctx.guild.icon:
        embed.set_author(name=f"{ctx.guild.name} • Announcement", icon_url=ctx.guild.icon.url)
    else:
        embed.set_author(name=f"{ctx.guild.name} • Announcement")
    embed.set_footer(text=f"Announced by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

    try:
        await channel.send(content=content, embed=embed, allowed_mentions=allowed)
    except discord.Forbidden:
        return await ctx.reply(f"{ZWARNING} I don't have permission to send messages or embeds in {channel.mention}.", mention_author=False)
    except discord.HTTPException as exc:
        return await ctx.reply(f"{CROSS} Discord rejected the announcement: `{exc}`", mention_author=False)

    confirm = discord.Embed(title=f"{TICK} Announcement Sent", description=f"Your announcement was sent to {channel.mention}.", color=0xFF0000)
    if content:
        confirm.add_field(name="Ping", value=content, inline=False)
    await ctx.reply(embed=confirm, mention_author=False)


announce = commands.hybrid_command(
    name="announce",
    help="Creates a rich announcement and sends it to a selected channel.",
    usage="announce <title> <description> <channel> [ping]",
)(_announce)


def patch_moderation():
    """Attach the command to the existing Moderation cog so it appears under Moderation help."""
    from .moderation import Moderation
    commands_list = getattr(Moderation, "__cog_commands__", None)
    if commands_list is None:
        return
    if not any(getattr(command, "name", None) == "announce" for command in commands_list):
        commands_list.append(announce)
