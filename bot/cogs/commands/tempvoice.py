from __future__ import annotations
import aiosqlite
import discord
from discord.ext import commands

DB = "tempvoice_data.db"

class RenameModal(discord.ui.Modal, title="Rename VC"):
    name = discord.ui.TextInput(label="Channel name", max_length=100)
    def __init__(self, cog): super().__init__(); self.cog=cog
    async def on_submit(self, interaction):
        vc=await self.cog.owned_vc(interaction)
        if vc:
            await vc.edit(name=str(self.name.value))
            await interaction.response.send_message("✏️ VC renamed.",ephemeral=True)

class LimitModal(discord.ui.Modal, title="Set VC limit"):
    limit = discord.ui.TextInput(label="Limit (0-99, 0 = unlimited)", max_length=2)
    def __init__(self,cog): super().__init__(); self.cog=cog
    async def on_submit(self,interaction):
        vc=await self.cog.owned_vc(interaction)
        if not vc:return
        try:
            n=int(str(self.limit.value))
            if not 0<=n<=99: raise ValueError
        except ValueError:
            return await interaction.response.send_message("❌ Enter a number from 0 to 99.",ephemeral=True)
        await vc.edit(user_limit=n)
        await interaction.response.send_message(f"👥 Limit set to **{n or 'unlimited'}**.",ephemeral=True)

class TransferSelect(discord.ui.View):
    def __init__(self,cog,interaction): super().__init__(timeout=120); self.cog=cog; self.owner=interaction.user
    @discord.ui.select(cls=discord.ui.UserSelect,placeholder="Select the new VC owner",min_values=1,max_values=1)
    async def select(self,interaction,select):
        if interaction.user.id!=self.owner.id:return await interaction.response.send_message("❌ Only the current owner can transfer ownership.",ephemeral=True)
        vc=await self.cog.owned_vc(interaction)
        if not vc:return
        member=select.values[0]
        if member.bot:return await interaction.response.send_message("❌ Choose a human member.",ephemeral=True)
        await self.cog.set_owner(vc.id,member.id)
        await vc.set_permissions(member,manage_channels=True,move_members=True,connect=True)
        await interaction.response.send_message(f"👑 Ownership transferred to {member.mention}.",ephemeral=True)

class PermitSelect(discord.ui.View):
    def __init__(self,cog,interaction): super().__init__(timeout=120); self.cog=cog; self.owner=interaction.user
    @discord.ui.select(cls=discord.ui.UserSelect,placeholder="Select a member to permit",min_values=1,max_values=1)
    async def select(self,interaction,select):
        if interaction.user.id!=self.owner.id:return await interaction.response.send_message("❌ Only the VC owner can permit members.",ephemeral=True)
        vc=await self.cog.owned_vc(interaction)
        if not vc:return
        member=select.values[0]
        await vc.set_permissions(member,connect=True,view_channel=True)
        await interaction.response.send_message(f"✅ {member.mention} can now join your VC.",ephemeral=True)

