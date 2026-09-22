import asyncio
import os
from datetime import datetime, timezone

import aiosqlite
import discord
from discord.ext import commands, tasks
from mcstatus import JavaServer, BedrockServer

from utils.config import OWNER_IDS

DB_PATH = "db/mcserver.db"
DEFAULT_IP = os.getenv("MC_SERVER_IP", "").strip()
try:
    DEFAULT_PORT = int(os.getenv("MC_SERVER_PORT", "25565"))
except ValueError:
    DEFAULT_PORT = 25565


class MCServer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("db", exist_ok=True)
        self.bot.loop.create_task(self._init_db())
        self.live_status.start()

    def cog_unload(self):
        self.live_status.cancel()

    async def _init_db(self):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mcserver_config (
                    guild_id INTEGER PRIMARY KEY,
                    ip TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    channel_id INTEGER,
                    message_id INTEGER
                )
            """)
            await db.commit()

    def owner(self, user_id):
        return user_id in OWNER_IDS

    async def config(self, guild_id):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT ip, port, channel_id, message_id FROM mcserver_config WHERE guild_id=?",
                (guild_id,)
            )
            return await cur.fetchone()

    async def save(self, guild_id, ip, port, channel_id=None, message_id=None):
        old = await self.config(guild_id)
        channel_id = channel_id if channel_id is not None else (old[2] if old else None)
        message_id = message_id if message_id is not None else (old[3] if old else None)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO mcserver_config(guild_id,ip,port,channel_id,message_id)
                VALUES(?,?,?,?,?)
                ON CONFLICT(guild_id) DO UPDATE SET
                ip=excluded.ip, port=excluded.port,
                channel_id=excluded.channel_id, message_id=excluded.message_id
            """, (guild_id, ip, port, channel_id, message_id))
            await db.commit()

    async def check(self, ip, port):
        try:
            s = JavaServer(ip, port)
            st = await asyncio.wait_for(s.async_status(tries=1), timeout=6)
            desc = st.description
            if isinstance(desc, dict):
                motd = str(desc.get("text", "")) + "".join(
                    str(x.get("text", "")) for x in desc.get("extra", []) if isinstance(x, dict)
                )
            else:
                motd = str(desc)
            return {
                "online": True, "type": "Java", "version": str(st.version.name),
                "players": st.players.online, "max": st.players.max,
                "motd": motd.strip() or "Minecraft Server",
                "ping": round(float(st.latency), 1)
            }
        except Exception:
            pass

        try:
            bp = 19132 if port == 25565 else port
            s = BedrockServer(ip, bp)
            st = await asyncio.wait_for(s.async_status(tries=1), timeout=6)
            return {
                "online": True, "type": "Bedrock", "version": str(st.version.name),
                "players": st.players.online, "max": st.players.max,
                "motd": str(st.motd).strip() or "Minecraft Server",
                "ping": round(float(st.latency), 1)
            }
        except Exception:
            return {
                "online": False, "type": "Unknown", "version": "Unavailable",
                "players": 0, "max": 0, "motd": "Server is offline or unreachable",
                "ping": None
            }

    def embed(self, ip, port, data):
        online = data["online"]
        e = discord.Embed(
            title=("🟢" if online else "🔴") + " Minecraft Server Status",
            color=discord.Color.green() if online else discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        e.add_field(name="Server", value=f"{ip}:{port}", inline=False)
        e.add_field(name="Edition", value=data["type"], inline=True)
        e.add_field(name="Players", value=f"{data['players']}/{data['max']}", inline=True)
        e.add_field(name="Version", value=data["version"], inline=True)
        if data["ping"] is not None:
            e.add_field(name="Ping", value=f"{data['ping']} ms", inline=True)
        e.add_field(name="MOTD", value=data["motd"][:1024], inline=False)
        e.set_footer(text="LightCore • Live status • refreshes every 60 seconds")
        return e

    @commands.group(name="mcserver", invoke_without_command=True)
    async def mcserver(self, ctx):
        if not self.owner(ctx.author.id):
            return await ctx.send("❌ This command is owner-only.")
        await ctx.send(
            "**⛏️ MCServer**\n"
            ".mcserver setup <ip> [port] — configure live status\n"
            ".mcserver status — check status now\n"
            ".mcserver ip — show configured IP\n"
            ".mcserver off — remove live panel"
        )

    @mcserver.command(name="setup")
    async def setup_server(self, ctx, ip=None, port=None):
        if not self.owner(ctx.author.id):
            return await ctx.send("❌ This command is owner-only.")
        ip = (ip or DEFAULT_IP).strip()
        if not ip:
            return await ctx.send("❌ Use .mcserver setup <ip> [port]")
        port = port or (DEFAULT_PORT if DEFAULT_IP else 25565)
        if not 1 <= port <= 65535:
            return await ctx.send("❌ Invalid port.")
        await ctx.typing()
        data = await self.check(ip, port)
        msg = await ctx.channel.send(embed=self.embed(ip, port, data))
        await self.save(ctx.guild.id, ip, port, ctx.channel.id, msg.id)
        await ctx.send(f"✅ Live MCServer status configured for {ip}:{port}.", delete_after=8)

    @mcserver.command(name="status")
    async def status_server(self, ctx):
        if not self.owner(ctx.author.id):
            return await ctx.send("❌ This command is owner-only.")
        row = await self.config(ctx.guild.id)
        if row:
            ip, port = row[0], row[1]
        elif DEFAULT_IP:
            ip, port = DEFAULT_IP, DEFAULT_PORT
        else:
            return await ctx.send("❌ No server configured. Use .mcserver setup <ip> [port]")
        data = await self.check(ip, port)
        await ctx.send(embed=self.embed(ip, port, data))

    @mcserver.command(name="ip")
    async def show_ip(self, ctx):
        if not self.owner(ctx.author.id):
            return await ctx.send("❌ This command is owner-only.")
        row = await self.config(ctx.guild.id)
        if row:
            return await ctx.send(f"🌐 {row[0]}:{row[1]}")
        if DEFAULT_IP:
            return await ctx.send(f"🌐 {DEFAULT_IP}:{DEFAULT_PORT}")
        await ctx.send("❌ No server IP configured.")

    @mcserver.command(name="off")
    async def off(self, ctx):
        if not self.owner(ctx.author.id):
            return await ctx.send("❌ This command is owner-only.")
        row = await self.config(ctx.guild.id)
        if not row:
            return await ctx.send("ℹ️ No MCServer panel configured.")
        try:
            channel = self.bot.get_channel(row[2]) or await self.bot.fetch_channel(row[2])
            message = await channel.fetch_message(row[3])
            await message.delete()
        except Exception:
            pass
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM mcserver_config WHERE guild_id=?", (ctx.guild.id,))
            await db.commit()
        await ctx.send("✅ MCServer live panel removed.")

    @tasks.loop(seconds=60)
    async def live_status(self):
        await self.bot.wait_until_ready()
        async with aiosqlite.connect(DB_PATH) as db:
            rows = await (await db.execute(
                "SELECT guild_id,ip,port,channel_id,message_id FROM mcserver_config"
            )).fetchall()
        for guild_id, ip, port, channel_id, message_id in rows:
            try:
                channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
                message = await channel.fetch_message(message_id)
                data = await self.check(ip, port)
                await message.edit(embed=self.embed(ip, port, data))
            except Exception as exc:
                print(f"[MCServer] refresh failed for {guild_id}: {exc}")

    @live_status.before_loop
    async def before_live_status(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(MCServer(bot))
