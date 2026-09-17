from __future__ import annotations

import aiosqlite
import discord
from discord.ext import commands


DB = "tempvoice_data.db"


class RenameModal(discord.ui.Modal, title="Rename your voice channel"):
    name = discord.ui.TextInput(label="Channel name", max_length=100, required=True)

    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        if not self.cog.is_owner_channel(interaction, self.channel):
            return await interaction.response.send_message("❌ You are not the owner of this temporary VC.", ephemeral=True)
        await self.channel.edit(name=str(self.name.value), reason="TempVoice rename")
        await interaction.response.send_message("✅ Channel renamed.", ephemeral=True)


class LimitModal(discord.ui.Modal, title="Set user limit"):
    limit = discord.ui.TextInput(label="Limit (0 = unlimited)", max_length=2, required=True)

    def __init__(self, cog, channel):
        super().__init__()
        self.cog = cog
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        if not self.cog.is_owner_channel(interaction, self.channel):
            return await interaction.response.send_message("❌ You are not the owner of this temporary VC.", ephemeral=True)
        try:
            value = int(str(self.limit.value))
            if not 0 <= value <= 99:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Enter a number from 0 to 99.", ephemeral=True)
        await self.channel.edit(user_limit=value, reason="TempVoice limit")
        await interaction.response.send_message(f"✅ User limit set to **{value or 'unlimited'}**.", ephemeral=True)


