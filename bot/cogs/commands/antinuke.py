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

import discord
from utils.emoji import CROSS, EMOTE, TICK, ZSAFE, ZSETTINGS
from discord.ext import commands
from discord.ui import LayoutView, TextDisplay, Separator, Container, Button, ActionRow
import aiosqlite
import asyncio
import json
from utils.Tools import *
from utils.cv2 import CV2, build_container
from utils.config import *




class Antinuke(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self._db_ready = asyncio.Event()
    self.bot.loop.create_task(self.initialize_db())

  async def initialize_db(self):
    self.db = await aiosqlite.connect('db/anti.db')
    await self.db.execute('''
        CREATE TABLE IF NOT EXISTS antinuke (
            guild_id INTEGER PRIMARY KEY,
            status BOOLEAN
        )
    ''')
    await self.db.execute('''
        CREATE TABLE IF NOT EXISTS limit_settings (
            guild_id INTEGER,
            action_type TEXT,
            action_limit INTEGER,
            time_window INTEGER,
            PRIMARY KEY (guild_id, action_type)
        )
    ''')
    await self.db.execute('''
        CREATE TABLE IF NOT EXISTS whitelisted_users (
            guild_id INTEGER,
            user_id INTEGER,
            ban INTEGER DEFAULT 0,
            kick INTEGER DEFAULT 0,
            botadd INTEGER DEFAULT 0,
            chcr INTEGER DEFAULT 0,
            chdl INTEGER DEFAULT 0,
            chup INTEGER DEFAULT 0,
            meneve INTEGER DEFAULT 0,
            serverup INTEGER DEFAULT 0,
            memup INTEGER DEFAULT 0,
            prune INTEGER DEFAULT 0,
            rlcr INTEGER DEFAULT 0,
            rldl INTEGER DEFAULT 0,
            rlup INTEGER DEFAULT 0,
            mngweb INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    ''')
    await self.db.execute('''
        CREATE TABLE IF NOT EXISTS antinuke_settings (
            guild_id INTEGER PRIMARY KEY,
            whitelist_role_id INTEGER,
            log_channel_id INTEGER,
            punishments TEXT NOT NULL DEFAULT '{}'
        )
    ''')
    await self.db.commit()
    self._db_ready.set()

    
  async def enable_limit_settings(self, guild_id):
    default_limits = DEFAULT_LIMITS
    for action, limit in default_limits.items():
      await self.db.execute('INSERT OR REPLACE INTO limit_settings (guild_id, action_type, action_limit, time_window) VALUES (?, ?, ?, ?)', (guild_id, action, limit, TIME_WINDOW))
      await self.db.commit()

  async def disable_limit_settings(self, guild_id):
    await self.db.execute('DELETE FROM limit_settings WHERE guild_id = ?', (guild_id,))
    await self.db.commit()


  @commands.hybrid_command(name='antinuke', aliases=['antiwizz', 'anti'], help="Enables/Disables Anti-Nuke Module in the server")
  
  @blacklist_check()
  @ignore_check()
  @commands.cooldown(1, 4, commands.BucketType.user)
  @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
  @commands.guild_only()
  @commands.has_permissions(administrator=True)
  async def antinuke(self, ctx, option: str = None):
    guild_id = ctx.guild.id
    pre=ctx.prefix

    async with self.db.execute('SELECT status FROM antinuke WHERE guild_id = ?', (guild_id,)) as cursor:
      row = await cursor.fetchone()

    async with self.db.execute(
            "SELECT owner_id FROM extraowners WHERE guild_id = ? AND owner_id = ?",
            (ctx.guild.id, ctx.author.id)
        ) as cursor:
            check = await cursor.fetchone()

    is_owner = ctx.author.id == ctx.guild.owner_id
    if not is_owner and not check:
      view = CV2(f"{CROSS} Access Denied", "Only Server Owner or Extra Owner can Run this Command!")
      return await ctx.send(view=view)

    is_activated = row[0] if row else False
    await self._db_ready.wait()

    if option and option.lower() == 'setup':
      needed = ctx.guild.me.guild_permissions
      if not needed.manage_roles or not needed.manage_channels or not needed.view_audit_log:
        return await ctx.send(view=CV2(f"{CROSS} Setup Failed", "I need Manage Roles, Manage Channels, and View Audit Log to run the automatic setup."))

      async with self.db.execute('SELECT whitelist_role_id, log_channel_id, punishments FROM antinuke_settings WHERE guild_id = ?', (guild_id,)) as cur:
        existing = await cur.fetchone()

      whitelist_role = ctx.guild.get_role(existing[0]) if existing and existing[0] else None
      log_channel = ctx.guild.get_channel(existing[1]) if existing and existing[1] else None

      if whitelist_role is None:
        whitelist_role = discord.utils.find(lambda r: r.name == f"{BRAND_NAME} Antinuke Whitelist", ctx.guild.roles)
      if whitelist_role is None:
        whitelist_role = await ctx.guild.create_role(
          name=f"{BRAND_NAME} Antinuke Whitelist",
          color=discord.Color.gold(),
          mentionable=True,
          reason=f"{BRAND_NAME} antinuke automatic setup"
        )

      if log_channel is None:
        log_channel = discord.utils.find(
          lambda ch: ch.name == "lightcore-antinuke-logs" and isinstance(ch, discord.TextChannel),
          ctx.guild.text_channels
        )
      if log_channel is None:
        overwrites = {
          ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
          ctx.guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)
        }
        if ctx.guild.owner:
          overwrites[ctx.guild.owner] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
        log_channel = await ctx.guild.create_text_channel(
          "lightcore-antinuke-logs",
          overwrites=overwrites,
          reason=f"{BRAND_NAME} antinuke automatic setup"
        )

      if whitelist_role < ctx.guild.me.top_role and whitelist_role not in ctx.author.roles:
        try:
          await ctx.author.add_roles(whitelist_role, reason=f"{BRAND_NAME} antinuke whitelist owner")
        except discord.HTTPException:
          pass

      defaults = {
        "ban": "ban", "kick": "ban", "botadd": "ban", "channel_create": "ban",
        "channel_delete": "ban", "channel_update": "ban", "role_create": "ban",
        "role_delete": "ban", "role_update": "ban", "member_update": "ban",
        "guild_update": "ban", "webhook": "ban", "prune": "ban", "everyone": "timeout"
      }
      try:
        punishments = json.loads(existing[2]) if existing and existing[2] else {}
      except Exception:
        punishments = {}
      for key, value in defaults.items():
        punishments.setdefault(key, value)

      await self.db.execute(
        'INSERT OR REPLACE INTO antinuke_settings (guild_id, whitelist_role_id, log_channel_id, punishments) VALUES (?, ?, ?, ?)',
        (guild_id, whitelist_role.id, log_channel.id, json.dumps(punishments))
      )
      await self.db.execute('INSERT OR REPLACE INTO antinuke (guild_id, status) VALUES (?, 1)', (guild_id,))
      await self.enable_limit_settings(guild_id)
      await self.db.commit()
      await self._sync_whitelist_role(ctx.guild, whitelist_role)

      embed = discord.Embed(title=f"{ZSAFE} {BRAND_NAME} Antinuke Setup Complete", color=0xF1C40F)
      embed.description = (
        f"Protection: {TICK} Enabled\n"
        f"Whitelist role: {whitelist_role.mention}\n"
        f"Security logs: {log_channel.mention}\n\n"
        f"Members with the whitelist role are ignored by the existing antinuke enforcement modules.\n"
        f"Use {ctx.prefix}antinuke disable to turn protection off.\n"
        f"Use {ctx.prefix}antinuke punishment <event> <ban|kick|timeout|off> to configure the saved policy."
      )
      await ctx.send(embed=embed)
      return

    if option and option.lower() == "punishment":
      event = (action or "").lower().strip()
      value = (punishment or "").lower().strip()
      allowed_events = {"ban","kick","botadd","channel_create","channel_delete","channel_update","role_create","role_delete","role_update","member_update","guild_update","webhook","prune","everyone"}
      allowed_values = {"ban","kick","timeout","off"}
      if event not in allowed_events or value not in allowed_values:
        return await ctx.send(view=CV2(f"{CROSS} Invalid punishment", "Use: antinuke punishment <event> <ban|kick|timeout|off>"))
      async with self.db.execute("SELECT punishments FROM antinuke_settings WHERE guild_id = ?", (guild_id,)) as cur:
        row2 = await cur.fetchone()
      try:
        punishments = json.loads(row2[0]) if row2 and row2[0] else {}
      except Exception:
        punishments = {}
      punishments[event] = value
      if row2:
        await self.db.execute("UPDATE antinuke_settings SET punishments = ? WHERE guild_id = ?", (json.dumps(punishments), guild_id))
      else:
        await self.db.execute("INSERT INTO antinuke_settings (guild_id, whitelist_role_id, log_channel_id, punishments) VALUES (?, NULL, NULL, ?)", (guild_id, json.dumps(punishments)))
      await self.db.commit()
      await ctx.send(view=CV2(f"{TICK} Punishment updated", f"{event} is now configured as {value}."))
      return

    if option is None:
      view = CV2(
        f"{ZSAFE} {BRAND_NAME} Security",
        "**Antinuke Defense Mode** — Protect your server from harmful admin actions with smart automated security protocols.",
        "**Core Functionalities**\n"
        "• Auto-ban malicious admin activities instantly.\n"
        "• Whitelist protection for trusted users.\n"
        "• Live monitoring of admin actions.\n"
        "• Rapid threat detection & neutralization.",
        "**Configuration Panel**\n"
        f"{TICK} Automatic Setup: `antinuke setup`\n"
        f"{TICK} Enable Protection: `antinuke enable`\n"
        f"{CROSS} Disable Protection: `antinuke disable`"
      )
      await ctx.send(view=view)

    elif option.lower() == 'enable':
      if is_activated:
        view = CV2(
          f"Security Settings For {ctx.guild.name}",
          f"Your server __**already has Antinuke enabled.**__\n\nCurrent Status: {TICK} Enabled\nTo Disable use `antinuke disable`"
        )
        await ctx.send(view=view)
      else:
        
        setup_view = CV2(f"Antinuke Setup {EMOTE}", f"{TICK} | Initializing Quick Setup!")
        setup_message = await ctx.send(view=setup_view)

        
        if not ctx.guild.me.guild_permissions.administrator:
          view = CV2(f"Antinuke Setup {EMOTE}",
            f"{TICK} | Initializing Quick Setup!\n"
            f"{CROSS} | **Ops! It seems I Don't Have Administrator Perm To enable antinuke**.")
          await setup_message.edit(view=view)
          return

        await asyncio.sleep(1)
        view = CV2(f"Antinuke Setup {EMOTE}",
          f"{TICK} | Initializing Quick Setup!\n"
          f"{TICK} Checking {BRAND_NAME}'s role position for optimal configuration...")
        await setup_message.edit(view=view)

        await asyncio.sleep(1)
        view = CV2(f"Antinuke Setup {EMOTE}",
          f"{TICK} | Initializing Quick Setup!\n"
          f"{TICK} Checking {BRAND_NAME}'s role position for optimal configuration...\n"
          f"{TICK} | Crafting and configuring the {BRAND_NAME} Supreme role...")
        await setup_message.edit(view=view)
        
        try:
          role = await ctx.guild.create_role(
            name=f"{BRAND_NAME} Supreme™",
            color=0xFF0000,
            permissions=discord.Permissions(administrator=True),
            hoist=False,
            mentionable=False,
            reason="Antinuke setup Role Creation"
          )
          await ctx.guild.me.add_roles(role)
        except discord.Forbidden:
          view = CV2("Antinuke Setup", f"{CROSS} | **Uh oh! I don't Have perms to enable antinuke**.")
          await setup_message.edit(view=view)
          return
        except discord.HTTPException as e:
          view = CV2("Antinuke Setup", f"{CROSS} | **Uh: HTTPException: {e}\nCheck Guild Audit Logs**.")
          await setup_message.edit(view=view)
          return

        await asyncio.sleep(1)
        view = CV2(f"Antinuke Setup {EMOTE}",
          f"{TICK} | Initializing Quick Setup!\n"
          f"{TICK} Checking {BRAND_NAME}'s role position...\n"
          f"{TICK} | Crafting the {BRAND_NAME} Supreme role...\n"
          f"{TICK} | Ensuring precise placement of the {BRAND_NAME} Supreme™ role...")
        await setup_message.edit(view=view)

        try:
          await ctx.guild.edit_role_positions(positions={role: 1})
        except discord.Forbidden:
          view = CV2("Antinuke Setup", f"{CROSS} | Ops! I don't have sufficient perms to move role.")
          await setup_message.edit(view=view)
          return
        except discord.HTTPException as e:
          view = CV2("Antinuke Setup", f"{CROSS} | Setup failed: HTTPException: {e}.")
          await setup_message.edit(view=view)
          return

        await asyncio.sleep(1)
        await asyncio.sleep(1)

        await self.db.execute('INSERT OR REPLACE INTO antinuke (guild_id, status) VALUES (?, ?)', (guild_id, True))
        await self.db.commit()

        await asyncio.sleep(1)
        await setup_message.delete()

        modules = (
          f"{TICK} **Anti Ban**\n"
          f"{TICK} **Anti Kick**\n"
          f"{TICK} **Anti Bot**\n"
          f"{TICK} **Anti Channel Create**\n"
          f"{TICK} **Anti Channel Delete**\n"
          f"{TICK} **Anti Channel Update**\n"
          f"{TICK} **Anti Everyone/Here**\n"
          f"{TICK} **Anti Role Create**\n"
          f"{TICK} **Anti Role Delete**\n"
          f"{TICK} **Anti Role Update**\n"
          f"{TICK} **Anti Member Update**\n"
          f"{TICK} **Anti Guild Update**\n"
          f"{TICK} **Anti Integration**\n"
          f"{TICK} **Anti Webhook Create**\n"
          f"{TICK} **Anti Webhook Delete**\n"
          f"{TICK} **Anti Webhook Update**\n"
          f"{TICK} **Anti Prune**\n"
          f"{TICK} **Auto Recovery**"
        )

        punishment_btn = Button(label="Show Punishment Type", style=discord.ButtonStyle.secondary)
        punishment_btn.callback = self._show_punishment

        result_view = LayoutView(timeout=None)
        result_view.add_item(
          build_container(
            TextDisplay(f"**{ZSETTINGS} Security Settings For {ctx.guild.name}**"),
            Separator(visible=True),
            TextDisplay("Tip: For optimal functionality, please ensure that my role has **Administration** permissions and is positioned at the **Top** of the roles list."),
            Separator(visible=True),
            TextDisplay(f"**Modules Enabled**\n{modules}"),
            Separator(visible=True),
            TextDisplay(f"Successfully Enabled Antinuke | Powered by {BRAND_NAME} Development™"),
            ActionRow(punishment_btn)
          )
        )

        await ctx.send(view=result_view)

    elif option.lower() == 'disable':
      if not is_activated:
        view = CV2(
          f"Security Settings For {ctx.guild.name}",
          f"Uhh, looks like your server hasn't enabled Antinuke.\n\nCurrent Status: {CROSS} Disabled\n\nTo Enable use `antinuke enable`"
        )
      else:
        await self.db.execute('DELETE FROM antinuke WHERE guild_id = ?', (guild_id,))
        await self.db.commit()
        view = CV2(
          f"Security Settings For {ctx.guild.name}",
          f"Successfully disabled Antinuke for this server.\n\nCurrent Status: {CROSS} Disabled\n\nTo Enable use `antinuke enable`"
        )
      await ctx.send(view=view)
    else:
      view = CV2(f"{CROSS} Error", "Invalid option. Please use `enable` or `disable`.")
      await ctx.send(view=view)

  async def _sync_whitelist_role(self, guild, role):
    columns = ["ban","kick","botadd","chcr","chdl","chup","meneve","serverup","memup","prune","rlcr","rldl","rlup","mngweb"]
    async with self.db.execute('SELECT user_id FROM whitelisted_users WHERE guild_id = ?', (guild.id,)) as cur:
      existing = {row[0] for row in await cur.fetchall()}
    current = {m.id for m in role.members if not m.bot}
    for user_id in current:
      await self.db.execute('INSERT OR IGNORE INTO whitelisted_users (guild_id, user_id) VALUES (?, ?)', (guild.id, user_id))
      await self.db.execute(
        'UPDATE whitelisted_users SET ' + ', '.join(f'{col}=1' for col in columns) + ' WHERE guild_id=? AND user_id=?',
        (guild.id, user_id)
      )
    for user_id in existing - current:
      await self.db.execute('DELETE FROM whitelisted_users WHERE guild_id=? AND user_id=?', (guild.id, user_id))
    await self.db.commit()

  async def _get_log_channel(self, guild):
    await self._db_ready.wait()
    async with self.db.execute('SELECT log_channel_id FROM antinuke_settings WHERE guild_id=?', (guild.id,)) as cur:
      row = await cur.fetchone()
    return guild.get_channel(row[0]) if row and row[0] else None

  async def _log_security(self, guild, title, description, color=0xF1C40F):
    channel = await self._get_log_channel(guild)
    if not channel:
      return
    try:
      embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
      await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
      pass

  @commands.Cog.listener()
  async def on_member_update(self, before, after):
    if before.roles == after.roles:
      return
    await self._db_ready.wait()
    async with self.db.execute('SELECT whitelist_role_id FROM antinuke_settings WHERE guild_id=?', (after.guild.id,)) as cur:
      row = await cur.fetchone()
    if not row or not row[0]:
      return
    role = after.guild.get_role(row[0])
    if role:
      await self._sync_whitelist_role(after.guild, role)

  @commands.Cog.listener()
  async def on_member_remove(self, member):
    try:
      async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=3):
        if getattr(entry.target, 'id', None) == member.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 15:
          await self._log_security(member.guild, 'Member Kicked', f'Member: {member} ({member.id})\\nExecutor: {entry.user.mention} ({entry.user.id})\\nReason: {entry.reason or "No reason supplied"}', 0xE67E22)
          break
    except Exception:
      pass

  @commands.Cog.listener()
  async def on_member_ban(self, guild, user):
    try:
      async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=3):
        if getattr(entry.target, 'id', None) == user.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 15:
          await self._log_security(guild, 'Member Banned', f'Member: {user} ({user.id})\\nExecutor: {entry.user.mention} ({entry.user.id})\\nReason: {entry.reason or "No reason supplied"}', 0xE74C3C)
          break
    except Exception:
      pass

  @commands.Cog.listener()
  async def on_guild_channel_create(self, channel):
    await self._log_security(channel.guild, 'Channel Created', f'Channel: {channel.mention} ({channel.id})')

  @commands.Cog.listener()
  async def on_guild_channel_delete(self, channel):
    await self._log_security(channel.guild, 'Channel Deleted', f'Channel: #{channel.name} ({channel.id})')

  @commands.Cog.listener()
  async def on_guild_role_create(self, role):
    await self._log_security(role.guild, 'Role Created', f'Role: {role.mention} ({role.id})')

  @commands.Cog.listener()
  async def on_guild_role_delete(self, role):
    await self._log_security(role.guild, 'Role Deleted', f'Role: {role.name} ({role.id})')

  async def _show_punishment(self, interaction: discord.Interaction):
    view = CV2(
      "Punishment Types for Unwhitelisted Admins/Mods",
      "**Anti Ban:** Ban\n"
      "**Anti Kick:** Ban\n"
      "**Anti Bot:** Ban the bot Inviter\n"
      "**Anti Channel Create/Delete/Update:** Ban\n"
      "**Anti Everyone/Here:** Remove the message & 1 hour timeout\n"
      "**Anti Role Create/Delete/Update:** Ban\n"
      "**Anti Member Update:** Ban\n"
      "**Anti Guild Update:** Ban\n"
      "**Anti Integration:** Ban\n"
      "**Anti Webhook Create/Delete/Update:** Ban\n"
      "**Anti Prune:** Ban\n"
      "**Auto Recovery:** Automatically recover damaged channels, roles, and settings",
      "Note: In the case of member updates, action will be taken only if the role contains dangerous permissions such as Ban Members, Administrator, Manage Guild, Manage Channels, Manage Roles, Manage Webhooks, or Mention Everyone"
    )
    await interaction.response.send_message(view=view, ephemeral=True)
