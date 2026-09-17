from __future__ import annotations

import asyncio
import aiosqlite
import discord
from discord.ext import commands

DB = "tempvoice_data.db"


async def safe_response(interaction: discord.Interaction, message: str):
    if interaction.response.is_done():
        return await interaction.followup.send(message, ephemeral=True)
    return await interaction.response.send_message(message, ephemeral=True)


class RenameModal(discord.ui.Modal, title="Rename your channel"):
    name = discord.ui.TextInput(label="Channel name", placeholder="My Voice", max_length=100)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        vc = await self.cog.owned_vc(interaction)
        if not vc:
            return
        try:
            await vc.edit(name=str(self.name.value).strip())
            await safe_response(interaction, "✏️ Your temporary channel has been renamed.")
        except discord.Forbidden:
            await safe_response(interaction, "❌ I need **Manage Channels** to rename your channel.")


class LimitModal(discord.ui.Modal, title="Set user limit"):
    limit = discord.ui.TextInput(label="User limit", placeholder="0 = unlimited", max_length=2)

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        vc = await self.cog.owned_vc(interaction)
        if not vc:
            return
        try:
            value = int(str(self.limit.value).strip())
            if value < 0 or value > 99:
                raise ValueError
        except ValueError:
            return await safe_response(interaction, "❌ Enter a number from **0 to 99**.")
        try:
            await vc.edit(user_limit=value)
            await safe_response(interaction, f"👥 User limit set to **{value or 'Unlimited'}**.")
        except discord.Forbidden:
            await safe_response(interaction, "❌ I need **Manage Channels** to change the limit.")


class MemberSelectView(discord.ui.View):
    def __init__(self, cog, owner_id: int, mode: str):
        super().__init__(timeout=120)
        self.cog = cog
        self.owner_id = owner_id
        self.mode = mode
        select = discord.ui.UserSelect(
            placeholder="Select a member",
            min_values=1,
            max_values=1,
        )
        select.callback = self.selected
        self.add_item(select)

    async def selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            return await safe_response(interaction, "❌ Only the current channel owner can use this menu.")
        vc = await self.cog.owned_vc(interaction)
        if not vc:
            return
        member = self.children[0].values[0]
        if member.bot:
            return await safe_response(interaction, "❌ Bots cannot be selected.")
        try:
            if self.mode == "transfer":
                old_owner = interaction.guild.get_member(self.owner_id)
                if old_owner:
                    await vc.set_permissions(old_owner, overwrite=None)
                await vc.set_permissions(member, view_channel=True, connect=True, manage_channels=True, move_members=True)
                await self.cog.set_owner(vc.id, member.id)
                await safe_response(interaction, f"👑 {member.mention} is now the channel owner.")
            elif self.mode == "permit":
                await vc.set_permissions(member, view_channel=True, connect=True)
                await safe_response(interaction, f"✅ {member.mention} can now join your channel.")
            elif self.mode == "kick":
                if member.voice and member.voice.channel == vc:
                    await member.move_to(None)
                    await safe_response(interaction, f"🚪 {member.mention} was disconnected.")
                else:
                    await safe_response(interaction, "ℹ️ That member is not in your temporary channel.")
        except discord.Forbidden:
            await safe_response(interaction, "❌ I don't have enough permissions to perform that action.")


