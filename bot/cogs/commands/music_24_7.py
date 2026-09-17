"""LightCore 24/7 music resilience layer.

Keeps Wavelink/Lavalink music running through normal track transitions,
transient track failures and node/voice websocket reconnects.  This is a
separate cog so the existing music UI and commands remain intact.
"""

import asyncio
import os
import wavelink
from discord.ext import commands


class Music247(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.retry_tasks = {}

    async def _recover(self, player: wavelink.Player, track=None):
        if not player or not player.guild:
            return

        guild_id = player.guild.id
        old = self.retry_tasks.get(guild_id)
        if old and not old.done():
            return

        async def worker():
            for delay in (2, 5, 10):
                await asyncio.sleep(delay)
                try:
                    current = player.current or track
                    if not current:
                        return

                    # If playback recovered by itself, do nothing.
                    if player.playing:
                        return

                    # Keep the same player/voice connection whenever possible.
                    await player.play(current, add_history=False)
                    return
                except Exception:
                    continue

        self.retry_tasks[guild_id] = asyncio.create_task(worker())

    @commands.Cog.listener()
    async def on_wavelink_track_exception(self, payload: wavelink.TrackExceptionEventPayload):
        if payload.player:
            await self._recover(payload.player, payload.track)

    @commands.Cog.listener()
    async def on_wavelink_track_stuck(self, payload: wavelink.TrackStuckEventPayload):
        if payload.player:
            await self._recover(payload.player, payload.track)

    @commands.Cog.listener()
    async def on_wavelink_websocket_closed(self, payload: wavelink.WebsocketClosedEventPayload):
        if payload.player:
            await self._recover(payload.player, payload.player.current)

    @commands.Cog.listener()
    async def on_wavelink_node_disconnected(self, payload: wavelink.NodeDisconnectedEventPayload):
        # Wavelink itself retries disconnected nodes. We only make sure the
        # player's playback is restarted after the node becomes usable again.
        for player in list(payload.node.players.values()):
            await self._recover(player, player.current)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        # Clear stale recovery tasks once a node is healthy again.
        for guild_id, task in list(self.retry_tasks.items()):
            if task.done():
                self.retry_tasks.pop(guild_id, None)


async def setup(bot):
    await bot.add_cog(Music247(bot))
