"""LightCore music reliability layer.

Patches the existing Music cog without replacing its UI/commands:
- connects to several Lavalink v4 nodes
- keeps retry/resume behavior
- disables the old 2-minute inactivity disconnect
- enables autoplay after a successful play so playback can continue
"""

import asyncio
import json
import os
import wavelink
from discord.ext import commands


def _patch_music_class():
    # Import after Wavelink is available, then patch the existing cog before
    # cogs.setup() instantiates Music(bot).
    from .music import Music

    async def connect_nodes(self) -> None:
        raw = os.getenv("LAVALINK_NODES", "").strip()
        configs = []

        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    configs = parsed
            except Exception:
                configs = []

        # Safe fallbacks. Credentials are public node credentials and can be
        # overridden entirely with LAVALINK_NODES on Render.
        if not configs:
            configs = [
                {"host": "lavalinkv4.serenetia.com", "port": 443,
                 "password": "https://seretia.link/discord", "secure": True},
                {"host": "lava-v4.millohost.my.id", "port": 443,
                 "password": "https://discord.gg/mjS5J2K3ep", "secure": True},
                {"host": "lava-v4.ajieblogs.eu.org", "port": 80,
                 "password": "https://dsc.gg/ajidevserver", "secure": False},
            ]

        nodes = []
        for index, item in enumerate(configs):
            try:
                host = str(item["host"]).strip()
                port = int(item.get("port", 443))
                password = str(item["password"])
                secure = bool(item.get("secure", port == 443))
                uri = f"https://{host}:{port}" if secure else f"http://{host}:{port}"
                nodes.append(
                    wavelink.Node(
                        identifier=f"lightcore-{index + 1}",
                        uri=uri,
                        password=password,
                        retries=None,
                        resume_timeout=180,
                        inactive_player_timeout=None,
                    )
                )
            except Exception as exc:
                print(f"[LightCore Music] Invalid Lavalink node config: {exc}")

        if not nodes:
            print("[LightCore Music] No Lavalink nodes configured.")
            return

        try:
            await wavelink.Pool.connect(
                nodes=nodes,
                client=self.client,
                cache_capacity=None,
            )
            print(f"[LightCore Music] Lavalink pool started with {len(nodes)} nodes.")
        except Exception as exc:
            print(f"[LightCore Music] Lavalink pool connection error: {exc}")

    async def check_inactivity(self, guild_id):
        # The original ZyroX music cog disconnected after 120 seconds when
        # alone in a voice channel. LightCore's 24/7 music mode must not do so.
        return

    original_play_source = Music.play_source

    async def play_source(self, ctx, query):
        last_error = None
        for attempt in range(3):
            try:
                await original_play_source(self, ctx, query)
                # The original method explicitly disables autoplay. Re-enable
                # it after a successful play so a queue can continue naturally.
                vc = ctx.voice_client
                if vc and vc.playing:
                    vc.autoplay = wavelink.AutoPlayMode.enabled
                return
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(1 + attempt * 2)
        if last_error:
            raise last_error

    Music.connect_nodes = connect_nodes
    Music.check_inactivity = check_inactivity
    Music.play_source = play_source


_patch_music_class()


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
