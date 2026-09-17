import re
from typing import Optional

import discord
from discord.ext import commands

from utils.emoji import CROSS, TICK, MESSAGE, ZWARNING

COLOR_DEFAULT = 0xFF0000


class _BaseEmbedModal(discord.ui.Modal):
    def __init__(self, builder, *, title: str):
        super().__init__(title=title, timeout=300)
        self.builder = builder

    async def _finish(self, interaction: discord.Interaction):
        await self.builder.refresh(interaction)


class BasicModal(_BaseEmbedModal):
    title_input = discord.ui.TextInput(label="Title", placeholder="Your embed title", max_length=256, required=False)
    description_input = discord.ui.TextInput(label="Description", placeholder="Your embed description...", style=discord.TextStyle.paragraph, max_length=4096, required=False)
    url_input = discord.ui.TextInput(label="Title URL", placeholder="https://example.com", max_length=2048, required=False)

    def __init__(self, builder):
        super().__init__(builder, title="Edit Embed • Basic")
        self.title_input.default = builder.data["title"] or ""
        self.description_input.default = builder.data["description"] or ""
        self.url_input.default = builder.data["url"] or ""

    async def on_submit(self, interaction: discord.Interaction):
        self.builder.data["title"] = str(self.title_input.value).strip()
        self.builder.data["description"] = str(self.description_input.value)
        self.builder.data["url"] = str(self.url_input.value).strip()
        await self._finish(interaction)


class StyleModal(_BaseEmbedModal):
    color_input = discord.ui.TextInput(label="Color (HEX)", placeholder="#FF0000", max_length=7, required=False)
    timestamp_input = discord.ui.TextInput(label="Timestamp", placeholder="yes / no", max_length=3, required=False)

    def __init__(self, builder):
        super().__init__(builder, title="Edit Embed • Style")
        self.color_input.default = f"#{builder.data['color']:06X}"
        self.timestamp_input.default = "yes" if builder.data["timestamp"] else "no"

    async def on_submit(self, interaction: discord.Interaction):
        raw = str(self.color_input.value).strip().lstrip("#")
        if raw:
            if not re.fullmatch(r"[0-9a-fA-F]{6}", raw):
                return await interaction.response.send_message(f"{CROSS} Invalid HEX color. Example: `#5865F2`", ephemeral=True)
            self.builder.data["color"] = int(raw, 16)
        ts = str(self.timestamp_input.value).strip().lower()
        if ts:
            if ts in {"yes", "y", "true", "on", "1"}:
                self.builder.data["timestamp"] = True
            elif ts in {"no", "n", "false", "off", "0"}:
                self.builder.data["timestamp"] = False
            else:
                return await interaction.response.send_message(f"{CROSS} Timestamp must be `yes` or `no`.", ephemeral=True)
        await self._finish(interaction)


class AuthorModal(_BaseEmbedModal):
    name_input = discord.ui.TextInput(label="Author name", max_length=256, required=False)
    icon_input = discord.ui.TextInput(label="Author icon URL", max_length=2048, required=False)
    url_input = discord.ui.TextInput(label="Author URL", max_length=2048, required=False)

    def __init__(self, builder):
        super().__init__(builder, title="Edit Embed • Author")
        self.name_input.default = builder.data["author_name"] or ""
        self.icon_input.default = builder.data["author_icon"] or ""
        self.url_input.default = builder.data["author_url"] or ""

    async def on_submit(self, interaction: discord.Interaction):
        self.builder.data["author_name"] = str(self.name_input.value).strip()
        self.builder.data["author_icon"] = str(self.icon_input.value).strip()
        self.builder.data["author_url"] = str(self.url_input.value).strip()
        await self._finish(interaction)


class FooterModal(_BaseEmbedModal):
    text_input = discord.ui.TextInput(label="Footer text", max_length=2048, required=False)
    icon_input = discord.ui.TextInput(label="Footer icon URL", max_length=2048, required=False)

    def __init__(self, builder):
        super().__init__(builder, title="Edit Embed • Footer")
        self.text_input.default = builder.data["footer_text"] or ""
        self.icon_input.default = builder.data["footer_icon"] or ""

    async def on_submit(self, interaction: discord.Interaction):
        self.builder.data["footer_text"] = str(self.text_input.value)
        self.builder.data["footer_icon"] = str(self.icon_input.value).strip()
        await self._finish(interaction)