class TempVoicePanel(discord.ui.View):
    def __init__(self,cog): super().__init__(timeout=None); self.cog=cog
    async def vc(self,i): return await self.cog.owned_vc(i)
    @discord.ui.button(label="Lock",emoji="🔒",style=discord.ButtonStyle.secondary,custom_id="tv:lock")
    async def lock(self,i,b):
        c=await self.vc(i)
        if c: await c.set_permissions(i.guild.default_role,connect=False); await i.response.send_message("🔒 Locked.",ephemeral=True)
    @discord.ui.button(label="Unlock",emoji="🔓",style=discord.ButtonStyle.secondary,custom_id="tv:unlock")
    async def unlock(self,i,b):
        c=await self.vc(i)
        if c: await c.set_permissions(i.guild.default_role,connect=True); await i.response.send_message("🔓 Unlocked.",ephemeral=True)
    @discord.ui.button(label="Hide",emoji="👁️",style=discord.ButtonStyle.secondary,custom_id="tv:hide")
    async def hide(self,i,b):
        c=await self.vc(i)
        if c: await c.set_permissions(i.guild.default_role,view_channel=False); await i.response.send_message("👁️ Hidden.",ephemeral=True)
    @discord.ui.button(label="Show",emoji="👀",style=discord.ButtonStyle.secondary,custom_id="tv:show")
    async def show(self,i,b):
        c=await self.vc(i)
        if c: await c.set_permissions(i.guild.default_role,view_channel=True); await i.response.send_message("👀 Visible.",ephemeral=True)
    @discord.ui.button(label="Rename",emoji="✏️",style=discord.ButtonStyle.primary,row=1,custom_id="tv:rename")
    async def rename(self,i,b):
        if await self.vc(i): await i.response.send_modal(RenameModal(self.cog))
    @discord.ui.button(label="Limit",emoji="👥",style=discord.ButtonStyle.primary,row=1,custom_id="tv:limit")
    async def limit(self,i,b):
        if await self.vc(i): await i.response.send_modal(LimitModal(self.cog))
    @discord.ui.button(label="Transfer",emoji="👑",style=discord.ButtonStyle.primary,row=1,custom_id="tv:transfer")
    async def transfer(self,i,b):
        if await self.vc(i): await i.response.send_message("Select the new owner:",view=TransferSelect(self.cog,i),ephemeral=True)
    @discord.ui.button(label="Permit",emoji="✅",style=discord.ButtonStyle.primary,row=2,custom_id="tv:permit")
    async def permit(self,i,b):
        if await self.vc(i): await i.response.send_message("Select a member to permit:",view=PermitSelect(self.cog,i),ephemeral=True)
    @discord.ui.button(label="Info",emoji="ℹ️",style=discord.ButtonStyle.secondary,row=2,custom_id="tv:info")
    async def info(self,i,b):
        c=await self.vc(i)
        if c:
            await i.response.send_message(f"📊 **{c.name}**\n👥 Members: **{len(c.members)}**\n🎚️ Limit: **{c.user_limit or 'Unlimited'}**\n🔊 Bitrate: **{c.bitrate // 1000}kbps**",ephemeral=True)
    @discord.ui.button(label="Disconnect",emoji="🚪",style=discord.ButtonStyle.secondary,row=2,custom_id="tv:disconnect")
    async def disconnect(self,i,b):
        c=await self.vc(i)
        if not c:return
        others=[m for m in c.members if m.id!=i.user.id and not m.bot]
        if not others:return await i.response.send_message("ℹ️ Nobody else is in your VC.",ephemeral=True)
        for m in others:
            try: await m.move_to(None)
            except (discord.Forbidden,discord.HTTPException): pass
        await i.response.send_message(f"🚪 Disconnected **{len(others)}** member(s).",ephemeral=True)
    @discord.ui.button(label="Claim",emoji="🫴",style=discord.ButtonStyle.primary,row=3,custom_id="tv:claim")
    async def claim(self,i,b):
        voice=i.user.voice
        if not voice or voice.channel.id not in self.cog.channels:return await i.response.send_message("❌ Join a temporary VC first.",ephemeral=True)
        data=self.cog.channels[voice.channel.id]; owner=i.guild.get_member(data["owner_id"])
        if owner and owner.voice and owner.voice.channel==voice.channel:return await i.response.send_message("❌ Current owner is still inside.",ephemeral=True)
        await self.cog.set_owner(voice.channel.id,i.user.id); await i.response.send_message("🫴 VC claimed.",ephemeral=True)
    @discord.ui.button(label="Delete",emoji="🗑️",style=discord.ButtonStyle.danger,row=3,custom_id="tv:delete")
    async def delete(self,i,b):
        c=await self.vc(i)
        if c: await self.cog.remove_channel(c.id); await c.delete(); await i.response.send_message("🗑️ VC deleted.",ephemeral=True)

class SetupView(discord.ui.View):
    def __init__(self,cog,ctx): super().__init__(timeout=300); self.cog=cog; self.ctx=ctx
    @discord.ui.button(label="Create a voice channel",emoji="➕",style=discord.ButtonStyle.primary)
    async def create(self,i,b):
        if i.user.id!=self.ctx.author.id:return await i.response.send_message("❌ Only the setup user can configure this.",ephemeral=True)
        await i.response.send_message("Choose the **category** where the Join to Create channel should be made:",view=CategorySelect(self.cog,self.ctx),ephemeral=True)
    @discord.ui.button(label="Use existing channel",emoji="🎙️",style=discord.ButtonStyle.secondary)
    async def existing(self,i,b):
        if i.user.id!=self.ctx.author.id:return await i.response.send_message("❌ Only the setup user can configure this.",ephemeral=True)
        await i.response.send_message("Choose the existing **voice channel** to use as Join to Create:",view=VoiceSelect(self.cog,self.ctx),ephemeral=True)

