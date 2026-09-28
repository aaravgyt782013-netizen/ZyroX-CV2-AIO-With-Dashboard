from __future__ import annotations
import os, re
import aiosqlite
import discord
from discord.ext import commands

DB = "db/automod.db"
RULES = [
    ("Anti spam", "More than 5 rapid messages"),
    ("Anti caps", "More than 70% uppercase in a long message"),
    ("Anti link", "Links except allowed Discord/Spotify/GIF links"),
    ("Anti invites", "Discord server invites"),
    ("Anti mass mention", "More than 4 mentions or @everyone"),
    ("Anti emoji spam", "More than 5 emojis"),
]
PUNISHMENTS = ["Mute", "Kick", "Ban"]

class AutomodV2(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("db", exist_ok=True)
        bot.loop.create_task(self._db())

    async def _db(self):
        async with aiosqlite.connect(DB) as db:
            await db.execute("CREATE TABLE IF NOT EXISTS automod (guild_id INTEGER PRIMARY KEY, enabled INTEGER DEFAULT 0)")
            await db.execute("CREATE TABLE IF NOT EXISTS automod_punishments (guild_id INTEGER, event TEXT, punishment TEXT, PRIMARY KEY (guild_id,event))")
            await db.execute("CREATE TABLE IF NOT EXISTS automod_ignored (guild_id INTEGER, type TEXT, id INTEGER, PRIMARY KEY (guild_id,type,id))")
            await db.execute("CREATE TABLE IF NOT EXISTS automod_logging (guild_id INTEGER PRIMARY KEY, log_channel INTEGER)")
            await db.commit()

    async def _enabled(self, guild_id):
        await self._db()
        async with aiosqlite.connect(DB) as db:
            row = await (await db.execute("SELECT enabled FROM automod WHERE guild_id=?", (guild_id,))).fetchone()
            return bool(row and row[0])

    async def _set(self, guild_id, enabled):
        await self._db()
        async with aiosqlite.connect(DB) as db:
            await db.execute("INSERT OR REPLACE INTO automod(guild_id,enabled) VALUES(?,?)", (guild_id, int(enabled)))
            await db.commit()

    async def _set_rules(self, guild_id, rules):
        await self._db()
        async with aiosqlite.connect(DB) as db:
            for rule in rules:
                await db.execute("INSERT OR REPLACE INTO automod_punishments(guild_id,event,punishment) VALUES(?,?,?)", (guild_id, rule, "Mute"))
            await db.commit()

    def _embed(self, title, description, color=0x5865F2):
        return discord.Embed(title=title, description=description, color=color)

    @commands.hybrid_group(name="automod", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def automod(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send(embed=self._embed("LightCore AutoMod", "Use /automod setup to configure protection."))

    @automod.command(name="setup")
    async def setup_cmd(self, ctx):
        await self._db()
        options = [discord.SelectOption(label=n, value=n, description=d) for n, d in RULES]
        select = discord.ui.Select(placeholder="Select AutoMod rules", min_values=1, max_values=len(options), options=options)
        view = discord.ui.View(timeout=120)
        view.add_item(select)
        done = discord.ui.Button(label="Enable Selected", style=discord.ButtonStyle.success)
        all_btn = discord.ui.Button(label="Enable All", style=discord.ButtonStyle.primary)
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.danger)
        view.add_item(done); view.add_item(all_btn); view.add_item(cancel)

        async def chosen(i):
            if i.user != ctx.author:
                await i.response.send_message("Only the setup user can use this panel.", ephemeral=True); return
            await i.response.defer()
            await self._set(ctx.guild.id, True)
            await self._set_rules(ctx.guild.id, select.values)
            await i.edit_original_response(embed=self._embed("AutoMod Enabled", "\n".join(f"✓ {x}" for x in select.values), 0x57F287), view=None)

        async def all_rules(i):
            if i.user != ctx.author:
                await i.response.send_message("Only the setup user can use this panel.", ephemeral=True); return
            await i.response.defer()
            selected = [x[0] for x in RULES]
            await self._set(ctx.guild.id, True); await self._set_rules(ctx.guild.id, selected)
            await i.edit_original_response(embed=self._embed("AutoMod Enabled", "\n".join(f"✓ {x}" for x in selected), 0x57F287), view=None)

        async def cancel_cb(i):
            if i.user != ctx.author:
                await i.response.send_message("Only the setup user can use this panel.", ephemeral=True); return
            await i.response.edit_message(embed=self._embed("Setup Cancelled", "No AutoMod settings were changed."), view=None)

        select.callback = chosen; done.callback = chosen; all_btn.callback = all_rules; cancel.callback = cancel_cb
        await ctx.send(embed=self._embed("LightCore AutoMod Setup", "Choose the protection rules you want enabled."), view=view)

    @automod.command(name="enable")
    async def enable(self, ctx):
        await self._set(ctx.guild.id, True)
        await ctx.send(embed=self._embed("AutoMod Enabled", "AutoMod is now enabled.", 0x57F287))

    @automod.command(name="disable")
    async def disable(self, ctx):
        await self._set(ctx.guild.id, False)
        await ctx.send(embed=self._embed("AutoMod Disabled", "AutoMod is now disabled.", 0xED4245))

    @automod.command(name="status")
    async def status(self, ctx):
        enabled = await self._enabled(ctx.guild.id)
        await self._db()
        async with aiosqlite.connect(DB) as db:
            rows = await (await db.execute("SELECT event,punishment FROM automod_punishments WHERE guild_id=?", (ctx.guild.id,))).fetchall()
        rules = "\n".join(f"• {e}: **{p}**" for e, p in rows) or "No rules configured."
        await ctx.send(embed=self._embed("AutoMod Status", f"Status: **{'Enabled' if enabled else 'Disabled'}**\n\n{rules}"))

    @automod.command(name="punishment")
    async def punishment(self, ctx, rule: str, punishment: str):
        if rule not in [x[0] for x in RULES] or punishment not in PUNISHMENTS:
            await ctx.send("Usage: /automod punishment <rule> <Mute|Kick|Ban>"); return
        await self._db()
        async with aiosqlite.connect(DB) as db:
            await db.execute("INSERT OR REPLACE INTO automod_punishments(guild_id,event,punishment) VALUES(?,?,?)", (ctx.guild.id, rule, punishment))
            await db.commit()
        await ctx.send(embed=self._embed("Punishment Updated", f"**{rule}** → **{punishment}**", 0x57F287))

    @automod.command(name="ignore")
    async def ignore(self, ctx, target_type: str, target: str):
        typ = target_type.lower()
        if typ not in ("channel", "role"):
            await ctx.send("Use channel or role."); return
        digits = re.sub(r"[^0-9]", "", target)
        if not digits:
            await ctx.send("Provide a valid channel or role mention/ID."); return
        oid = int(digits)
        obj = ctx.guild.get_channel(oid) if typ == "channel" else ctx.guild.get_role(oid)
        if not obj:
            await ctx.send("Target not found."); return
        await self._db()
        async with aiosqlite.connect(DB) as db:
            row = await (await db.execute("SELECT 1 FROM automod_ignored WHERE guild_id=? AND type=? AND id=?", (ctx.guild.id, typ, oid))).fetchone()
            if row:
                await db.execute("DELETE FROM automod_ignored WHERE guild_id=? AND type=? AND id=?", (ctx.guild.id, typ, oid))
                action = "removed from"
            else:
                await db.execute("INSERT OR IGNORE INTO automod_ignored(guild_id,type,id) VALUES(?,?,?)", (ctx.guild.id, typ, oid))
                action = "added to"
            await db.commit()
        await ctx.send(embed=self._embed("AutoMod Ignore Updated", f"{obj.mention} {action} the {typ} ignore list.", 0x57F287))

async def setup(bot):
    await bot.add_cog(AutomodV2(bot))