class ImagesModal(_BaseEmbedModal):
    thumbnail_input = discord.ui.TextInput(label="Thumbnail URL", max_length=2048, required=False)
    image_input = discord.ui.TextInput(label="Main image URL", max_length=2048, required=False)

    def __init__(self, builder):
        super().__init__(builder, title="Edit Embed • Images")
        self.thumbnail_input.default = builder.data["thumbnail"] or ""
        self.image_input.default = builder.data["image"] or ""

    async def on_submit(self, interaction: discord.Interaction):
        for field_name, value in (("thumbnail", self.thumbnail_input.value), ("image", self.image_input.value)):
            value = str(value).strip()
            if value and not value.startswith(("http://", "https://")):
                return await interaction.response.send_message(f"{CROSS} Image URLs must start with `http://` or `https://`.", ephemeral=True)
            self.builder.data[field_name] = value
        await self._finish(interaction)


class FieldModal(_BaseEmbedModal):
    name_input = discord.ui.TextInput(label="Field name", max_length=256, required=True)
    value_input = discord.ui.TextInput(label="Field value", style=discord.TextStyle.paragraph, max_length=1024, required=True)
    inline_input = discord.ui.TextInput(label="Inline? yes/no", max_length=3, required=False, default="no")

    def __init__(self, builder):
        super().__init__(builder, title="Add Embed Field")

    async def on_submit(self, interaction: discord.Interaction):
        if len(self.builder.data["fields"]) >= 25:
            return await interaction.response.send_message(f"{ZWARNING} Discord allows up to 25 fields.", ephemeral=True)
        inline = str(self.inline_input.value).strip().lower() in {"yes", "y", "true", "1", "on"}
        self.builder.data["fields"].append({"name": str(self.name_input.value), "value": str(self.value_input.value), "inline": inline})
        await self._finish(interaction)


