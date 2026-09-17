# ╔══════════════════════════════════════════════════════════════════╗
# ║                                                                  ║
# ║   ░█▀▀░█▀█░█▀▄░█▀▀░█░█   ░█▀▄░█▀▀░█░█░█▀▀                     ║
# ║   ░█░░░█░█░█░█░█▀▀░▄▀▄   ░█░█░█▀▀░▀▄▀░▀▀█                     ║
# ║   ░▀▀▀░▀▀▀░▀▀░░▀▀▀░▀░▀   ░▀▀░░▀▀▀░░▀░░▀▀▀                     ║
# ║                                                                  ║
# ║            © 2026 CodeX Devs — All Rights Reserved              ║
# ║                                                                  ║
# ║   discord  ──  https://discord.gg/codexdev                      ║
# ║   youtube  ──  https://youtube.com/@CodeXDevs                   ║
# ║   github   ──  https://github.com/RayExo                        ║
# ║                                                                  ║
# ╚══════════════════════════════════════════════════════════════════╝

import asyncio
import discord
from discord.ext import commands
from typing import Union
import wavelink
from utils.Tools import *


class FilterCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_filters = {}
        self._stalled = {}
        self._retrying = set()
        self._audio_monitor = bot.loop.create_task(self._monitor_audio())
        self._prefix_migration = bot.loop.create_task(self._migrate_prefixes())

    def cog_unload(self):
        for task in (self._audio_monitor, self._prefix_migration):
            if not task.done():
                task.cancel()

    async def _migrate_prefixes(self):
        """Migrate the old default prefix to the new dot prefix."""
        await self.bot.wait_until_ready()
        for guild in list(self.bot.guilds):
            try:
                config = await getConfig(guild.id)
                if config.get("prefix") == ">":
                    await updateConfig(guild.id, {"prefix": "."})
            except Exception:
                continue

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            config = await getConfig(guild.id)
            if config.get("prefix") == ">":
                await updateConfig(guild.id, {"prefix": "."})
        except Exception:
            pass

    async def _monitor_audio(self):
        """Keep the Lavalink player gain stable and recover from a stalled stream."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await asyncio.sleep(10)
            for player in list(self.bot.voice_clients):
                try:
                    if not isinstance(player, wavelink.Player):
                        continue
                    if not player.is_connected() or not player.current:
                        self._stalled.pop(player.guild.id, None)
                        continue
                    if not player.playing or player.paused:
                        self._stalled.pop(player.guild.id, None)
                        continue

                    if getattr(player, "volume", 100) != 100:
                        await player.set_volume(100)

                    guild_id = player.guild.id
                    track_id = getattr(player.current, "identifier", None) or player.current.title
                    position = int(player.position)
                    previous = self._stalled.get(guild_id)

                    if previous and previous[0] == track_id and abs(position - previous[1]) < 250:
                        stalled_for = previous[2] + 1
                    else:
                        stalled_for = 0

                    self._stalled[guild_id] = (track_id, position, stalled_for)

                    if stalled_for >= 2 and guild_id not in self._retrying:
                        self._retrying.add(guild_id)
                        try:
                            resume_at = max(0, position)
                            track = player.current
                            await player.play(track, start=resume_at, replace=True, volume=100)
                            self._stalled[guild_id] = (track_id, resume_at, 0)
                        finally:
                            self._retrying.discard(guild_id)
                except Exception:
                    continue

    async def apply_filter(self, ctx: commands.Context, filter_name: str):
        player: Union[wavelink.Player, None] = ctx.voice_client
        if not player or not player.playing:
            await ctx.send("I'm not playing anything.")
            return

        if ctx.author.voice is None or ctx.author.voice.channel != player.channel:
            await ctx.send("You need to be in the same voice channel as me.")
            return

        filters = wavelink.Filters()

        if filter_name == "nightcore":
            filters.timescale.set(pitch=1.2, speed=1.2, rate=1)
        elif filter_name == "bassboost":
            filters.equalizer.set(bands=[{"band": 0, "gain": 0.5}, {"band": 1, "gain": 0.5}, {"band": 2, "gain": 0.5}])
        elif filter_name == "vaporwave":
            filters.timescale.set(rate=0.85, pitch=0.85)
        elif filter_name == "karaoke":
            filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
        elif filter_name == "tremolo":
            filters.tremolo.set(depth=0.5, frequency=14.0)
        elif filter_name == "vibrato":
            filters.vibrato.set(depth=0.5, frequency=14.0)
        elif filter_name == "rotation":
            filters.rotation.set(rotation_hz=5.0)
        elif filter_name == "distortion":
            filters.distortion.set(
                sin_offset=0.0,
                sin_scale=1.0,
                cos_offset=0.0,
                cos_scale=1.0,
                tan_offset=0.0,
                tan_scale=1.0,
                offset=0.0,
                scale=1.0
            )
        elif filter_name == "channelmix":
            filters.channel_mix.set(left_to_left=0.5, left_to_right=0.5, right_to_left=0.5, right_to_right=0.5)

        await player.set_filters(filters)
        self.active_filters[ctx.guild.id] = filter_name
        await ctx.send(embed=discord.Embed(description=f"Filter set to **{filter_name}**.", color=discord.Color.green()))

    @commands.hybrid_group(invoke_without_command=True)
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def filter(self, ctx: commands.Context):
        await ctx.send("Use `filter enable` to enable a filter or `filter disable` to disable the current filter.")

    @filter.command(help="Enable a filter.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def enable(self, ctx: commands.Context):
        player: Union[wavelink.Player, None] = ctx.voice_client
        if not player or not player.playing:
            await ctx.send("I'm not connected to a voice channel.")
            return

        if ctx.author.voice is None or ctx.author.voice.channel != player.channel:
            await ctx.send("You need to be in the same voice channel as me.")
            return

        filter_options = [
            discord.SelectOption(label="Vaporwave", description="Apply vaporwave effect"),
            discord.SelectOption(label="Nightcore", description="Apply nightcore effect"),
            discord.SelectOption(label="Vibrato", description="Apply vibrato effect"),
            discord.SelectOption(label="Tremolo", description="Apply tremolo effect"),
            discord.SelectOption(label="Bassboost", description="Apply bass boost effect"),
            discord.SelectOption(label="Karaoke", description="Apply karaoke effect"),
            discord.SelectOption(label="Rotation", description="Apply rotation effect"),
            discord.SelectOption(label="Distortion", description="Apply distortion effect"),
            discord.SelectOption(label="Channelmix", description="Apply channel mix effect"),
        ]

        class FilterSelect(discord.ui.View):
            @discord.ui.select(placeholder="Choose a filter...", options=filter_options)
            async def select_filter(self, interaction: discord.Interaction, select: discord.ui.Select):
                await interaction.response.defer()
                selected_filter = select.values[0].lower()
                await self.cog.apply_filter(ctx, selected_filter)
                self.disable_all()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.message.delete()
                self.disable_all()

            def disable_all(self):
                for child in self.children:
                    child.disabled = True
                self.stop()

        view = FilterSelect()
        view.cog = self

        current_filter = self.active_filters.get(ctx.guild.id, "None")
        embed = discord.Embed(title="Enable Filter", description="Choose a filter to apply:", color=discord.Color.blue())
        embed.add_field(name="Current Filter", value=current_filter, inline=False)
        await ctx.send(embed=embed, view=view)

    @filter.command(help="Disable the current filter.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def disable(self, ctx: commands.Context):
        player: Union[wavelink.Player, None] = ctx.voice_client
        if not player or not player.playing:
            await ctx.send("I'm not connected to a voice channel.")
            return

        if ctx.author.voice is None or ctx.author.voice.channel != player.channel:
            await ctx.send("You need to be in the same voice channel as me.")
            return

        filters = wavelink.Filters()
        await player.set_filters(filters)
        self.active_filters.pop(ctx.guild.id, None)
        await ctx.send(embed=discord.Embed(description="Filter disabled.", color=discord.Color.red()))
