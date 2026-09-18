import re
import json
import sqlite3
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.emoji import CROSS, TICK, MESSAGE, ZWARNING

COLOR_DEFAULT = 0xFF0000
EMBED_DB = "saved_embeds.db"