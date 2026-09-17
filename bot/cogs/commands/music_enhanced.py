import re
import asyncio
import wavelink
import discord
from discord.ext import commands

from .music import Music as BaseMusic, MusicControlView
from utils.cv2 import CV2, build_container
from discord.ui import Button, LayoutView, TextDisplay, Separator, ActionRow
from utils.config import BRAND_NAME


YOUTUBE_WATCH_RE = re.compile(r"https?://(?:www\.|m\.|music\.)?youtube\.com/watch\?[^\s>]*v=([A-Za-z0-9_-]+)", re.I)
YOUTUBE_SHORT_RE = re.compile(r"https?://youtu\.be/([A-Za-z0-9_-]+)", re.I)
YOUTUBE_MUSIC_RE = re.compile(r"https?://music\.youtube\.com/watch\?([^\s>]+)", re.I)


class EnhancedMusic(BaseMusic):
    """LightCore music layer: direct YouTube URLs + a fresh control panel per track."""

    @staticmethod
    def normalize_youtube_url(query: str) -> str:
        query = query.strip()

        # YouTube Music watch links are normalized to a normal YouTube watch URL.
        # This keeps the exact video ID while allowing Lavalink's YouTube source to resolve it.
        match = YOUTUBE_MUSIC_RE.match(query)
        if match:
            params = match.group(1)
            video = re.search(r"(?:^|&)v=([A-Za-z0-9_-]+)", params, re.I)
            if video:
                return f"https://www.youtube.com/watch?v={video.group(1)}"

        if YOUTUBE_SHORT_RE.fullmatch(query):
            return query

        if YOUTUBE_WATCH_RE.fullmatch(query):
            return query

        return query

    async def play_source(self, ctx, query):
        # Accept direct youtube.com, youtu.be and music.youtube.com links.
        # Non-YouTube searches continue through the original music implementation.
        query = self.normalize_youtube_url(query)
        return await super().play_source(ctx, query)

    async def display_player_embed(self, player, track, ctx, autoplay=False):
        # Always send a brand-new panel. We intentionally do not edit/reuse the
        # previous panel so every newly started song gets its own controls.
        if not ctx or not getattr(ctx, "channel", None):
            return
        try:
            await ctx.send(view=MusicControlView(player, ctx, track, autoplay))
        except (discord.HTTPException, discord.Forbidden):
            pass

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """Send the same music control panel whenever Lavalink actually starts a track."""
        player = payload.player
        track = payload.track
        ctx = getattr(player, "ctx", None)
        if not ctx or not track:
            return

        autoplay = False
        try:
            # A track started by Lavalink after the previous one ended is still
            # considered normal playback; the panel itself remains identical.
            await self.display_player_embed(player, track, ctx, autoplay=autoplay)
        except Exception:
            pass

    async def on_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Advance playback without creating a second panel; track_start owns panels."""
        player = payload.player
        ctx = getattr(player, "ctx", None)
        if not player:
            return

        if player.queue.mode == wavelink.QueueMode.loop:
            await player.play(payload.track)
            return

        if not player.queue.is_empty:
            next_track = await player.queue.get_wait()
            await player.play(next_track)
            return

        if player.autoplay == wavelink.AutoPlayMode.enabled:
            # Wavelink/Lavalink handles recommendation/autoplay selection.
            # Give it a moment to transition before checking the player again.
            await asyncio.sleep(2)
            if player.current:
                return
            if ctx:
                await ctx.send(view=CV2("No suitable track found for autoplay."))
            return

        try:
            await player.disconnect()
        except Exception:
            pass

        if ctx:
            try:
                support = Button(label="Support", style=discord.ButtonStyle.link, url="https://discord.gg/Ehmqr5drSz")
                view = LayoutView(timeout=None)
                view.add_item(build_container(
                    TextDisplay("**Queue Ended**"),
                    Separator(visible=True),
                    TextDisplay("All tracks have been played, leaving the voice channel."),
                    Separator(visible=True),
                    ActionRow(support),
                    Separator(visible=True),
                    TextDisplay(f"*Thanks for choosing {BRAND_NAME}!*")
                ))
                await ctx.send(view=view)
            except Exception:
                pass
