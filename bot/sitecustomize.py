"""Python startup hook for LightCore compatibility patches."""

# Python imports sitecustomize automatically when this directory is on
# sys.path. Importing the patch here ensures it is installed before the
# cogs package creates the Music cog instance.
try:
    from cogs.commands.music import Music
    from cogs.commands.youtube_playback_fix import install
    install(Music)
except Exception:
    # Never prevent the bot from starting because of an optional patch.
    pass
