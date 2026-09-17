import discord
from discord.ext import commands


class ServerSelect(discord.ui.Select):
    def __init__(self, cog, guilds, page=0):
        self.cog = cog
        self.guilds_page = guilds
        self.page = page
        options = []
        for guild in guilds:
            label = guild.name[:100]
            description = f"{guild.member_count or 0} members • ID {guild.id}"[:100]
            options.append(discord.SelectOption(label=label, description=description, value=str(guild.id)))
        super().__init__(placeholder="Select a server to view its details", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        guild = self.cog.bot.get_guild(int(self.values[0]))
        if guild is None:
            return await interaction.response.send_message("That server is no longer available.", ephemeral=True)
        await self.cog.send_server_dm(interaction.user, guild)
        await interaction.response.send_message(f"📩 I sent **{guild.name}**'s server information to your DMs.", ephemeral=True)


class ServerPager(discord.ui.View):
    def __init__(self, cog, guilds, page=0):
        super().__init__(timeout=180)
        self.cog = cog
        self.guilds = guilds
        self.page = page
        self.per_page = 25
        self.total_pages = max(1, (len(guilds) + self.per_page - 1) // self.per_page)
        start = page * self.per_page
        current = guilds[start:start + self.per_page]
        self.add_item(ServerSelect(cog, current, page))

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


class InteractiveServers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_server_dm(self, user, guild):
        embed = discord.Embed(title=f"{guild.name} — Server Information", color=0xFF0000)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=False)
        embed.add_field(name="Members", value=f"`{guild.member_count or 0}`", inline=True)
        embed.add_field(name="Owner", value=f"<@{guild.owner_id}> (`{guild.owner_id}`)", inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, style="F"), inline=False)
        embed.add_field(name="Channels", value=f"`{len(guild.channels)}` total • `{len(guild.text_channels)}` text • `{len(guild.voice_channels)}` voice", inline=True)
        embed.add_field(name="Roles", value=f"`{len(guild.roles)}`", inline=True)

        invite = None
        me = guild.me
        if me:
            candidates = [guild.system_channel] if guild.system_channel else []
            candidates += [c for c in guild.text_channels if c not in candidates]
            for channel in candidates:
                try:
                    if channel.permissions_for(me).create_instant_invite:
                        invite = await channel.create_invite(max_age=0, max_uses=0, unique=False, reason="LightCore owner server information")
                        break
                except (discord.Forbidden, discord.HTTPException):
                    continue

        if invite:
            embed.add_field(name="Server Invite", value=str(invite), inline=False)
        else:
            embed.add_field(name="Server Invite", value="Unavailable — the bot has no permission to create an invite in this server.", inline=False)

        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            raise

    @commands.command(name="servers", aliases=["serverlist", "guilds"], help="Shows all servers the bot is in (owner only).")
    @commands.is_owner()
    async def servers(self, ctx):
        guilds = sorted(self.bot.guilds, key=lambda g: (g.member_count or 0), reverse=True)
        if not guilds:
            return await ctx.send("The bot is not currently in any servers.")

        embed = discord.Embed(
            title=f"{self.bot.user.name} • Server Manager",
            description="Select a server below to receive its complete information and invite in your DMs.",
            color=0xFF0000,
        )
        embed.add_field(name="Total Servers", value=f"`{len(guilds)}`", inline=True)
        embed.add_field(name="Your Access", value="Owner only", inline=True)
        embed.set_footer(text="Use the dropdown to select a server • Buttons change pages")
        await ctx.send(embed=embed, view=ServerPager(self, guilds))


async def setup(bot):
    # Replace the legacy text-only servers command without touching the rest of Status.
    bot.remove_command("servers")
    await bot.add_cog(InteractiveServers(bot))
