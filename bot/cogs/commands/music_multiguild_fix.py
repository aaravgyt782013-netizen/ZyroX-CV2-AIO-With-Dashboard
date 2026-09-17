"""Multi-guild music connection fix for LightCore.

The music player must always be resolved from the current guild.  This patch
keeps each Discord server's voice/player state independent while retaining the
existing Music cog, queue, events, and UI.
"""

import asyncio
import discord
import wavelink

from utils.cv2 import CV2
from utils.emoji import WARNING, ZPLUS


_PATCHED = False


async def _play_source_per_guild(self, ctx, query):
    if not ctx.guild:
        return

    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send(view=CV2(f"{WARNING} you need to be in a voice channel to use this command."))
        return

    channel = ctx.author.voice.channel

    # IMPORTANT: resolve the voice player from THIS guild explicitly.
    # Never reuse a player/voice connection from another guild.
    vc = ctx.guild.voice_client

    try:
        if vc is None:
            vc = await channel.connect(cls=wavelink.Player, reconnect=True)
        elif vc.channel.id != channel.id:
            await ctx.send(view=CV2(f"You must be connected to {vc.channel.mention} to play."))
            return

        if not isinstance(vc, wavelink.Player):
            await ctx.send(view=CV2(f"{WARNING} The music player could not be initialized for this server."))
            return

        vc.ctx = ctx
        vc.autoplay = wavelink.AutoPlayMode.disabled

        tracks = await wavelink.Playable.search(query)
        if not tracks:
            await ctx.send(view=CV2("No results found."))
            return

        if isinstance(tracks, wavelink.Playlist):
            await vc.queue.put_wait(tracks.tracks)
            await ctx.send(view=CV2(
                f"{ZPLUS} Added playlist **{tracks.name}** with **{len(tracks.tracks)} songs** to the queue."
            ))

            if not vc.playing and not vc.paused:
                next_track = await vc.queue.get_wait()
                await vc.play(next_track)
                await self.display_player_embed(vc, next_track, ctx)
        else:
            track = tracks[0]
            await vc.queue.put_wait(track)
            await ctx.send(view=CV2(f"{ZPLUS} Added **{track.title}** to the queue."))

            if not vc.playing and not vc.paused:
                next_track = await vc.queue.get_wait()
                await vc.play(next_track)
                await self.display_player_embed(vc, next_track, ctx)

        # Keep inactivity tracking isolated by guild.
        asyncio.create_task(self.check_inactivity(ctx.guild.id))

    except (discord.ClientException, wavelink.WavelinkException) as exc:
        await ctx.send(view=CV2(f"{WARNING} Music connection error: `{exc}`"))
    except Exception as exc:
        await ctx.send(view=CV2(f"{WARNING} I couldn't start music in this server: `{exc}`"))


def patch_music():
    global _PATCHED
    if _PATCHED:
        return

    from .music import Music
    Music.play_source = _play_source_per_guild
    _PATCHED = True


async def setup(bot):
    # Importing the original Music module here is intentional: the patch works
    # regardless of whether the loader reaches this file before or after music.py.
    patch_music()
