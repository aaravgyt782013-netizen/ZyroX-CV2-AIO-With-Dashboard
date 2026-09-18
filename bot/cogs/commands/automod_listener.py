from __future__ import annotations

import re
import os
import time
from collections import defaultdict, deque
from datetime import timedelta

import aiosqlite
import discord
from discord.ext import commands

DATABASE_PATH = "db/automod.db"
os.makedirs("db", exist_ok=True)

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
INVITE_RE = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord(?:app)?\.com/invite)/[A-Za-z0-9-]+", re.IGNORECASE)
SPOTIFY_RE = re.compile(r"(?:https?://)?open\.spotify\.com/", re.IGNORECASE)
GIF_RE = re.compile(r"(?:https?://)?(?:tenor\.com|giphy\.com)/", re.IGNORECASE)
EMOJI_RE = re.compile(
    r"<a?:[^:>]+:\d+|"
    r"[\U0001F1E6-\U0001F1FF]|[\U0001F300-\U0001FAFF]|"
    r"[\u2600-\u27BF]",
    re.UNICODE,
)

PUNISHMENT_TIMEOUTS = {
    "Anti spam": 12,
    "Anti caps": 1,
    "Anti link": 7,
    "Anti invites": 12,
    "Anti mass mention": 3,
    "Anti emoji spam": 1,
}


class AutomodListener(commands.Cog):
    """Enforces the Automod rules saved by the Automod command cog."""

    def __init__(self, bot):
        self.bot = bot
        self._spam_windows: dict[tuple[int, int], deque[float]] = defaultdict(deque)

    async def _enabled_rules(self, guild_id: int) -> set[str]:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT event FROM automod_punishments WHERE guild_id = ?",
                (guild_id,),
            ) as cursor:
                return {event for (event,) in await cursor.fetchall()}

    async def _ignored(self, message: discord.Message) -> bool:
        if not message.guild:
            return True

        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM automod_ignored WHERE guild_id = ? AND type = 'channel' AND id = ?",
                (message.guild.id, message.channel.id),
            ) as cursor:
                if await cursor.fetchone():
                    return True

            role_ids = [role.id for role in getattr(message.author, "roles", [])]
            if role_ids:
                placeholders = ",".join("?" for _ in role_ids)
                async with db.execute(
                    f"SELECT 1 FROM automod_ignored WHERE guild_id = ? AND type = 'role' AND id IN ({placeholders}) LIMIT 1",
                    (message.guild.id, *role_ids),
                ) as cursor:
                    if await cursor.fetchone():
                        return True

        return False

    async def _punishment(self, guild_id: int, event: str) -> str:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT punishment FROM automod_punishments WHERE guild_id = ? AND event = ?",
                (guild_id, event),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row and row[0] else "Mute"

    async def _log(self, guild: discord.Guild, message: discord.Message, event: str, punishment: str) -> None:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT log_channel FROM automod_logging WHERE guild_id = ?",
                (guild.id,),
            ) as cursor:
                row = await cursor.fetchone()

        if not row:
            return

        channel = guild.get_channel(row[0])
        if not channel:
            return

        embed = discord.Embed(
            title="Automod Action",
            description=(
                f"Rule: {event}\n"
                f"User: {message.author.mention} ({message.author.id})\n"
                f"Channel: {message.channel.mention}\n"
                f"Punishment: {punishment}"
            ),
            color=0xFF0000,
        )
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass

    async def _apply(self, message: discord.Message, event: str) -> None:
        guild = message.guild
        if not guild:
            return

        punishment = await self._punishment(guild.id, event)
        member = message.author

        try:
            if punishment == "Mute":
                minutes = PUNISHMENT_TIMEOUTS.get(event, 1)
                await member.timeout(
                    timedelta(minutes=minutes),
                    reason=f"LightCore Automod: {event}",
                )
            elif punishment == "Kick":
                if guild.me.guild_permissions.kick_members and member != guild.owner:
                    if member.top_role < guild.me.top_role:
                        await member.kick(reason=f"LightCore Automod: {event}")
            elif punishment == "Ban":
                if guild.me.guild_permissions.ban_members and member != guild.owner:
                    if member.top_role < guild.me.top_role:
                        await member.ban(reason=f"LightCore Automod: {event}")
        except (discord.Forbidden, discord.HTTPException):
            pass

        await self._log(guild, message, event, punishment)

    async def _trigger(self, message: discord.Message, event: str) -> bool:
        rules = await self._enabled_rules(message.guild.id)
        if event not in rules:
            return False

        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

        await self._apply(message, event)
        return True

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        if await self._ignored(message):
            return

        content = message.content or ""
        rules = await self._enabled_rules(message.guild.id)
        if not rules:
            return

        if "Anti spam" in rules:
            key = (message.guild.id, message.author.id)
            now = time.monotonic()
            window = self._spam_windows[key]
            window.append(now)
            while window and now - window[0] > 8:
                window.popleft()
            if len(window) > 5:
                window.clear()
                if await self._trigger(message, "Anti spam"):
                    return

        if "Anti caps" in rules and len(content) >= 45:
            letters = [c for c in content if c.isalpha()]
            if letters:
                caps_ratio = sum(c.isupper() for c in letters) / len(letters)
                if caps_ratio > 0.70:
                    if await self._trigger(message, "Anti caps"):
                        return

        if "Anti invites" in rules and INVITE_RE.search(content):
            if await self._trigger(message, "Anti invites"):
                return

        if "Anti link" in rules and URL_RE.search(content):
            if not INVITE_RE.search(content) and not SPOTIFY_RE.search(content) and not GIF_RE.search(content):
                if await self._trigger(message, "Anti link"):
                    return

        if "Anti mass mention" in rules:
            mention_count = len(message.mentions) + len(message.role_mentions)
            if mention_count > 4 or message.mention_everyone:
                if await self._trigger(message, "Anti mass mention"):
                    return

        if "Anti emoji spam" in rules and len(EMOJI_RE.findall(content)) > 5:
            await self._trigger(message, "Anti emoji spam")


async def setup(bot):
    await bot.add_cog(AutomodListener(bot))
