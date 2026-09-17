# ╔══════════════════════════════════════════════════════════════════╗
# ║   © 2026 LightCore — All Rights Reserved                        ║
# ╚══════════════════════════════════════════════════════════════════╝

import discord
from utils.emoji import DND, ICON_BROWSER, IDLE, LOADING_ALT1, MOBILE, OFFLINE, ONLINE, PC
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import aiohttp
import os
from utils.Tools import *


class ServerSelect(discord.ui.Select):
    def __init__(self, cog, guilds):
        self.cog = cog
        options = []
        for guild in guilds:
            options.append(discord.SelectOption(
                label=guild.name[:100],
                description=f"{guild.member_count or 0} members • ID {guild.id}"[:100],
                value=str(guild.id)
            ))
        super().__init__(placeholder="Select a server to view its details", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        guild = self.cog.bot.get_guild(int(self.values[0]))
        if guild is None:
            return await interaction.response.send_message("That server is no longer available.", ephemeral=True)
        try:
            await self.cog.send_server_dm(interaction.user, guild)
            await interaction.response.send_message(f"📩 **{guild.name}**'s information and invite were sent to your DMs.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I couldn't DM you. Please enable DMs from server members.", ephemeral=True)


class ServerPager(discord.ui.View):
    def __init__(self, cog, guilds, page=0):
        super().__init__(timeout=180)
        self.cog = cog
        self.guilds = guilds
        self.page = page
        self.per_page = 25
        self.total_pages = max(1, (len(guilds) + self.per_page - 1) // self.per_page)
        start = page * self.per_page
        self.add_item(ServerSelect(cog, guilds[start:start + self.per_page]))

        previous = discord.ui.Button(label="Previous", emoji="◀️", style=discord.ButtonStyle.secondary, disabled=page <= 0)
        next_button = discord.ui.Button(label="Next", emoji="▶️", style=discord.ButtonStyle.secondary, disabled=page >= self.total_pages - 1)
        previous.callback = self.previous
        next_button.callback = self.next_page
        self.add_item(previous)
        self.add_item(next_button)

    async def previous(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=ServerPager(self.cog, self.guilds, self.page - 1))

    async def next_page(self, interaction: discord.Interaction):
        await interaction.response.edit_message(view=ServerPager(self.cog, self.guilds, self.page + 1))


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="servers", aliases=["serverlist", "guilds"], help="Shows all servers the bot is in (owner only).")
    @commands.is_owner()
    async def servers(self, ctx):
        servers = sorted(self.bot.guilds, key=lambda g: (g.member_count or 0), reverse=True)
        if not servers:
            return await ctx.send("The bot is not currently in any servers.")

        embed = discord.Embed(
            title=f"{self.bot.user.name} • Server Manager",
            description="Select a server below to receive its complete information and invite in your DMs.",
            color=0xFF0000,
        )
        embed.add_field(name="Total Servers", value=f"`{len(servers)}`", inline=True)
        embed.add_field(name="Access", value="Owner only", inline=True)
        embed.set_footer(text="Use the dropdown to select a server • Buttons change pages")
        await ctx.send(embed=embed, view=ServerPager(self, servers))

    async def send_server_dm(self, user, guild):
        embed = discord.Embed(title=f"{guild.name} — Server Information", color=0xFF0000)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=False)
        embed.add_field(name="Members", value=f"`{guild.member_count or 0}`", inline=True)
        embed.add_field(name="Owner", value=f"<@{guild.owner_id}> (`{guild.owner_id}`)", inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, style="F"), inline=False)
        embed.add_field(
            name="Channels",
            value=f"`{len(guild.channels)}` total • `{len(guild.text_channels)}` text • `{len(guild.voice_channels)}` voice",
            inline=True,
        )
        embed.add_field(name="Roles", value=f"`{len(guild.roles)}`", inline=True)

        invite = None
        me = guild.me
        if me:
            candidates = []
            if guild.system_channel:
                candidates.append(guild.system_channel)
            candidates.extend(c for c in guild.text_channels if c not in candidates)
            for channel in candidates:
                try:
                    if channel.permissions_for(me).create_instant_invite:
                        invite = await channel.create_invite(
                            max_age=0,
                            max_uses=0,
                            unique=False,
                            reason="LightCore owner server information"
                        )
                        break
                except (discord.Forbidden, discord.HTTPException):
                    continue

        if invite:
            embed.add_field(name="Server Invite", value=str(invite), inline=False)
        else:
            embed.add_field(
                name="Server Invite",
                value="Unavailable — the bot does not have permission to create an invite in this server.",
                inline=False,
            )

        embed.set_footer(text="LightCore • Owner Server Information")
        await user.send(embed=embed)

    @commands.command(name="status", help="Shows the status of the user in detail.")
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def status(self, ctx, user: discord.User = None):
        user = user or ctx.author
        processing = await ctx.send(f"{LOADING_ALT1} Loading Status...")
        embed = discord.Embed(title=f"{user.display_name}'s Status", color=0xFF0000)

        status_emoji = {
            "online": f"{ONLINE} Online",
            "idle": f"{IDLE} Idle",
            "dnd": f"{DND} Do Not Disturb",
            "offline": f"{OFFLINE} Offline"
        }

        member = None
        for guild in self.bot.guilds:
            member = guild.get_member(user.id)
            if member:
                break

        if member:
            status = status_emoji.get(str(member.status), f"{OFFLINE} Offline")
            embed.add_field(name="Status:", value=status, inline=False)
            avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
            embed.set_thumbnail(url=avatar_url)

            platform = self.get_platform(member)
            embed.add_field(name="Platform:", value=platform, inline=False)

            custom_status = self.get_custom_status(member)
            if custom_status:
                embed.add_field(name="Custom Status:", value=custom_status, inline=False)

            activity_text = self.get_activity_text(member.activities)
            if activity_text:
                embed.add_field(name="__Activity__:", value=activity_text, inline=False)

            for activity in member.activities:
                if isinstance(activity, discord.Spotify):
                    song_name = activity.title
                    album_cover_url = str(activity.album_cover_url)
                    album_image_path = 'data/pictures/album_image.png'
                    async with aiohttp.ClientSession() as session:
                        async with session.get(album_cover_url) as resp:
                            if resp.status == 200:
                                album_data = await resp.read()
                                with open(album_image_path, 'wb') as f:
                                    f.write(album_data)
                    card_image_path = self.create_spotify_card(song_name, album_image_path)
                    if os.path.exists(card_image_path):
                        file = discord.File(card_image_path, filename="spotify_card.png")
                        embed.set_image(url="attachment://spotify_card.png")
                    else:
                        await ctx.send("Failed to generate the Spotify card image.")
        else:
            try:
                user = await self.bot.fetch_user(user.id)
                embed.add_field(name="Status:", value=f"{OFFLINE} Offline", inline=False)
                embed.set_thumbnail(url=user.default_avatar.url)
            except discord.NotFound:
                await ctx.send("User not found.")
                return

        requester_avatar_url = ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=requester_avatar_url)
        await ctx.send(embed=embed, file=file if 'file' in locals() else None)
        await processing.delete()

    def create_spotify_card(self, song_name, album_image_path):
        card_path = 'data/pictures/spotify.png'
        output_path = 'data/pictures/spotify_card_output.png'
        base_img = Image.open(card_path).convert("RGBA")
        draw = ImageDraw.Draw(base_img)
        album_img = Image.open(album_image_path).convert("RGBA")
        album_img = album_img.resize((160, 160))
        mask = Image.new("L", album_img.size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, 160, 160), fill=255)
        base_img.paste(album_img, (30, 30), mask)
        font_path = 'utils/arial.ttf'
        font = ImageFont.truetype(font_path, 40)
        truncated_song_name = song_name if len(song_name) <= 60 else song_name[:57] + "..."
        draw.text((220, 70), truncated_song_name, font=font, fill="white")
        base_img.save(output_path)
        return output_path

    def get_platform(self, member):
        if member.desktop_status != discord.Status.offline:
            return f"{PC} Desktop"
        elif member.mobile_status != discord.Status.offline:
            return f"{MOBILE} Mobile"
        elif member.web_status != discord.Status.offline:
            return f"{ICON_BROWSER} Browser"
        return "Unknown"

    def get_custom_status(self, member):
        for activity in member.activities:
            if isinstance(activity, discord.CustomActivity):
                status_text = activity.name or ""
                if activity.name == "Custom Status":
                    status_text = "‎"
                status_emoji = str(activity.emoji) if activity.emoji else ""
                if status_emoji and not status_text:
                    return status_emoji
                elif status_emoji and status_text:
                    return f"{status_emoji} {status_text}"
                elif status_text:
                    return status_text
        return None

    def get_activity_text(self, activities):
        activity_list = []
        for activity in activities:
            if isinstance(activity, discord.Game):
                activity_list.append(f"Playing {activity.name}")
            elif isinstance(activity, discord.Streaming):
                activity_list.append(f"Streaming {activity.name} on **[Twitch]({activity.url})**")
            elif isinstance(activity, discord.Spotify):
                activity_list.append(f"**[Listening to Spotify](https://open.spotify.com/track/{activity.track_id})**")
            elif isinstance(activity, discord.Activity):
                activity_list.append(f"{activity.type.name.capitalize()} {activity.name}")
        return "\n".join(activity_list) if activity_list else None
