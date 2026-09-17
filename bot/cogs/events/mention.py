from utils import getConfig
from utils.config import BotName, serverLink
import discord
from utils.emoji import ARROWRED, CODEBASE, HEART3, INDEX, ZYROXLINKS
from discord.ui import LayoutView, TextDisplay, Separator, Container, ActionRow, Select
from discord.ext import commands
from utils.Tools import get_ignore_data
import aiosqlite
from . import __name__ as _event_package

class MentionSelectView(LayoutView):
    def __init__(self, message, bot, prefix):
        super().__init__(timeout=300)
        self.message = message
        self.bot = bot
        self.prefix = prefix
        self.select = Select(placeholder=f"Start With {BotName}", options=[
            discord.SelectOption(label="Home", emoji=INDEX, description="Go to the main menu", value="home"),
            discord.SelectOption(label="Developer", emoji=CODEBASE, description="See the developer and owner commands", value="developer"),
            discord.SelectOption(label="Links", emoji=ZYROXLINKS, description="Useful bot links", value="links"),
        ])
        self.select.callback = self.on_select
        self.add_item(self._container(f"**{message.guild.name}**", f"> {HEART3} **Hey {message.author.mention}**\n> {ARROWRED} **Prefix For This Server: `{prefix}`**\n\n___Type `{prefix}help` for more information.___"))
    def _owner_commands(self):
        found=[]; seen=set()
        for command in self.bot.walk_commands():
            if command.name in seen: continue
            for check in getattr(command,"checks",[]):
                code=getattr(check,"__code__",None); names=set(getattr(code,"co_names",())) if code else set(); qualname=getattr(check,"__qualname__","")
                if "is_owner" in names or "is_owner" in qualname: found.append(command.qualified_name); seen.add(command.name); break
        if "servers" not in seen and self.bot.get_command("servers") is not None: found.append("servers")
        return sorted(set(found))
    def _developer_content(self):
        cmds="\n".join(f"• `{self.prefix}{n}`" for n in self._owner_commands()) or "• No owner-only commands detected."
        return "## Developer\n**Developer:** `@aaravg7820133.exe`\n\n### Owner Only Commands\nThese commands use the bot's configured owner ID(s):\n\n"+cmds
    def _container(self,title,content): return Container(TextDisplay(title),Separator(visible=True),TextDisplay(content),ActionRow(self.select))
    async def on_select(self,interaction):
        if interaction.user.id != self.message.author.id: return await interaction.response.send_message("This menu is not for you!",ephemeral=True)
        selected=interaction.data.get("values",["home"])[0]
        if selected=="home": content=f"> {HEART3} **Hey {interaction.user.mention}**\n> {ARROWRED} **Prefix For This Server: `{self.prefix}`**\n\n___Type `{self.prefix}help` for more information.___"
        elif selected=="developer": content=self._developer_content()
        else: content=f"**[Invite {BotName}](https://discord.com/oauth2/authorize?client_id=1516313619476779120)**\n**[Join Support Server]({serverLink})**"
        self.clear_items(); self.add_item(self._container(f"**{self.message.guild.name}**",content)); await interaction.response.edit_message(view=self)

class Mention(commands.Cog):
    def __init__(self, bot):
        self.bot=bot; self.color=0xFF0000; self.bot_name=BotName
        # Register the TempVoice cog from an already-loaded event cog so it is active even on deployments where the main cog list omits it.
        try:
            from ..commands.tempvoice import TempVoice
            bot.loop.create_task(bot.add_cog(TempVoice(bot)))
        except Exception as exc:
            print(f"TempVoice registration error: {exc}")
    async def is_blacklisted(self,message):
        async with aiosqlite.connect("db/block.db") as db:
            cursor=await db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?",(message.guild.id,))
            if await cursor.fetchone(): return True
            cursor=await db.execute("SELECT 1 FROM user_blacklist WHERE user_id = ?",(message.author.id,))
            if await cursor.fetchone(): return True
        return False
    @commands.Cog.listener()
    async def on_message(self,message):
        if message.author.bot or not message.guild:return
        if await self.is_blacklisted(message):return
        ignore_data=await get_ignore_data(message.guild.id)
        if str(message.author.id) in ignore_data["user"] or str(message.channel.id) in ignore_data["channel"]:return
        if self.bot.user in message.mentions and len(message.content.strip().split())==1:
            data=await getConfig(message.guild.id); prefix=data["prefix"]
            await message.channel.send(view=MentionSelectView(message,self.bot,prefix))

def setup(bot):
    bot.add_cog(Mention(bot))
