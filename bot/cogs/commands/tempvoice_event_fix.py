from __future__ import annotations

import asyncio
import aiosqlite
import discord
from discord.ext import commands

DB = "tempvoice_data.db"


class TempVoiceEventFix(commands.Cog):
    """Reliable Join-to-Create listener for the TempVoice system."""

    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()
        bot.loop.create_task(self._install())

    async def _install(self):
        await self.bot.wait_until_ready()
        for _ in range(30):
            tempvoice = self.bot.get_cog("TempVoice")
            if tempvoice is not None:
                # The original listener can race with this fallback. Remove it
                # and use this single reliable handler instead.
                try:
                    self.bot.remove_listener(tempvoice.on_voice_state_update, "on_voice_state_update")
                except Exception:
                    pass
                return
            await asyncio.sleep(1)

    async def _get_setup(self, guild_id):
        async with aiosqlite.connect(DB) as db:
            async with db.execute(
                "SELECT join_id, category_id FROM setup WHERE guild_id=?",
                (guild_id,),
            ) as cursor:
                return await cursor.fetchone()

    async def _get_owner_channel(self, guild_id, owner_id):
        async with aiosqlite.connect(DB) as db:
            async with db.execute(
                "SELECT channel_id FROM channels WHERE guild_id=? AND owner_id=?",
                (guild_id, owner_id),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None

    async def _save_channel(self, channel_id, guild_id, owner_id):
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR REPLACE INTO channels VALUES(?,?,?)",
                (channel_id, guild_id, owner_id),
            )
            await db.commit()
        tempvoice = self.bot.get_cog("TempVoice")
        if tempvoice is not None:
            tempvoice.channels[channel_id] = {
                "guild_id": guild_id,
                "owner_id": owner_id,
            }

    async def _remove_channel(self, channel_id):
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
            await db.commit()
        tempvoice = self.bot.get_cog("TempVoice")
        if tempvoice is not None:
            tempvoice.channels.pop(channel_id, None)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot or member.guild is None:
            return

        # Join-to-Create handling.
        if after.channel is not None:
            setup = await self._get_setup(member.guild.id)
            if setup and after.channel.id == setup[0]:
                async with self._lock:
                    # If this member already owns a temporary VC, reuse it.
                    existing_id = await self._get_owner_channel(member.guild.id, member.id)
                    existing = member.guild.get_channel(existing_id) if existing_id else None
                    if isinstance(existing, discord.VoiceChannel):
                        try:
                            await member.move_to(existing, reason="TempVoice existing channel")
                        except discord.HTTPException:
                            pass
                        return

                    me = member.guild.me
                    if me is None:
                        return

                    perms = after.channel.permissions_for(me)
                    if not perms.manage_channels or not perms.move_members:
                        try:
                            await member.send(
                                "❌ TempVoice is configured, but I need **Manage Channels** and **Move Members** permissions."
                            )
                        except discord.HTTPException:
                            pass
                        return

                    category = member.guild.get_channel(setup[1]) if setup[1] else after.channel.category
                    try:
                        vc = await member.guild.create_voice_channel(
                            f"{member.display_name}'s VC",
                            category=category,
                            reason="TempVoice Join-to-Create",
                        )
                        await self._save_channel(vc.id, member.guild.id, member.id)
                        await vc.set_permissions(
                            member,
                            view_channel=True,
                            connect=True,
                            manage_channels=True,
                            move_members=True,
                        )
                        await member.move_to(vc, reason="TempVoice Join-to-Create")
                    except discord.Forbidden:
                        try:
                            await member.send(
                                "❌ I could not create your temporary voice channel. Please make sure LightCore has **Manage Channels** and **Move Members**."
                            )
                        except discord.HTTPException:
                            pass
                    except discord.HTTPException as exc:
                        print(f"TempVoice Join-to-Create error: {exc}")

        # Delete tracked temporary VCs as soon as they become empty.
        if before.channel is not None:
            tempvoice = self.bot.get_cog("TempVoice")
            tracked = getattr(tempvoice, "channels", {}) if tempvoice else {}
            if before.channel.id in tracked:
                await asyncio.sleep(0.5)
                if not before.channel.members:
                    try:
                        await before.channel.delete(reason="TempVoice empty")
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
                    await self._remove_channel(before.channel.id)


async def setup(bot):
    await bot.add_cog(TempVoiceEventFix(bot))