class EmbedBuilder(discord.ui.View):
    """Interactive Mimu-style embed builder using Discord buttons and modals."""

    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=600)
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        self.destination: discord.TextChannel = ctx.channel
        self.data = {
            "title": "", "description": "", "url": "", "color": COLOR_DEFAULT,
            "timestamp": False, "author_name": "", "author_icon": "", "author_url": "",
            "footer_text": "", "footer_icon": "", "thumbnail": "", "image": "", "fields": [],
        }
        self._build_components()

    def _build_embed(self) -> discord.Embed:
        d = self.data
        embed = discord.Embed(title=d["title"] or None, description=d["description"] or None, url=d["url"] or None, color=d["color"])
        if d["timestamp"]:
            embed.timestamp = discord.utils.utcnow()
        if d["author_name"]:
            kwargs = {"name": d["author_name"]}
            if d["author_icon"]:
                kwargs["icon_url"] = d["author_icon"]
            if d["author_url"]:
                kwargs["url"] = d["author_url"]
            embed.set_author(**kwargs)
        if d["footer_text"] or d["footer_icon"]:
            kwargs = {"text": d["footer_text"] or ""}
            if d["footer_icon"]:
                kwargs["icon_url"] = d["footer_icon"]
            embed.set_footer(**kwargs)
        if d["thumbnail"]:
            embed.set_thumbnail(url=d["thumbnail"])
        if d["image"]:
            embed.set_image(url=d["image"])
        for field in d["fields"]:
            embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])
        return embed

    def _build_components(self):
        self.clear_items()
        edit_select = discord.ui.Select(
            placeholder="Choose what you want to edit", min_values=1, max_values=1, row=0,
            options=[
                discord.SelectOption(label="Basic", value="basic", emoji="📝", description="Title, description and title URL"),
                discord.SelectOption(label="Style", value="style", emoji="🎨", description="Color and timestamp"),
                discord.SelectOption(label="Author", value="author", emoji="👤", description="Author name, icon and URL"),
                discord.SelectOption(label="Footer", value="footer", emoji="📌", description="Footer text and icon"),
                discord.SelectOption(label="Images", value="images", emoji="🖼️", description="Thumbnail and main image"),
            ],
        )
        edit_select.callback = self._edit_select
        self.add_item(edit_select)

        for label, emoji, callback in [
            ("Basic", "📝", self._basic), ("Style", "🎨", self._style), ("Author", "👤", self._author),
            ("Footer", "📌", self._footer), ("Images", "🖼️", self._images),
        ]:
            button = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, row=1)
            button.callback = callback
            self.add_item(button)

        add_field = discord.ui.Button(label="Add Field", emoji="➕", style=discord.ButtonStyle.primary, row=2)
        remove_field = discord.ui.Button(label="Remove Field", emoji="➖", style=discord.ButtonStyle.secondary, row=2)
        reset = discord.ui.Button(label="Reset", emoji="♻️", style=discord.ButtonStyle.danger, row=2)
        add_field.callback = self._add_field
        remove_field.callback = self._remove_field
        reset.callback = self._reset
        self.add_item(add_field)
        self.add_item(remove_field)
        self.add_item(reset)

        channel_select = discord.ui.ChannelSelect(
            placeholder="Choose destination channel (default: current channel)",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news], min_values=1, max_values=1, row=3,
        )
        channel_select.callback = self._channel_select
        self.add_item(channel_select)

        send = discord.ui.Button(label="Send Embed", emoji=TICK, style=discord.ButtonStyle.success, row=4)
        cancel = discord.ui.Button(label="Cancel", emoji=CROSS, style=discord.ButtonStyle.danger, row=4)
        send.callback = self._send
        cancel.callback = self._cancel
        self.add_item(send)
        self.add_item(cancel)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This embed builder belongs to the person who opened it.", ephemeral=True)
            return False
        return True

    async def _edit_select(self, interaction: discord.Interaction):
        selected = interaction.data.get("values", ["basic"])[0]
        modal_class = {"basic": BasicModal, "style": StyleModal, "author": AuthorModal, "footer": FooterModal, "images": ImagesModal}[selected]
        await interaction.response.send_modal(modal_class(self))

    async def _basic(self, interaction): await interaction.response.send_modal(BasicModal(self))
    async def _style(self, interaction): await interaction.response.send_modal(StyleModal(self))
    async def _author(self, interaction): await interaction.response.send_modal(AuthorModal(self))
    async def _footer(self, interaction): await interaction.response.send_modal(FooterModal(self))
    async def _images(self, interaction): await interaction.response.send_modal(ImagesModal(self))
    async def _add_field(self, interaction): await interaction.response.send_modal(FieldModal(self))

    async def _remove_field(self, interaction):
        if self.data["fields"]:
            self.data["fields"].pop()
            await self.refresh(interaction)
        else:
            await interaction.response.send_message("There are no fields to remove.", ephemeral=True)

    async def _reset(self, interaction):
        self.data.update({
            "title": "", "description": "", "url": "", "color": COLOR_DEFAULT, "timestamp": False,
            "author_name": "", "author_icon": "", "author_url": "", "footer_text": "", "footer_icon": "",
            "thumbnail": "", "image": "", "fields": [],
        })
        await self.refresh(interaction)

    async def _channel_select(self, interaction):
        selected = interaction.data.get("values", [])
        if selected:
            try:
                self.destination = self.ctx.guild.get_channel(int(selected[0])) or self.ctx.channel
            except (TypeError, ValueError):
                self.destination = self.ctx.channel
        await interaction.response.send_message(f"Destination set to {self.destination.mention}.", ephemeral=True)

    async def _send(self, interaction):
        try:
            await self.destination.send(embed=self._build_embed())
        except discord.Forbidden:
            return await interaction.response.send_message(f"{ZWARNING} I cannot send embeds in {self.destination.mention}.", ephemeral=True)
        except discord.HTTPException as exc:
            return await interaction.response.send_message(f"{CROSS} Discord rejected the embed: `{exc}`", ephemeral=True)
        await interaction.response.send_message(f"{TICK} Embed sent to {self.destination.mention}.", ephemeral=True)
        self.stop()

    async def _cancel(self, interaction):
        await interaction.response.edit_message(content="Embed builder cancelled.", embed=None, view=None)
        self.stop()

    async def refresh(self, interaction: discord.Interaction):
        self._build_components()
        await interaction.response.defer()
        if self.message:
            await self.message.edit(embed=self._build_embed(), view=self)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass


class Embed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def help_custom(self):
        return MESSAGE, "Embed Commands", "Interactive embed builder"

    @commands.hybrid_command(
        name="embed",
        aliases=["embeds", "embedbuilder"],
        help="Open the interactive embed builder.",
        usage="embed",
    )
    @commands.cooldown(1, 7, commands.BucketType.user)
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def _embed(self, ctx: commands.Context):
        builder = EmbedBuilder(ctx)
        builder.message = await ctx.send(embed=builder._build_embed(), view=builder)


async def setup(bot):
    await bot.add_cog(Embed(bot))
