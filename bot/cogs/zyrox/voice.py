import discord
from utils.emoji import MUTE
from discord.ext import commands

class _voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def help_custom(self):
        return MUTE, "Voice Commands", "Voice moderation + TempVoice (setup, panel, reset)"

    @commands.group()
    async def __Voice__(self, ctx: commands.Context):
        """
        `voice` , `voice kick` , `voice kickall` , `voice mute` , `voice muteall` , `voice unmute` , `voice unmuteall` , `voice deafen` , `voice deafenall` , `voice undeafen` , `voice undeafenall` , `voice move` , `voice moveall` , `voice pull` , `voice pullall` , `voice lock` , `voice unlock` , `voice private` , `voice unprivate`

**__VC Autorole__**
`vcrole add` , `vcrole remove` , `vcrole config`

**__TempVoice__**
`tempvoice setup` , `tempvoice panel` , `tempvoice reset`
Join the generated **Join to Create** VC to automatically create a personal temporary VC. Use the persistent control panel for Lock, Unlock, Hide, Show, Rename, Limit, Claim and Delete.
        """
