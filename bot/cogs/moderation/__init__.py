"""Moderation package bootstrap.

The announce command is attached to the existing Moderation cog so it stays
inside the Moderation help category instead of creating a duplicate category.
"""

from .announce import patch_moderation

patch_moderation()
