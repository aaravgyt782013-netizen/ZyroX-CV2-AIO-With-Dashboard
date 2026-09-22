"""LightCore music reliability layer with a bot-wide beta notice."""

import asyncio
import json
import os
import re
import wavelink
from discord.ext import commands


def _normalize_youtube_url(query: str) -> str:
    query = query.strip()
    match = re.fullmatch(r"https?://music\.youtube\.com/watch\?([^\s>]+)", query, re.I)
    if match:
        video = re.search(r"(?:^|&)v=([A-Za-z0-9_-]+)", match.group(1), re.I)
        if video:
            return f"https://www.youtube.com/watch?v={video.group(1)}"
    return query


def _patch_music_class():
    from .music import Music

    # Keep Music.connect_nodes from music.py. It discovers the current
    # healthy Lavalink list and ignores stale nodes; do not override it here.
    async def check_inactivity(self, guild_id):
        return

    original_play_source = Music.play_source

    async def play_source(self, ctx, query):
        query = _normalize_youtube_url(query)
        last_error = None
        for attempt in range(3):
            try:
                await original_play_source(self, ctx, query)
                vc = ctx.voice_client
                if vc and vc.playing:
                    vc.autoplay = wavelink.AutoPlayMode.enabled
                return
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(1 + attempt * 2)
        if last_error:
            raise last_error

    async def on_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player:
            return
        if player.queue.mode == wavelink.QueueMode.loop:
            await player.play(payload.track)
            return
        if not player.queue.is_empty:
            await player.play(await player.queue.get_wait())
            return
        if player.autoplay == wavelink.AutoPlayMode.enabled:
            await asyncio.sleep(2)
            if player.current:
                return
            ctx = getattr(player, "ctx", None)
            if ctx:
                try:
                    await ctx.send("No suitable track found for autoplay.")
                except Exception:
                    pass
            return
        try:
            await player.disconnect()
        except Exception:
            pass

    Music.check_inactivity = check_inactivity
    Music.play_source = play_source
    Music.on_track_end = on_track_end


_patch_music_class()


class Music247(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.retry_tasks = {}

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload):
        player = payload.player
        track = payload.track
        ctx = getattr(player, "ctx", None)
        if not player or not track or not ctx:
            return
        try:
            from .music import MusicControlView
            from discord.ui import TextDisplay
            view = MusicControlView(player, ctx, track, False)
            view.add_item(TextDisplay(
                "🧪 **BOT IS IN BETA TESTING**\n"
                "Found a bug? Please report it in the **LightCore support server**."
            ))
            await ctx.send(view=view)
        except Exception as exc:
            print(f"[LightCore Music] Could not send track control panel: {exc}")

    async def _recover(self, player: wavelink.Player, track=None):
        if not player or not player.guild:
            return
        guild_id = player.guild.id
        old = self.retry_tasks.get(guild_id)
        if old and not old.done():
            return
        async def worker():
            for delay in (2, 5, 10, 20):
                await asyncio.sleep(delay)
                try:
                    current = player.current or track
                    if not current or player.playing:
                        return
                    await player.play(current, add_history=False)
                    return
                except Exception:
                    continue
        self.retry_tasks[guild_id] = asyncio.create_task(worker())

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload):
        if payload.player:
            await self._recover(payload.player, payload.track)

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload):
        if payload.player:
            await self._recover(payload.player, payload.track)

    @commands.Cog.listener()
    async def on_wavelink_websocket_closed(self, payload):
        if payload.player:
            await self._recover(payload.player, payload.player.current)

    @commands.Cog.listener()
    async def on_wavelink_node_disconnected(self, payload):
        for player in list(payload.node.players.values()):
            await self._recover(player, player.current)


async def setup(bot):
    await bot.add_cog(Music247(bot))