class CategorySelect(discord.ui.View):
    def __init__(self,cog,ctx): super().__init__(timeout=300); self.cog=cog; self.ctx=ctx
    @discord.ui.select(placeholder="Select a server category",min_values=1,max_values=1)
    async def select(self,i,select):
        cat=i.guild.get_channel(int(select.values[0]))
        if not isinstance(cat,discord.CategoryChannel):return await i.response.send_message("❌ Invalid category.",ephemeral=True)
        await i.response.send_message("Now choose the **text channel** where the TempVoice interface should be posted:",view=TextSelect(self.cog,self.ctx,cat),ephemeral=True)

class VoiceSelect(discord.ui.View):
    def __init__(self,cog,ctx): super().__init__(timeout=300); self.cog=cog; self.ctx=ctx
    @discord.ui.select(placeholder="Select an existing voice channel",min_values=1,max_values=1)
    async def select(self,i,select):
        ch=i.guild.get_channel(int(select.values[0]))
        if not isinstance(ch,discord.VoiceChannel):return await i.response.send_message("❌ Invalid voice channel.",ephemeral=True)
        await i.response.send_message("Now choose the **text channel** where the TempVoice interface should be posted:",view=TextSelect(self.cog,self.ctx,ch.category,existing=ch),ephemeral=True)

class TextSelect(discord.ui.View):
    def __init__(self,cog,ctx,cat,existing=None):
        super().__init__(timeout=300); self.cog=cog; self.ctx=ctx; self.cat=cat; self.existing=existing
        channels=[c for c in ctx.guild.text_channels if c.permissions_for(ctx.guild.me).send_messages]
        opts=[discord.SelectOption(label=c.name[:100],value=str(c.id),description="Use this channel for the TempVoice interface") for c in channels[:25]]
        self.remove_item(self.select)
        self.add_item(discord.ui.Select(placeholder="Select the interface text channel",options=opts,min_values=1,max_values=1,custom_id="tv:interface") )
        self.children[0].callback=self.choose
    async def choose(self,i,select):
        ch=i.guild.get_channel(int(select.values[0]))
        if not isinstance(ch,discord.TextChannel):return await i.response.send_message("❌ Invalid text channel.",ephemeral=True)
        await self.cog.finish_setup(i,self.cat,self.existing,ch)

