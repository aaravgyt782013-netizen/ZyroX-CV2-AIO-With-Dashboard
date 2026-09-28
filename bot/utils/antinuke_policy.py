import json
from datetime import timedelta
import aiosqlite
import discord

DB_PATH = "db/anti.db"

DEFAULT_PUNISHMENTS = {
    "ban": "ban",
    "kick": "ban",
    "botadd": "ban",
    "channel_create": "ban",
    "channel_delete": "ban",
    "channel_update": "ban",
    "role_create": "ban",
    "role_delete": "ban",
    "role_update": "ban",
    "member_update": "ban",
    "guild_update": "ban",
    "webhook": "ban",
    "prune": "ban",
    "everyone": "timeout",
}

async def get_punishment(guild_id: int, event: str) -> str:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT punishments FROM antinuke_settings WHERE guild_id = ?",
                (guild_id,),
            )
            row = await cur.fetchone()
        if row and row[0]:
            data = json.loads(row[0])
            return str(data.get(event, DEFAULT_PUNISHMENTS.get(event, "ban"))).lower()
    except Exception:
        pass
    return DEFAULT_PUNISHMENTS.get(event, "ban")

async def apply_punishment(guild: discord.Guild, member: discord.Member, event: str, reason: str) -> bool:
    action = await get_punishment(guild.id, event)
    if action == "off":
        return False

    try:
        if action == "kick":
            await guild.kick(member, reason=reason)
        elif action == "timeout":
            await member.edit(
                timed_out_until=discord.utils.utcnow() + timedelta(hours=1),
                reason=reason,
            )
        else:
            await guild.ban(member, reason=reason)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False
    except Exception:
        return False
