from utils import getConfig
from utils.config import BotName, serverLink
import discord
from utils.emoji import ARROWRED, CODEBASE, HEART3, INDEX, ZYROXLINKS
from discord.ui import LayoutView, TextDisplay, Separator, Container, ActionRow, Select
from discord.ext import commands
from utils.Tools import get_ignore_data
import aiosqlite


class MentionSelectView(LayoutView):
    def __init__(self, message, bot, prefix):
        super().__init__(timeout=300)
        self.message = message
        self.bot = bot
        self.prefix = prefix
        self.select = Select(placeholder=f"Start With {BotName}", options=[
            discord.SelectOption(label="Home", emoji=INDEX, description="Go to the main menu", value="home"),
            discord.SelectOption(label="Developer", emoji=CODEBASE, description="See the developer information", value="developer"),
            discord.SelectOption(label="Links", emoji=ZYROXLINKS, description="Useful bot links", value="links"),
        ])
        self.select.callback = self.on_select
        self._refresh()

    def _refresh(self, content=None):
        if content is None:
            content = (
                f"> {HEART3} **Hey {self.message.author.mention}**\n"
                f"> {ARROWRED} **Prefix For This Server: `{self.prefix}`**\n\n"
                f"___Type `{self.prefix}help` for more information.___"
            )
        self.clear_items()
        self.add_item(Container(
            TextDisplay(f"**{self.message.guild.name}**"),
            Separator(visible=True),
            TextDisplay(content),
            ActionRow(self.select)
        ))

    async def on_select(self, interaction):
        if interaction.user.id != self.message.author.id:
            return await interaction.response.send_message("This menu is not for you!", ephemeral=True)
        selected = interaction.data.get("values", ["home"])[0]
        if selected == "home":
            content = (
                f"> {HEART3} **Hey {interaction.user.mention}**\n"
                f"> {ARROWRED} **Prefix For This Server: `{self.prefix}`**\n\n"
                f"___Type `{self.prefix}help` for more information.___"
            )
        elif selected == "developer":
            # Keep the Developer section, but do not expose owner-only commands.
            content = (
                "## Developer\n"
                "**Developer:** `@aaravg7820133.exe`\n\n"
                "This bot is developed and maintained by the LightCore development team."
            )
        else:
            content = (
                f"**[Invite {BotName}]"
                f"(https://discord.com/oauth2/authorize?client_id=1516313619476779120&permissions=8&integration_type=0&scope=bot)**\n"
                f"**[Join Support Server]({serverLink})**"
            )
        self._refresh(content)
        await interaction.response.edit_message(view=self)


class Mention(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0xFF0000
        self.bot_name = BotName
        try:
            from ..commands.tempvoice import TempVoice
            if bot.get_cog("TempVoice") is None:
                bot.loop.create_task(bot.add_cog(TempVoice(bot)))
        except Exception as exc:
            print(f"TempVoice registration error: {exc}")

    async def is_blacklisted(self, message):
        async with aiosqlite.connect("db/block.db") as db:
            cursor = await db.execute("SELECT 1 FROM guild_blacklist WHERE guild_id = ?", (message.guild.id,))
            if await cursor.fetchone():
                return True
            cursor = await db.execute("SELECT 1 FROM user_blacklist WHERE user_id = ?", (message.author.id,))
            if await cursor.fetchone():
                return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if await self.is_blacklisted(message):
            return
        ignore_data = await get_ignore_data(message.guild.id)
        if str(message.author.id) in ignore_data["user"] or str(message.channel.id) in ignore_data["channel"]:
            return
        if self.bot.user in message.mentions and len(message.content.strip().split()) == 1:
            data = await getConfig(message.guild.id)
            prefix = data["prefix"]
            await message.channel.send(view=MentionSelectView(message, self.bot, prefix))


def setup(bot):
    bot.add_cog(Mention(bot))