class TempVoicePanel(discord.ui.View):
    def __init__(self, cog, channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id

    def channel(self, guild):
        return guild.get_channel(self.channel_id)

    async def check(self, interaction):
        channel = self.channel(interaction.guild)
        if not channel:
            await interaction.response.send_message("❌ This temporary VC no longer exists.", ephemeral=True)
            return None
        if not self.cog.is_owner_channel(interaction, channel):
            await interaction.response.send_message("❌ Only the VC owner can use these controls.", ephemeral=True)
            return None
        return channel

    @discord.ui.button(label="Lock", emoji="🔒", style=discord.ButtonStyle.secondary, custom_id="tempvoice:lock")
    async def lock(self, interaction, button):
        channel = await self.check(interaction)
        if not channel: return
        await channel.set_permissions(interaction.guild.default_role, connect=False, reason="TempVoice lock")
        await interaction.response.send_message("🔒 VC locked.", ephemeral=True)

    @discord.ui.button(label="Unlock", emoji="🔓", style=discord.ButtonStyle.secondary, custom_id="tempvoice:unlock")
    async def unlock(self, interaction, button):
        channel = await self.check(interaction)
        if not channel: return
        await channel.set_permissions(interaction.guild.default_role, connect=True, reason="TempVoice unlock")
        await interaction.response.send_message("🔓 VC unlocked.", ephemeral=True)

    @discord.ui.button(label="Hide", emoji="👁️", style=discord.ButtonStyle.secondary, custom_id="tempvoice:hide")
    async def hide(self, interaction, button):
        channel = await self.check(interaction)
        if not channel: return
        await channel.set_permissions(interaction.guild.default_role, view_channel=False, reason="TempVoice hide")
        await interaction.response.send_message("👁️ VC hidden.", ephemeral=True)

    @discord.ui.button(label="Show", emoji="👀", style=discord.ButtonStyle.secondary, custom_id="tempvoice:show")
    async def show(self, interaction, button):
        channel = await self.check(interaction)
        if not channel: return
        await channel.set_permissions(interaction.guild.default_role, view_channel=True, reason="TempVoice show")
        await interaction.response.send_message("👀 VC visible.", ephemeral=True)

    @discord.ui.button(label="Rename", emoji="✏️", style=discord.ButtonStyle.primary, custom_id="tempvoice:rename", row=1)
    async def rename(self, interaction, button):
        channel = await self.check(interaction)
        if channel: await interaction.response.send_modal(RenameModal(self.cog, channel))

    @discord.ui.button(label="Limit", emoji="👥", style=discord.ButtonStyle.primary, custom_id="tempvoice:limit", row=1)
    async def limit(self, interaction, button):
        channel = await self.check(interaction)
        if channel: await interaction.response.send_modal(LimitModal(self.cog, channel))

    @discord.ui.button(label="Claim", emoji="👑", style=discord.ButtonStyle.primary, custom_id="tempvoice:claim", row=1)
    async def claim(self, interaction, button):
        channel = self.channel(interaction.guild)
        if not channel:
            return await interaction.response.send_message("❌ VC no longer exists.", ephemeral=True)
        data = await self.cog.get_channel_data(channel.id)
        if not data:
            return await interaction.response.send_message("❌ This is not a temporary VC.", ephemeral=True)
        owner = interaction.guild.get_member(data["owner_id"])
        if owner and owner.voice and owner.voice.channel and owner.voice.channel.id == channel.id:
            return await interaction.response.send_message("❌ The current owner is still in the VC.", ephemeral=True)
        await self.cog.set_owner(channel.id, interaction.user.id)
        await interaction.response.send_message("👑 You are now the VC owner.", ephemeral=True)

    @discord.ui.button(label="Delete", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="tempvoice:delete", row=1)
    async def delete(self, interaction, button):
        channel = await self.check(interaction)
        if not channel: return
        await self.cog.remove_channel(channel.id)
        await channel.delete(reason="TempVoice owner deleted channel")
        await interaction.response.send_message("🗑️ Temporary VC deleted.", ephemeral=True)


class TempVoice(commands.Cog):
    """Astro/TempVoice-style join-to-create voice channels with a persistent control panel."""

    def __init__(self, bot):
        self.bot = bot
        self.setup = {}
        self.channels = {}
        bot.loop.create_task(self.init_db())

    async def init_db(self):
        async with aiosqlite.connect(DB) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS setup (guild_id INTEGER PRIMARY KEY, join_id INTEGER, category_id INTEGER, panel_channel_id INTEGER, panel_message_id INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS channels (channel_id INTEGER PRIMARY KEY, guild_id INTEGER, owner_id INTEGER)")
            await db.commit()
            async with db.execute("SELECT guild_id, join_id, category_id, panel_channel_id, panel_message_id FROM setup") as cur:
                async for row in cur:
                    self.setup[row[0]] = {"join_id": row[1], "category_id": row[2], "panel_channel_id": row[3], "panel_message_id": row[4]}
            async with db.execute("SELECT channel_id, guild_id, owner_id FROM channels") as cur:
                async for row in cur:
                    self.channels[row[0]] = {"guild_id": row[1], "owner_id": row[2]}
        self.bot.loop.create_task(self.restore_panels())

    async def restore_panels(self):
        await self.bot.wait_until_ready()
        for guild_id, data in list(self.setup.items()):
            guild = self.bot.get_guild(guild_id)
            if not guild: continue
            channel = guild.get_channel(data["panel_channel_id"])
            if not channel: continue
            try:
                msg = await channel.fetch_message(data["panel_message_id"])
                await msg.edit(view=TempVoiceSetupPanel(self, guild_id))
            except Exception:
                pass

    async def save_setup(self, guild_id, data):
        async with aiosqlite.connect(DB) as db:
            await db.execute("INSERT OR REPLACE INTO setup VALUES (?, ?, ?, ?, ?)", (guild_id, data["join_id"], data["category_id"], data["panel_channel_id"], data["panel_message_id"]))
            await db.commit()

    async def save_channel(self, cid, gid, oid):
        self.channels[cid] = {"guild_id": gid, "owner_id": oid}
        async with aiosqlite.connect(DB) as db:
            await db.execute("INSERT OR REPLACE INTO channels VALUES (?, ?, ?)", (cid, gid, oid))
            await db.commit()

    async def remove_channel(self, cid):
        self.channels.pop(cid, None)
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM channels WHERE channel_id=?", (cid,))
            await db.commit()

    async def set_owner(self, cid, oid):
        if cid in self.channels: self.channels[cid]["owner_id"] = oid
        async with aiosqlite.connect(DB) as db:
            await db.execute("UPDATE channels SET owner_id=? WHERE channel_id=?", (oid, cid))
            await db.commit()

    async def get_channel_data(self, cid):
        return self.channels.get(cid)

    def is_owner_channel(self, interaction, channel):
        data = self.channels.get(channel.id)
        return bool(data and (data["owner_id"] == interaction.user.id or self.bot.get_user(interaction.user.id) == interaction.user))

    @commands.group(name="tempvoice", aliases=["tv"], invoke_without_command=True)
    @commands.guild_only()
    async def tempvoice(self, ctx):
        await ctx.send("Use `.tempvoice setup` to configure TempVoice, or `.tempvoice reset` to remove it.")

    @tempvoice.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_command(self, ctx):
        if ctx.guild.id in self.setup:
            return await ctx.send("❌ TempVoice is already configured in this server.")
        category = await ctx.guild.create_category("TempVoice")
        join = await ctx.guild.create_voice_channel("➕ Join to Create", category=category)
        panel = await ctx.channel.send(view=TempVoiceSetupPanel(self, ctx.guild.id))
        data = {"join_id": join.id, "category_id": category.id, "panel_channel_id": ctx.channel.id, "panel_message_id": panel.id}
        self.setup[ctx.guild.id] = data
        await self.save_setup(ctx.guild.id, data)
        await ctx.send(f"✅ TempVoice configured. Join {join.mention} to create your temporary VC.\nThe control panel is above in {ctx.channel.mention}.")

    @tempvoice.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_command(self, ctx):
        data = self.setup.pop(ctx.guild.id, None)
        if not data: return await ctx.send("❌ TempVoice is not configured here.")
        category = ctx.guild.get_channel(data["category_id"])
        if category:
            for ch in list(category.channels):
                try: await ch.delete(reason="TempVoice reset")
                except discord.HTTPException: pass
            try: await category.delete(reason="TempVoice reset")
            except discord.HTTPException: pass
        for cid, info in list(self.channels.items()):
            if info["guild_id"] == ctx.guild.id: await self.remove_channel(cid)
        async with aiosqlite.connect(DB) as db:
            await db.execute("DELETE FROM setup WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
        await ctx.send("✅ TempVoice reset complete.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        data = self.setup.get(member.guild.id)
        if not data: return
        if after.channel and after.channel.id == data["join_id"]:
            category = member.guild.get_channel(data["category_id"])
            if not category: return
            vc = await member.guild.create_voice_channel(f"{member.display_name}'s VC", category=category, reason="TempVoice create")
            await self.save_channel(vc.id, member.guild.id, member.id)
            await vc.set_permissions(member, connect=True, manage_channels=True, move_members=True)
            await member.move_to(vc, reason="TempVoice join-to-create")
        if before.channel and before.channel.id in self.channels and not before.channel.members:
            cid = before.channel.id
            await self.remove_channel(cid)
            try: await before.channel.delete(reason="TempVoice empty")
            except discord.HTTPException: pass

    def help_custom(self):
        return "🔊", "Voice Commands", "Voice moderation and Astro-style TempVoice"


class TempVoiceSetupPanel(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        # The setup panel is informational; actual per-VC controls are posted in the VC chat.

    @discord.ui.button(label="How TempVoice Works", emoji="ℹ️", style=discord.ButtonStyle.primary, custom_id="tempvoice:how")
    async def how(self, interaction, button):
        data = self.cog.setup.get(self.guild_id)
        join = interaction.guild.get_channel(data["join_id"]) if data else None
        await interaction.response.send_message(f"Join {join.mention if join else 'the Join to Create channel'} to create your own temporary VC. Once inside, use `.tempvoice panel` to open your controls.", ephemeral=True)

    @discord.ui.button(label="Setup Info", emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="tempvoice:info")
    async def info(self, interaction, button):
        await interaction.response.send_message("TempVoice automatically creates a private voice channel for you, removes it when empty, and gives the owner Lock, Unlock, Hide, Show, Rename, Limit, Claim and Delete controls.", ephemeral=True)


# Per-VC panel command is intentionally separate so the owner can reopen it.
TempVoice.panel = commands.command(name="panel")(lambda self, ctx: None)
