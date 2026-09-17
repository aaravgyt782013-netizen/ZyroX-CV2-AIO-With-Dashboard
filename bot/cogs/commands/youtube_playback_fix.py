"""LightCore YouTube URL playback compatibility patch.

Loaded before the Music cog is instantiated. It keeps the existing music
system/UI/queue intact while making direct youtube.com and music.youtube.com
links explicitly resolve through Lavalink's YouTube source.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

import wavelink

from utils.cv2 import CV2
from utils.emoji import WARNING, ZPLUS


_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


def _is_youtube_url(value: str) -> bool:
    try:
        parsed = urlsplit(value.strip())
        return parsed.scheme in ("http", "https") and parsed.hostname in _YOUTUBE_HOSTS
    except Exception:
        return False


def _normalize_youtube_url(value: str) -> str:
    """Normalize YouTube Music URLs to a normal YouTube host.

    youtube-source/Lavalink handles YouTube URLs more consistently when the
    URL is presented with the regular YouTube host. Query parameters such as
    v= and list= are preserved.
    """
    parsed = urlsplit(value.strip())
    if parsed.hostname == "music.youtube.com":
        return urlunsplit((parsed.scheme, "www.youtube.com", parsed.path, parsed.query, parsed.fragment))
    return value.strip()


def install(Music):
    original_play_source = Music.play_source

    async def play_source(self, ctx, query):
        query = query.strip()

        # Direct YouTube / YouTube Music links must be resolved as YouTube
        # URLs, not treated as a normal text search.
        if _is_youtube_url(query):
            query = _normalize_youtube_url(query)

            if not ctx.author.voice:
                await ctx.send(view=CV2(f"{WARNING} you need to be in a voice channel to use this command."))
                return

            vc = ctx.voice_client or await ctx.author.voice.channel.connect(cls=wavelink.Player)
            vc.ctx = ctx

            if vc.playing and vc.channel != ctx.author.voice.channel:
                await ctx.send(view=CV2(f"You must be connected to {vc.channel.mention} to play."))
                return

            try:
                # Explicitly select Lavalink's YouTube source for direct URLs.
                tracks = await wavelink.Playable.search(
                    query,
                    source=wavelink.enums.TrackSource.YouTube,
                )
            except Exception as exc:
                await ctx.send(view=CV2(f"{WARNING} YouTube link could not be loaded: `{type(exc).__name__}`"))
                return

            if not tracks:
                await ctx.send(view=CV2(f"{WARNING} No playable track was found for that YouTube link."))
                return

            if isinstance(tracks, wavelink.Playlist):
                await vc.queue.put_wait(tracks.tracks)
                await ctx.send(view=CV2(
                    f"{ZPLUS} Added YouTube playlist **{tracks.name}** with **{len(tracks.tracks)} songs** to the queue."
                ))
                if not vc.playing:
                    track = await vc.queue.get_wait()
                    await vc.play(track)
                    await self.display_player_embed(vc, track, ctx)
            else:
                track = tracks[0]
                await vc.queue.put_wait(track)
                await ctx.send(view=CV2(f"{ZPLUS} Added [{track.title}]({track.uri}) to the queue."))
                if not vc.playing:
                    track = await vc.queue.get_wait()
                    await vc.play(track)
                    await self.display_player_embed(vc, track, ctx)
            return

        # Preserve all existing search/Spotify/other-platform behavior.
        return await original_play_source(self, ctx, query)

    Music.play_source = play_source
    return Music