class TempVoicePanel(discord.ui.View):
    """Persistent TempVoice Bot-style owner control panel."""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def vc(self, interaction):
        return await self.cog.owned_vc(interaction)

    @discord.ui.button(label="Lock", emoji="🔒", style=discord.ButtonStyle.secondary, row=0, custom_id="lightcore:tv:lock")
    async def lock(self, interaction, button):
        vc = await self.vc(interaction)
        if not vc:
            return
        try:
            await vc.set_permissions(interaction.guild.default_role, connect=False)
            await safe_response(interaction, "🔒 Your channel is now **locked**.")
        except discord.Forbidden:
            await safe_response(interaction, "❌ I need **Manage Channels** to lock it.")

    @discord.ui.button(label="Unlock", emoji="🔓", style=discord.ButtonStyle.secondary, row=0, custom_id="lightcore:tv:unlock")
    async def unlock(self, interaction, button):
        vc = await self.vc(interaction)
        if not vc:
            return
        try:
            await vc.set_permissions(interaction.guild.default_role, connect=True)
            await safe_response(interaction, "🔓 Your channel is now **unlocked**.")
        except discord.Forbidden:
            await safe_response(interaction, "❌ I need **Manage Channels** to unlock it.")

    @discord.ui.button(label="Hide", emoji="🙈", style=discord.ButtonStyle.secondary, row=0, custom_id="lightcore:tv:hide")
    async def hide(self, interaction, button):
        vc = await self.vc(interaction)
        if not vc:
            return
        try:
            await vc.set_permissions(interaction.guild.default_role, view_channel=False)
            await vc.set_permissions(interaction.user, view_channel=True, connect=True, manage_channels=True, move_members=True)
            await safe_response(interaction, "🙈 Your channel is now **hidden**.")
        except discord.Forbidden:
            await safe_response(interaction, "❌ I need **Manage Channels** to hide it.")

    @discord.ui.button(label="Unhide", emoji="👁️", style=discord.ButtonStyle.secondary, row=0, custom_id="lightcore:tv:unhide")
    async def unhide(self, interaction, button):
        vc = await self.vc(interaction)
        if not vc:
            return
        try:
            await vc.set_permissions(interaction.guild.default_role, view_channel=True)
            await safe_response(interaction, "👁️ Your channel is visible again.")
        except discord.Forbidden:
            await safe_response(interaction, "❌ I need **Manage Channels** to unhide it.")

    @discord.ui.button(label="Rename", emoji="✏️", style=discord.ButtonStyle.primary, row=0, custom_id="lightcore:tv:rename")
    async def rename(self, interaction, button):
        if await self.vc(interaction):
            await interaction.response.send_modal(RenameModal(self.cog))

    @discord.ui.button(label="Limit", emoji="👥", style=discord.ButtonStyle.primary, row=1, custom_id="lightcore:tv:limit")
    async def limit(self, interaction, button):
        if await self.vc(interaction):
            await interaction.response.send_modal(LimitModal(self.cog))

    @discord.ui.button(label="Transfer", emoji="👑", style=discord.ButtonStyle.primary, row=1, custom_id="lightcore:tv:transfer")
    async def transfer(self, interaction, button):
        if await self.vc(interaction):
            await interaction.response.send_message("👑 **Transfer ownership**\nSelect the member who should become the new owner.", view=MemberSelectView(self.cog, interaction.user.id, "transfer"), ephemeral=True)

    @discord.ui.button(label="Permit", emoji="✅", style=discord.ButtonStyle.primary, row=1, custom_id="lightcore:tv:permit")
    async def permit(self, interaction, button):
        if await self.vc(interaction):
            await interaction.response.send_message("✅ **Permit a member**\nSelect the member who can join your channel.", view=MemberSelectView(self.cog, interaction.user.id, "permit"), ephemeral=True)

    @discord.ui.button(label="Kick", emoji="👢", style=discord.ButtonStyle.secondary, row=1, custom_id="lightcore:tv:kick")
    async def kick(self, interaction, button):
        if await self.vc(interaction):
            await interaction.response.send_message("👢 **Kick a member**\nSelect a member currently in your channel.", view=MemberSelectView(self.cog, interaction.user.id, "kick"), ephemeral=True)

    @discord.ui.button(label="Info", emoji="ℹ️", style=discord.ButtonStyle.secondary, row=2, custom_id="lightcore:tv:info")
    async def info(self, interaction, button):
        vc = await self.vc(interaction)
        if not vc:
            return
        owner_id = self.cog.channels.get(vc.id, {}).get("owner_id", interaction.user.id)
        embed = discord.Embed(title="🎙️ Temporary Voice", color=0x5865F2)
        embed.add_field(name="Channel", value=vc.mention, inline=False)
        embed.add_field(name="Owner", value=f"<@{owner_id}>", inline=True)
        embed.add_field(name="Members", value=str(len(vc.members)), inline=True)
        embed.add_field(name="Limit", value=str(vc.user_limit or "Unlimited"), inline=True)
        embed.add_field(name="Bitrate", value=f"{vc.bitrate // 1000} kbps", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Disconnect", emoji="🚪", style=discord.ButtonStyle.secondary, row=2, custom_id="lightcore:tv:disconnect")
    async def disconnect(self, interaction, button):
        vc = await self.vc(interaction)
        if not vc:
            return
        count = 0
        for member in list(vc.members):
            if member.id == interaction.user.id or member.bot:
                continue
            try:
                await member.move_to(None)
                count += 1
            except (discord.Forbidden, discord.HTTPException):
                pass
        await safe_response(interaction, f"🚪 Disconnected **{count}** member(s).")

    @discord.ui.button(label="Claim", emoji="🫴", style=discord.ButtonStyle.primary, row=2, custom_id="lightcore:tv:claim")
    async def claim(self, interaction, button):
        voice = interaction.user.voice
        if not voice or voice.channel.id not in self.cog.channels:
            return await safe_response(interaction, "❌ Join a temporary channel first.")
        vc = voice.channel
        owner_id = self.cog.channels[vc.id]["owner_id"]
        owner = interaction.guild.get_member(owner_id)
        if owner and owner.voice and owner.voice.channel == vc:
            return await safe_response(interaction, "❌ The current owner is still in the channel.")
        await self.cog.set_owner(vc.id, interaction.user.id)
        try:
            await vc.set_permissions(interaction.user, view_channel=True, connect=True, manage_channels=True, move_members=True)
        except discord.Forbidden:
            pass
        await safe_response(interaction, "🫴 You now own this temporary channel.")

    @discord.ui.button(label="Delete", emoji="🗑️", style=discord.ButtonStyle.danger, row=2, custom_id="lightcore:tv:delete")
    async def delete(self, interaction, button):
        vc = await self.vc(interaction)
        if not vc:
            return
        await self.cog.delete_temp_channel(vc.id)
        await safe_response(interaction, "🗑️ Your temporary channel has been deleted.")


class SetupView(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx

    async def allowed(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            await safe_response(interaction, "❌ Only the person who started setup can configure TempVoice.")
            return False
        return True

    @discord.ui.button(label="Create voice channel", emoji="➕", style=discord.ButtonStyle.primary, custom_id="lightcore:tv:create")
    async def create(self, interaction, button):
        if await self.allowed(interaction):
            await interaction.response.send_message("Choose the **category** for the Join to Create voice channel:", view=CategorySelect(self.cog, self.ctx), ephemeral=True)

    @discord.ui.button(label="Use existing voice", emoji="🎙️", style=discord.ButtonStyle.secondary, custom_id="lightcore:tv:existing")
    async def existing(self, interaction, button):
        if await self.allowed(interaction):
            await interaction.response.send_message("Choose the **existing voice channel** that members will join to create their temporary channel:", view=VoiceSelect(self.cog, self.ctx), ephemeral=True)


class CategorySelect(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        categories = ctx.guild.categories[:25]
        options = [discord.SelectOption(label=c.name[:100], value=str(c.id), description="Create Join to Create here") for c in categories]
        if not options:
            options = [discord.SelectOption(label="No categories found", value="0")]
        select = discord.ui.Select(placeholder="Select a category", options=options)
        select.callback = self.selected
        self.add_item(select)

    async def selected(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await safe_response(interaction, "❌ Only the setup user can configure TempVoice.")
        category = interaction.guild.get_channel(int(self.children[0].values[0]))
        if not isinstance(category, discord.CategoryChannel):
            return await safe_response(interaction, "❌ Invalid category.")
        await interaction.response.send_message("Now choose the **interface text channel** where the TempVoice control panel should live:", view=TextSelect(self.cog, self.ctx, category=category), ephemeral=True)


class VoiceSelect(discord.ui.View):
    def __init__(self, cog, ctx):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        voices = [c for c in ctx.guild.voice_channels if not cog.is_temp_channel(c.id)][:25]
        options = [discord.SelectOption(label=c.name[:100], value=str(c.id), description=f"Category: {c.category.name[:80]}" if c.category else "No category") for c in voices]
        if not options:
            options = [discord.SelectOption(label="No voice channels found", value="0")]
        select = discord.ui.Select(placeholder="Select Join to Create voice channel", options=options)
        select.callback = self.selected
        self.add_item(select)

    async def selected(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await safe_response(interaction, "❌ Only the setup user can configure TempVoice.")
        channel = interaction.guild.get_channel(int(self.children[0].values[0]))
        if not isinstance(channel, discord.VoiceChannel) or channel.id == 0:
            return await safe_response(interaction, "❌ Invalid voice channel.")
        await interaction.response.send_message("Now choose the **interface text channel** where the TempVoice control panel should live:", view=TextSelect(self.cog, self.ctx, category=channel.category, existing=channel), ephemeral=True)


class TextSelect(discord.ui.View):
    def __init__(self, cog, ctx, category=None, existing=None):
        super().__init__(timeout=300)
        self.cog = cog
        self.ctx = ctx
        self.category = category
        self.existing = existing
        me = ctx.guild.me
        text_channels = [c for c in ctx.guild.text_channels if not me or c.permissions_for(me).send_messages]
        options = [discord.SelectOption(label=c.name[:100], value=str(c.id), description="TempVoice control interface") for c in text_channels[:25]]
        if not options:
            options = [discord.SelectOption(label="No usable text channels", value="0")]
        select = discord.ui.Select(placeholder="Select interface text channel", options=options)
        select.callback = self.selected
        self.add_item(select)

    async def selected(self, interaction):
        if interaction.user.id != self.ctx.author.id:
            return await safe_response(interaction, "❌ Only the setup user can configure TempVoice.")
        channel = interaction.guild.get_channel(int(self.children[0].values[0]))
        if not isinstance(channel, discord.TextChannel) or channel.id == 0:
            return await safe_response(interaction, "❌ Invalid text channel.")
        await self.cog.finish_setup(interaction, self.category, self.existing, channel)


class TempVoice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.setup = {}
        self.channels = {}
        self._cleanup_lock = asyncio.Lock()
        bot.loop.create_task(self.load())

    def is_temp_channel(self, channel_id: int) -> bool:
        return channel_id in self.channels

    async def load(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(DB) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS setup (guild_id INTEGER PRIMARY KEY,join_id INTEGER,category_id INTEGER,panel_channel_id INTEGER,panel_message_id INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS channels (channel_id INTEGER PRIMARY KEY,guild_id INTEGER,owner_id INTEGER)")
            await db.commit()
            async with db.execute("SELECT guild_id,join_id,category_id,panel_channel_id,panel_message_id FROM setup") as cursor:
                async for row in cursor:
                    self.setup[row[0]] = {"join_id": row[1], "category_id": row[2], "panel_channel_id": row[3], "panel_message_id": row[4]}
            async with db.execute("SELECT channel_id,guild_id,owner_id FROM channels") as cursor:
                async for row in cursor:
                    self.channels[row[0]] = {"guild_id": row[1], "owner_id": row[2]}

        self.bot.add_view(TempVoicePanel(self))
        await self.cleanup_empty_channels()

        for guild_id, data in list(self.setup.items()):
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            panel_channel = guild.get_channel(data["panel_channel_id"])
            if not isinstance(panel_channel, discord.TextChannel):
                continue
            try:
                message = await panel_channel.fetch_message(data["panel_message_id"])
                await message.edit(view=TempVoicePanel(self))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

    async def save_setup(self, guild_id, data):
        async with aiosqlite.connect(DB) as db:
            await db.execute("INSERT OR REPLACE INTO setup VALUES(?,?,?,?,?)", (guild_id, data["join_id"], data["category_id"], data["panel_channel_id"], data["panel_message_id"]))
            await db.commit()

    async def save_channel(self, channel_id, guild_id, owner_id):
        self.channels[channel_id] = {"guild_id": guild_id, "owner_id": owner_id}
        async with aiosqlite.connect(DB) as db:
            await db.execute("INSERT OR REPLACE INTO channels VALUES(?,?,?)", (channel_id, guild_id, owner_id))
            await db.commit()

    async def remove_channel(self, channel_id):
        self.channels.pop(channel_id, None)
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM channels WHERE channel_id=?", (channel_id,))
            await db.commit()

    async def set_owner(self, channel_id, owner_id):
        if channel_id in self.channels:
            self.channels[channel_id]["owner_id"] = owner_id
        async with aiosqlite.connect(DB) as db:
            await db.execute("UPDATE channels SET owner_id=? WHERE channel_id=?", (owner_id, channel_id))
            await db.commit()

    async def delete_temp_channel(self, channel_id):
        channel = self.bot.get_channel(channel_id)
        await self.remove_channel(channel_id)
        if channel:
            try:
                await channel.delete(reason="TempVoice empty/owner deleted channel")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

    async def cleanup_empty_channels(self):
        async with self._cleanup_lock:
            for channel_id in list(self.channels):
                channel = self.bot.get_channel(channel_id)
                if channel is None:
                    await self.remove_channel(channel_id)
                    continue
                if isinstance(channel, discord.VoiceChannel) and not channel.members:
                    await self.delete_temp_channel(channel_id)

    async def cleanup_loop(self):
        while not self.bot.is_closed():
            await asyncio.sleep(10)
            try:
                await self.cleanup_empty_channels()
            except Exception as exc:
                print(f"TempVoice cleanup error: {exc}")

    async def owned_vc(self, interaction):
        voice = interaction.user.voice
        if not voice or voice.channel.id not in self.channels:
            await safe_response(interaction, "❌ Join your temporary voice channel first.")
            return None
        if self.channels[voice.channel.id]["owner_id"] != interaction.user.id:
            await safe_response(interaction, "❌ You don't own this temporary voice channel.")
            return None
        return voice.channel

    async def lock_interface(self, channel):
        me = channel.guild.me
        await channel.set_permissions(channel.guild.default_role, view_channel=True, send_messages=False, add_reactions=False, read_message_history=True)
        if me:
            await channel.set_permissions(me, view_channel=True, send_messages=True, read_message_history=True, embed_links=True)

    async def finish_setup(self, interaction, category, existing, interface):
        guild = interaction.guild
        if guild.id in self.setup:
            return await safe_response(interaction, "❌ TempVoice is already configured here. Use `.tempvoice reset` first if you want to reconfigure it.")

        try:
            join = existing
            if join is None:
                join = await guild.create_voice_channel("➕ Join to Create", category=category, reason="TempVoice setup")
            if not isinstance(join, discord.VoiceChannel):
                return await safe_response(interaction, "❌ The selected Join to Create channel is invalid.")

            embed = discord.Embed(
                title="🎙️ TempVoice",
                description=(
                    "**Create your own temporary voice channel**\n\n"
                    f"Join {join.mention} to automatically create your personal voice channel.\n"
                    "When your temporary channel becomes empty, it is automatically deleted.\n\n"
                    "### Channel Controls\n"
                    "🔒 Lock  •  🔓 Unlock  •  🙈 Hide  •  👁️ Unhide  •  ✏️ Rename\n"
                    "👥 Limit  •  👑 Transfer  •  ✅ Permit  •  👢 Kick\n"
                    "ℹ️ Info  •  🚪 Disconnect  •  🫴 Claim  •  🗑️ Delete\n\n"
                    "Only the owner of a temporary channel can use its controls."
                ),
                color=0x5865F2,
            )
            embed.set_footer(text="TempVoice • LightCore")
            panel = await interface.send(embed=embed, view=TempVoicePanel(self))
            await self.lock_interface(interface)

            data = {
                "join_id": join.id,
                "category_id": join.category.id if join.category else 0,
                "panel_channel_id": interface.id,
                "panel_message_id": panel.id,
            }
            self.setup[guild.id] = data
            await self.save_setup(guild.id, data)
            await safe_response(interaction, f"✅ **TempVoice configured successfully.**\n\n🎙️ Join to Create: {join.mention}\n🖥️ Interface: {interface.mention}\n\nJoin the configured voice channel to test it.")
        except discord.Forbidden:
            await safe_response(interaction, "❌ I need **Manage Channels**, **Move Members**, and permission to send messages in the selected interface channel.")
        except discord.HTTPException as exc:
            await safe_response(interaction, f"❌ Discord rejected the setup: `{type(exc).__name__}`")

    @commands.group(name="tempvoice", aliases=["tv"], invoke_without_command=True)
    @commands.guild_only()
    async def tempvoice(self, ctx):
        await ctx.send(f"Use `{ctx.prefix}tempvoice setup` to configure TempVoice.")

    @tempvoice.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_cmd(self, ctx):
        if ctx.guild.id in self.setup:
            return await ctx.send(f"❌ TempVoice is already configured. Use `{ctx.prefix}tempvoice reset` to reconfigure it.")
        await ctx.send("## 🎙️ TempVoice Setup\nChoose how you want to configure the **Join to Create** voice channel and the **interface text channel**.", view=SetupView(self, ctx))

    @tempvoice.command(name="panel")
    @commands.has_permissions(administrator=True)
    async def panel_cmd(self, ctx):
        data = self.setup.get(ctx.guild.id)
        if not data:
            return await ctx.send(f"❌ TempVoice is not configured. Use `{ctx.prefix}tempvoice setup` first.")
        channel = ctx.guild.get_channel(data["panel_channel_id"])
        if not isinstance(channel, discord.TextChannel):
            return await ctx.send("❌ The configured interface channel no longer exists. Run setup again after reset.")
        try:
            message = await channel.send(embed=discord.Embed(title="🎙️ TempVoice", description="Use the buttons below to manage your temporary voice channel.", color=0x5865F2), view=TempVoicePanel(self))
            data["panel_message_id"] = message.id
            await self.save_setup(ctx.guild.id, data)
            await ctx.send(f"✅ New TempVoice interface created in {channel.mention}.", delete_after=8)
        except discord.Forbidden:
            await ctx.send("❌ I cannot send messages in the configured interface channel.")

    @tempvoice.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_cmd(self, ctx):
        data = self.setup.pop(ctx.guild.id, None)
        if not data:
            return await ctx.send("❌ TempVoice is not configured in this server.")
        for channel_id in list(self.channels):
            if self.channels[channel_id]["guild_id"] == ctx.guild.id:
                await self.delete_temp_channel(channel_id)
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM setup WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
        await ctx.send("✅ TempVoice configuration and its temporary channels have been reset.")

    async def on_voice_state_update(self, member, before, after):
        if after.channel:
            setup = self.setup.get(member.guild.id)
            if setup and after.channel.id == setup["join_id"] and not member.bot:
                category = member.guild.get_channel(setup["category_id"])
                try:
                    vc = await member.guild.create_voice_channel(f"{member.display_name}'s VC", category=category, reason="TempVoice create")
                    await self.save_channel(vc.id, member.guild.id, member.id)
                    await vc.set_permissions(member, view_channel=True, connect=True, manage_channels=True, move_members=True)
                    await member.move_to(vc, reason="TempVoice")
                except discord.Forbidden:
                    try:
                        await member.send("❌ TempVoice could not create your channel because the bot is missing Discord permissions.")
                    except discord.HTTPException:
                        pass
                except discord.HTTPException as exc:
                    print(f"TempVoice create error: {exc}")

        if before.channel and before.channel.id in self.channels:
            await asyncio.sleep(0.5)
            if not before.channel.members:
                await self.delete_temp_channel(before.channel.id)

    async def cog_load(self):
        if not self._cleanup_task if False else False:
            pass
        self._cleanup_task = self.bot.loop.create_task(self.cleanup_loop())

    async def cog_unload(self):
        task = getattr(self, "_cleanup_task", None)
        if task:
            task.cancel()


async def setup(bot):
    cog = TempVoice(bot)
    await bot.add_cog(cog)
