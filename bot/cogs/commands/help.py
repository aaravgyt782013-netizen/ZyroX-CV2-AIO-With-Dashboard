import discord
from discord.ext import commands
from discord import app_commands
from difflib import get_close_matches
from contextlib import suppress
import asyncio

from core import Context
from core.zyrox import zyrox
from core.Cog import Cog
from utils.Tools import *
from utils.Tools import getConfig
from utils.cv2 import CV2, CV2Embed
from utils.config import serverLink, BotName, BRAND_NAME
from utils import help as vhelp
from utils import Paginator, FieldPagePaginator
from utils.emoji import *

color = 0xFF0000
client = zyrox()


class HelpCommand(commands.HelpCommand):
    async def send_ignore_message(self, ctx, ignore_type: str):
        if ignore_type == "channel":
            await ctx.reply("This channel is ignored.", mention_author=False)
        elif ignore_type == "command":
            await ctx.reply(f"{ctx.author.mention} This Command, Channel, or You have been ignored here.", delete_after=6)
        elif ignore_type == "user":
            await ctx.reply("You are ignored.", mention_author=False)

    async def _allowed(self, ctx):
        try:
            if not await blacklist_check().predicate(ctx):
                return False
            if not await ignore_check().predicate(ctx):
                await self.send_ignore_message(ctx, "command")
                return False
        except Exception:
            pass
        return True

    async def on_help_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            return
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        with suppress(Exception):
            await ctx.reply(f"❌ Help menu error: `{error}`", mention_author=False)

    async def command_not_found(self, string: str) -> None:
        ctx = self.context
        if not await self._allowed(ctx):
            return
        cmds = [str(cmd) for cmd in self.context.bot.walk_commands()]
        matches = get_close_matches(string, cmds)
        suggestion = f"\nDid you mean `{ctx.prefix}{matches[0]}`?" if matches else ""
        embed = CV2Embed(
            title=f"{BotName} Helper",
            description=f">>> **Ops! Command not found with the name** `{string}`.{suggestion}",
            color=color,
        )
        await ctx.reply(view=embed, mention_author=True)

    async def send_bot_help(self, mapping):
        ctx = self.context
        if not await self._allowed(ctx):
            return

        loading_embed = CV2(f"{LOADINGRED} Loading help Menu...")
        loading_msg = await ctx.reply(view=loading_embed)
        await asyncio.sleep(2)
        with suppress(discord.NotFound):
            await loading_msg.delete()

        data = await getConfig(ctx.guild.id) if ctx.guild else {"prefix": "."}
        prefix = data.get("prefix", ".")

        # Keep the original category system, while ensuring the newly added
        # Embed and TempVoice categories are available when those cogs exist.
        mapping = dict(mapping)
        for cog_name in ("Embed", "TempVoice"):
            cog = ctx.bot.get_cog(cog_name)
            if cog is not None:
                mapping[cog] = list(cog.get_commands())

        # This is the original LightCore home page layout/content.
        embed = CV2Embed(
            description=(
                f"**{ARROWRED} __Start {BotName} Today__**\n"
                f"**{ZARROW} Type {prefix}antinuke enable**\n"
                f"**{ZARROW} Server Prefix:** `{prefix}`\n"
                f"**{ZARROW} Total Commands:** `{len(set(ctx.bot.walk_commands()))}`\n"
            ),
            color=0xFF0000,
        )

        embed.add_field(
            name=f"{ZCLOUD} Main Features",
            value=f">>> \n {ZSAFE} `»` Security\n"
                  f" {ZBOT} `»` Automoderation\n"
                  f" {ZWRENCH} `»` Utility\n"
                  f" {MUSIC} `»` Music\n"
                  f" {WIFI} `»` Autoreact & responder\n"
                  f" {SWORD} `»` Moderation\n"
                  f" {ZPEOPLE} `»` Autorole & Invc\n"
                  f" {ZROCKET} `»` Fun\n"
                  f" {GAMES} `»` Games\n"
                  f" {ZBAN} `»` Ignore Channels\n"
                  f" {WIFI} `»` Server\n"
                  f" {ZUNMUTE} `»` Voice\n"
                  f" {SEED} `»` Welcomer\n"
                  f" {ZTADA} `»` Giveaway\n"
                  f" {TICKET} `»` Ticket {NEW}\n"
                  f" {ZPEOPLE} `»` Invite Tracker {NEW}\n"
        )

        embed.add_field(
            name=f" {ZMODULE} Extra Features",
            value=f">>> \n {CAST} `»` Advance Logging\n"
                  f" {STAR} `»` Vanityroles\n"
                  f" {ZCOUNTING} `»` Counting {NEW}\n"
                  f" {SYSTEM} `»` J2C {NEW}\n"
                  f" {ZAI} `»` AI {NEW}\n"
                  f" {BOOST} `»` Boost {NEW}\n"
                  f" {LEVEL_UP} `»` Leveling {NEW}\n"
                  f" {PIN} `»` Sticky {NEW}\n"
                  f" {THUNDER} `»` Verification {NEW}\n"
                  f" {LOCK} `»` Encryption {NEW}\n"
                  f" {MINECRAFT} `»` Minecraft {NEW}\n"
                  f" {MESSAGE} `»` Joindm {NEW}\n"
                  f" {ZCIRCLE} `»` Birthday {NEW}\n"
                  f" {ZCIRCLE_ALT1} `»` Customrole\n"
        )

        embed.add_field(
            name="⚡ Quick Commands",
            value=(
                f"\`{prefix}help\` • Open this menu\n"
                f"\`{prefix}play <song>\` • Play music\n"
                f"\`{prefix}embed add <name>\` • Create a saved embed\n"
                f"\`{prefix}embed list\` • List saved embeds\n"
                f"\`{prefix}ticket setup\` • Configure tickets\n"
                f"\`{prefix}tempvoice setup\` • Configure TempVoice"
            ),
            inline=False,
        )

        embed.set_footer(text=f"Requested By {ctx.author} | [Support]({serverLink})")

        try:
            view = vhelp.View(mapping=mapping, ctx=ctx, homeembed=embed, ui=2)
            await ctx.reply(view=view, mention_author=False)
        except Exception as exc:
            fallback = CV2Embed(
                title=f"{BotName} Help",
                description=(
                    f"Prefix: `{prefix}`\n\n"
                    f"Use `{prefix}<command>` to run the bot.\n"
                    f"TempVoice: `{prefix}tempvoice setup`\n"
                    f"Embed: `{prefix}embed`\n\n"
                    f"Help UI error: `{type(exc).__name__}`"
                ),
                color=color,
            )
            await ctx.reply(view=fallback, mention_author=False)

    async def send_command_help(self, command):
        ctx = self.context
        if not await self._allowed(ctx):
            return
        description = command.help or command.description or "No help provided."
        embed = CV2Embed(description=f">>> {description}", color=color)
        aliases = " & ".join(command.aliases)
        embed.add_field(name="**Alt cmd**", value=f"```{aliases}```" if aliases else "No Alt cmd", inline=False)
        embed.add_field(name="**Usage**", value=f"```{ctx.prefix}{command.signature}```")
        embed.set_author(name=f"{command.qualified_name.title()} Command")
        embed.set_footer(text="<[] = optional | < > = required • Use Prefix Before Commands.")
        await ctx.reply(view=embed, mention_author=False)

    def get_command_signature(self, command: commands.Command) -> str:
        parent = command.full_parent_name
        aliases = " | ".join(command.aliases)
        if aliases:
            name = f"[{command.name} | {aliases}]"
        else:
            name = command.name
        if parent:
            name = f"{parent} {name}"
        return f"{name} {command.signature}".strip()

    async def send_group_help(self, group):
        ctx = self.context
        if not await self._allowed(ctx):
            return
        entries = [
            (f"`{ctx.prefix}{cmd.qualified_name}`", cmd.short_doc or "No description available")
            for cmd in group.commands
        ]
        embeds = FieldPagePaginator(
            entries=entries,
            title=f"{group.qualified_name.title()} [{len(group.commands)}]",
            description="< > Duty | [ ] Optional\n",
            per_page=4,
        ).get_pages()
        await Paginator(ctx, embeds).paginate()

    async def send_cog_help(self, cog):
        ctx = self.context
        if not await self._allowed(ctx):
            return
        entries = [
            (f"> `{ctx.prefix}{cmd.qualified_name}`", f"-# Description : {cmd.short_doc or ''}\n\u200b")
            for cmd in cog.get_commands()
        ]
        paginator = Paginator(
            source=FieldPagePaginator(
                entries=entries,
                title=f"{BRAND_NAME}'s {cog.qualified_name.title()} ({len(cog.get_commands())})",
                description="`<..> Required | [..] Optional`\n\n",
                color=color,
                per_page=4,
            ),
            ctx=ctx,
        )
        await paginator.paginate()


class Help(Cog, name="help"):
    def __init__(self, client: zyrox):
        self._original_help_command = client.help_command
        attributes = {
            "name": "help",
            "aliases": ["h"],
            "cooldown": commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.user),
            "help": "Shows help about bot, a command, or a category",
        }
        client.help_command = HelpCommand(command_attrs=attributes)
        client.help_command.cog = self

    async def cog_unload(self):
        self.help_command = self._original_help_command
