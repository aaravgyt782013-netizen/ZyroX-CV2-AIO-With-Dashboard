import discord
from discord.ext import commands
from utils.Tools import *
from utils.cv2 import build_container
from utils.emoji import REWIND, PREVIOUS, NEXT, FORWARD, DELETE, HOME
from discord.ui import LayoutView, TextDisplay, Separator, ActionRow

class Dropdown(discord.ui.Select):
    def __init__(self, ctx, options, placeholder="Choose a Category for Help"):
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)
        self.invoker = ctx.author

    async def callback(self, interaction: discord.Interaction):
        if self.invoker == interaction.user:
            index = self.view.find_index_from_select(self.values[0])
            await self.view.set_page(index if index else 0, interaction)
        else:
            await interaction.response.send_message("You must run this command to interact with it.", ephemeral=True)

class View(LayoutView):
    def __init__(self, mapping: dict, ctx, homeembed, ui: int):
        super().__init__(timeout=None)
        self.mapping, self.ctx, self.index, self.current_page, self.ui = mapping, ctx, 0, 0, ui
        self.options, self.pages, self.total_pages = self.gen_pages(homeembed)
        if not self.pages:
            self.pages = [{'title': 'Help', 'description': 'No help categories are currently available.', 'fields': [], 'footer': None}]
            self.total_pages = 1
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        page = self.pages[self.index]
        page['footer'] = f"• Help page {self.index + 1}/{self.total_pages} | Requested by: {self.ctx.author.display_name}"
        items = []
        if page.get('title'): items.append(TextDisplay(f"**{page['title']}**"))
        if page.get('description'):
            if items: items.append(Separator(visible=True))
            items.append(TextDisplay(page['description']))
        for name, value in page.get('fields', []):
            items.append(Separator(visible=True))
            items.append(TextDisplay(f"**{name}**\n{value}"))
        first, last = self.index == 0, self.index >= len(self.pages) - 1
        homeB = discord.ui.Button(label="", emoji=REWIND, style=discord.ButtonStyle.secondary, disabled=first)
        backB = discord.ui.Button(label="", emoji=PREVIOUS, style=discord.ButtonStyle.secondary, disabled=first)
        quitB = discord.ui.Button(label="", emoji=DELETE, style=discord.ButtonStyle.danger)
        nextB = discord.ui.Button(label="", emoji=NEXT, style=discord.ButtonStyle.secondary, disabled=last)
        lastB = discord.ui.Button(label="", emoji=FORWARD, style=discord.ButtonStyle.secondary, disabled=last)
        homeB.callback, backB.callback, quitB.callback = self._home_cb, self._back_cb, self._quit_cb
        nextB.callback, lastB.callback = self._next_cb, self._last_cb
        items.append(ActionRow(homeB, backB, quitB, nextB, lastB))
        if self.options:
            if self.ui == 2:
                mid = max(1, len(self.options) // 2)
                if self.options[:mid]: items.append(ActionRow(Dropdown(self.ctx, self.options[:mid], "Main Commands")))
                if self.options[mid:]: items.append(ActionRow(Dropdown(self.ctx, self.options[mid:], "Extra Commands")))
            else:
                items.append(ActionRow(Dropdown(self.ctx, self.options)))
        if page.get('footer'):
            items.append(Separator(visible=True)); items.append(TextDisplay(f"*{page['footer']}*"))
        self.add_item(build_container(*items))

    async def _check(self, interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("You must run this command to interact with it.", ephemeral=True); return False
        return True
    async def _home_cb(self, interaction):
        if await self._check(interaction): await self.set_page(0, interaction)
    async def _back_cb(self, interaction):
        if await self._check(interaction): await self.set_page(max(0, self.index - 1), interaction)
    async def _quit_cb(self, interaction):
        if await self._check(interaction):
            await interaction.response.defer(); await interaction.delete_original_response()
    async def _next_cb(self, interaction):
        if await self._check(interaction): await self.set_page(min(len(self.pages)-1, self.index + 1), interaction)
    async def _last_cb(self, interaction):
        if await self._check(interaction): await self.set_page(len(self.pages)-1, interaction)

    def find_index_from_select(self, value):
        i = 0
        for cog in self.get_cogs():
            if cog.__class__.__name__ == "Roleplay" or "help_custom" not in dir(cog): continue
            _, label, _ = cog.help_custom()
            if label == value or value.startswith(label + " "): return i + 1
            i += 1
        return 0

    def get_cogs(self):
        return sorted(list(self.mapping.keys()), key=lambda cog: 0 if cog.__class__.__name__ == "Embed" else 1)

    def gen_pages(self, homeembed):
        options, pages, used_labels = [], [], {"Home"}
        options.append(discord.SelectOption(label="Home", emoji=HOME, description="Main help page"))
        if hasattr(homeembed, '_title'):
            fields = []
            for field in getattr(homeembed, '_fields', []):
                if isinstance(field, dict): fields.append((field.get('name', ''), field.get('value', '')))
                else: fields.append((getattr(field, 'name', ''), getattr(field, 'value', '')))
            pages.append({'title': homeembed._title or '', 'description': homeembed._description or '', 'fields': fields, 'footer': None})
        else:
            fields = [(f.name, f.value) for f in getattr(homeembed, 'fields', [])]
            pages.append({'title': getattr(homeembed, 'title', '') or '', 'description': getattr(homeembed, 'description', '') or '', 'fields': fields, 'footer': None})
        for cog in self.get_cogs():
            if cog.__class__.__name__ == "Roleplay" or "help_custom" not in dir(cog): continue
            emoji, label, description = cog.help_custom(); original_label = label; counter = 1
            while label in used_labels: label = f"{original_label} {counter}"; counter += 1
            used_labels.add(label); options.append(discord.SelectOption(label=label, emoji=emoji, description=(description or "Commands")[:100]))
            commands_for_help = []
            seen = set()

            def add_commands(source):
                if source is None:
                    return
                for command in source.get_commands():
                    if command.name not in seen:
                        commands_for_help.append(command)
                        seen.add(command.name)
                    if isinstance(command, commands.GroupMixin):
                        for child in command.commands:
                            key = child.qualified_name
                            if key not in seen:
                                commands_for_help.append(child)
                                seen.add(key)

            # Category cogs contain the help labels, while the real command
            # cogs contain the actual commands. Merge both so help pages never
            # show an empty category.
            add_commands(cog)
            label_key = original_label.lower()
            source_names = []
            if "music" in label_key:
                source_names = ["Music", "Music247"]
            elif "embed" in label_key:
                source_names = ["Embed"]
            elif "voice" in label_key:
                source_names = ["Voice", "TempVoice"]
            elif "ticket" in label_key:
                source_names = ["TicketCog"]
            for source_name in source_names:
                add_commands(self.ctx.bot.get_cog(source_name))
            fields = []
            for command in commands_for_help:
                params = ''.join(f" <{p}>" for p in command.clean_params if p not in ["self", "ctx"])
                help_text = command.help or command.description or "No description available"
                if len(help_text) > 900: help_text = help_text[:897] + "..."
                fields.append((f"{command.qualified_name}{params}", f"{help_text}\n•"))
            pages.append({'title': f"{emoji} {original_label}", 'description': '', 'fields': fields, 'footer': None})
        return options, pages, len(pages)

    async def set_page(self, page, interaction):
        self.index = max(0, min(page, len(self.pages)-1)); self.current_page = self.index
        self._rebuild(); await interaction.response.edit_message(view=self)
