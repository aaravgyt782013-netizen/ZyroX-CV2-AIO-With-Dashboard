from __future__ import annotations
import asyncio, json, os
from datetime import datetime
from typing import Optional
import discord
from discord.ext import commands

CONFIG_PATH = "jsondb/lightcore_logging.json"
STREAMS = {
    "message": ("message-logs", "Messages edited, deleted and pinned/unpinned"),
    "member": ("member-logs", "Joins, leaves, nicknames and role changes"),
    "moderation": ("moderation-logs", "Bans, unbans, kicks, timeouts and AutoMod"),
    "server": ("server-logs", "Channels, roles, emojis, invites and server changes"),
    "voice": ("voice-logs", "Voice joins, leaves, moves and state changes"),
}

class LoggingV2(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.configs: dict[int, dict] = {}
        os.makedirs("jsondb", exist_ok=True)
        asyncio.create_task(self._load())

    async def _load(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    self.configs = {int(k): v for k, v in json.load(f).items()}
        except Exception:
            self.configs = {}

    async def _save(self):
        tmp = CONFIG_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in self.configs.items()}, f, indent=2)
        os.replace(tmp, CONFIG_PATH)

    def _overwrites(self, guild):
        return {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, read_message_history=True),
        }

    async def _ensure_setup(self, guild):
        if not guild.me or not guild.me.guild_permissions.manage_channels:
            raise RuntimeError("I need Manage Channels to create the logging setup.")
        category = discord.utils.get(guild.categories, name="lightcore-logs")
        if not category:
            category = await guild.create_category("lightcore-logs", overwrites=self._overwrites(guild), reason="LightCore logging setup")
        ids = {}
        for key, (name, topic) in STREAMS.items():
            channel = discord.utils.get(category.text_channels, name=name)
            if not channel:
                channel = await guild.create_text_channel(name, category=category, overwrites=self._overwrites(guild), topic=topic, reason="LightCore logging setup")
            ids[key] = channel.id
        self.configs[guild.id] = {"category_id": category.id, "channels": ids, "updated_at": datetime.utcnow().isoformat()}
        await self._save()
        try:
            import aiosqlite
            os.makedirs("db", exist_ok=True)
            async with aiosqlite.connect("db/automod.db") as db:
                await db.execute("CREATE TABLE IF NOT EXISTS automod_logging (guild_id INTEGER PRIMARY KEY, log_channel INTEGER)")
                await db.execute("INSERT OR REPLACE INTO automod_logging (guild_id, log_channel) VALUES (?, ?)", (guild.id, ids["moderation"]))
                await db.commit()
        except Exception:
            pass
        return category, ids

    async def _channel(self, guild, stream):
        cfg = self.configs.get(guild.id)
        if not cfg:
            return None
        cid = cfg.get("channels", {}).get(stream)
        return guild.get_channel(cid) if cid else None

    async def _log(self, guild, stream, title, description, color=0x5865F2, fields=None):
        channel = await self._channel(guild, stream)
        if not channel:
            return
        embed = discord.Embed(title=title, description=description[:4096], color=color, timestamp=discord.utils.utcnow())
        for name, value in fields or []:
            embed.add_field(name=name, value=str(value)[:1024], inline=True)
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.hybrid_group(name="log", invoke_without_command=True)
    @commands.guild_only()
    async def log(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Use /log setup to create the five LightCore logging channels.")

    @log.command(name="setup")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def setup(self, ctx):
        try:
            category, ids = await self._ensure_setup(ctx.guild)
            mentions = "\n".join(f"• **{name.title()}** → <#{cid}>" for name, cid in ids.items())
            embed = discord.Embed(title="LightCore Logging Setup", description="Your private five-channel logging system is ready.", color=0x5865F2)
            embed.add_field(name="Category", value=category.mention, inline=False)
            embed.add_field(name="Five Log Streams", value=mentions, inline=False)
            embed.set_footer(text="Run /log setup again to repair missing channels.")
            await ctx.send(embed=embed)
        except RuntimeError as e:
            await ctx.send(f"❌ {e}")
        except discord.Forbidden:
            await ctx.send("❌ I don't have enough permission to create the logging category/channels.")

    @log.command(name="status")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def status(self, ctx):
        cfg = self.configs.get(ctx.guild.id)
        if not cfg:
            await ctx.send("❌ Logging is not configured. Use /log setup.")
            return
        lines = []
        for key, (name, _) in STREAMS.items():
            ch = await self._channel(ctx.guild, key)
            lines.append(f"• **{name}** → {ch.mention if ch else 'missing'}")
        await ctx.send(embed=discord.Embed(title="LightCore Logging Status", description="\n".join(lines), color=0x5865F2))

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild and not message.author.bot:
            await self._log(message.guild, "message", "Message Deleted", f"Message by {message.author.mention} was deleted in {message.channel.mention}.", 0xED4245, [("User", f"{message.author} ({message.author.id})"), ("Content", message.content[:900] or "No text")])

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild and not before.author.bot and before.content != after.content:
            await self._log(before.guild, "message", "Message Edited", f"{before.author.mention} edited a message in {before.channel.mention}.", 0xFEE75C, [("Before", before.content[:900] or "No text"), ("After", after.content[:900] or "No text")])

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self._log(member.guild, "member", "Member Joined", f"{member.mention} joined the server.", 0x57F287, [("Account", f"{member} ({member.id})")])

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self._log(member.guild, "member", "Member Left", f"{member} left the server.", 0xED4245, [("User ID", str(member.id))])

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick != after.nick:
            await self._log(after.guild, "member", "Nickname Changed", f"{after.mention} changed nickname.", 0xFEE75C, [("Before", before.nick or "None"), ("After", after.nick or "None")])
        if before.roles != after.roles:
            added = [r.mention for r in after.roles if r not in before.roles]
            removed = [r.mention for r in before.roles if r not in after.roles]
            if added or removed:
                await self._log(after.guild, "member", "Roles Updated", f"Roles changed for {after.mention}.", 0x5865F2, [("Added", ", ".join(added) or "None"), ("Removed", ", ".join(removed) or "None")])

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self._log(guild, "moderation", "Member Banned", f"{user.mention} was banned.", 0xED4245, [("User ID", str(user.id))])

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self._log(guild, "moderation", "Member Unbanned", f"{user} was unbanned.", 0x57F287, [("User ID", str(user.id))])

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return
        action = "Joined" if after.channel and not before.channel else "Left" if before.channel and not after.channel else "Moved"
        place = after.channel.mention if after.channel else before.channel.mention
        await self._log(member.guild, "voice", f"Voice {action}", f"{member.mention} {action.lower()} {place}.", 0x5865F2)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self._log(channel.guild, "server", "Channel Created", f"{channel.mention} was created.", 0x57F287)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self._log(channel.guild, "server", "Channel Deleted", f"#{channel.name} was deleted.", 0xED4245)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self._log(role.guild, "server", "Role Created", f"{role.mention} was created.", 0x57F287)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self._log(role.guild, "server", "Role Deleted", f"@{role.name} was deleted.", 0xED4245)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        if before.name != after.name or before.permissions != after.permissions:
            await self._log(after.guild, "server", "Role Updated", f"{after.mention} was updated.", 0xFEE75C)

async def setup(bot):
    await bot.add_cog(LoggingV2(bot))