class TempVoice(commands.Cog):
    def __init__(self,bot):
        self.bot=bot; self.setup={}; self.channels={}; bot.loop.create_task(self.load())
    async def load(self):
        async with aiosqlite.connect(DB) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS setup (guild_id INTEGER PRIMARY KEY,join_id INTEGER,category_id INTEGER,panel_channel_id INTEGER,panel_message_id INTEGER)")
            await db.execute("CREATE TABLE IF NOT EXISTS channels (channel_id INTEGER PRIMARY KEY,guild_id INTEGER,owner_id INTEGER)"); await db.commit()
            async with db.execute("SELECT guild_id,join_id,category_id,panel_channel_id,panel_message_id FROM setup") as c:
                async for r in c:self.setup[r[0]]={"join_id":r[1],"category_id":r[2],"panel_channel_id":r[3],"panel_message_id":r[4]}
            async with db.execute("SELECT channel_id,guild_id,owner_id FROM channels") as c:
                async for r in c:self.channels[r[0]]={"guild_id":r[1],"owner_id":r[2]}
        await self.bot.wait_until_ready()
        for gid,d in self.setup.items():
            g=self.bot.get_guild(gid); ch=g.get_channel(d["panel_channel_id"]) if g else None
            if ch:
                try:m=await ch.fetch_message(d["panel_message_id"]); await m.edit(view=TempVoicePanel(self))
                except:pass
    async def save_setup(self,gid,d):
        async with aiosqlite.connect(DB) as db:await db.execute("INSERT OR REPLACE INTO setup VALUES(?,?,?,?,?)",(gid,d["join_id"],d["category_id"],d["panel_channel_id"],d["panel_message_id"]));await db.commit()
    async def save_channel(self,cid,gid,oid):
        self.channels[cid]={"guild_id":gid,"owner_id":oid}
        async with aiosqlite.connect(DB) as db:await db.execute("INSERT OR REPLACE INTO channels VALUES(?,?,?)",(cid,gid,oid));await db.commit()
    async def remove_channel(self,cid):
        self.channels.pop(cid,None)
        async with aiosqlite.connect(DB) as db:await db.execute("DELETE FROM channels WHERE channel_id=?",(cid,));await db.commit()
    async def set_owner(self,cid,oid):
        if cid in self.channels:self.channels[cid]["owner_id"]=oid
        async with aiosqlite.connect(DB) as db:await db.execute("UPDATE channels SET owner_id=? WHERE channel_id=?",(oid,cid));await db.commit()
    async def owned_vc(self,i):
        v=i.user.voice
        if not v or v.channel.id not in self.channels:return await i.response.send_message("❌ Join your temporary VC first.",ephemeral=True) or None
        if self.channels[v.channel.id]["owner_id"]!=i.user.id:return await i.response.send_message("❌ You don't own this VC.",ephemeral=True) or None
        return v.channel
    async def lock_interface(self,ch):
        me=ch.guild.me
        await ch.set_permissions(ch.guild.default_role,view_channel=True,send_messages=False,add_reactions=False)
        if me: await ch.set_permissions(me,view_channel=True,send_messages=True,send_messages_in_threads=True,embed_links=True,attach_files=True)
    async def finish_setup(self,i,cat,existing,interface):
        if i.guild.id in self.setup:return await i.response.send_message("❌ TempVoice is already configured.",ephemeral=True)
        join=existing or await i.guild.create_voice_channel("➕ Join to Create",category=cat)
        panel=await interface.send("## 🎙️ TempVoice\nManage the temporary voice channel you currently own using the controls below.\n\n🔒 Lock  •  🔓 Unlock  •  👁️ Hide  •  👀 Show\n✏️ Rename  •  👥 Limit  •  👑 Transfer  •  ✅ Permit\nℹ️ Info  •  🚪 Disconnect  •  🫴 Claim  •  🗑️ Delete",view=TempVoicePanel(self))
        await self.lock_interface(interface)
        d={"join_id":join.id,"category_id":join.category.id if join.category else 0,"panel_channel_id":interface.id,"panel_message_id":panel.id};self.setup[i.guild.id]=d;await self.save_setup(i.guild.id,d)
        await i.response.send_message(f"✅ TempVoice configured!\n🎙️ Join-to-create: {join.mention}\n📋 Interface: {interface.mention}\n🔒 Members cannot send messages in the interface channel.",ephemeral=True)
    @commands.group(name="tempvoice",aliases=["tv"],invoke_without_command=True)
    @commands.guild_only()
    async def tempvoice(self,ctx):await ctx.send(f"Use `{ctx.prefix}tempvoice setup` to configure TempVoice.")
    @tempvoice.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_cmd(self,ctx):
        if ctx.guild.id in self.setup:return await ctx.send("❌ TempVoice is already configured.")
        await ctx.send("## 🎙️ TempVoice Setup\nChoose how the **Join to Create** channel should be configured.",view=SetupView(self,ctx))
    @tempvoice.command(name="panel")
    async def panel_cmd(self,ctx):
        if ctx.guild.id not in self.setup:return await ctx.send(f"❌ Not configured. Use `{ctx.prefix}tempvoice setup`.")
        await ctx.send("## 🎙️ TempVoice\nUse the buttons below to configure the temporary voice channel you currently own.",view=TempVoicePanel(self))
    @tempvoice.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_cmd(self,ctx):
        d=self.setup.pop(ctx.guild.id,None)
        if not d:return await ctx.send("❌ TempVoice is not configured.")
        cat=ctx.guild.get_channel(d["category_id"])
        if cat:
            for c in list(cat.channels):
                try:await c.delete()
                except:pass
            try:await cat.delete()
            except:pass
        for cid,x in list(self.channels.items()):
            if x["guild_id"]==ctx.guild.id:await self.remove_channel(cid)
        async with aiosqlite.connect(DB) as db:await db.execute("DELETE FROM setup WHERE guild_id=?",(ctx.guild.id,));await db.commit()
        await ctx.send("✅ TempVoice reset.")
    @commands.Cog.listener()
    async def on_voice_state_update(self,member,before,after):
        d=self.setup.get(member.guild.id)
        if not d:return
        if after.channel and after.channel.id==d["join_id"]:
            cat=member.guild.get_channel(d["category_id"])
            if cat:
                vc=await member.guild.create_voice_channel(f"{member.display_name}'s VC",category=cat)
                await self.save_channel(vc.id,member.guild.id,member.id)
                await vc.set_permissions(member,manage_channels=True,move_members=True,connect=True)
                await member.move_to(vc)
        if before.channel and before.channel.id in self.channels and not before.channel.members:
            cid=before.channel.id;await self.remove_channel(cid)
            try:await before.channel.delete()
            except:pass
    def help_custom(self):return "🔊","Voice Commands","Voice moderation + TempVoice"

async def setup(bot):await bot.add_cog(TempVoice(bot))
