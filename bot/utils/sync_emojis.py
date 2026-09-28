# ╔══════════════════════════════════════════════════════════════════╗
# ║                         LIGHTCORE                                ║
# ╚══════════════════════════════════════════════════════════════════╝

"""Reliable application-emoji synchronizer for LightCore.

The source of truth is utils/emoji.py. Discord application emojis are
synchronized at startup and missing/stale IDs are repaired automatically.

Note: Discord does not provide global/application stickers. Stickers are
guild assets and must be created in each guild separately.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import sys

import aiohttp
from colorama import Fore, Style, init

init(autoreset=True)

EMOJI_PY_PATH = os.path.join(os.path.dirname(__file__), "emoji.py")
API_BASE = "https://discord.com/api/v10"


def _log(level: str, color: str, symbol: str, msg: str) -> None:
    print(f"{color}{symbol} {level}:{Style.RESET_ALL} {msg}")


def info(msg): _log("EmojiSync", Fore.CYAN, "◈", msg)
def success(msg): _log("EmojiSync", Fore.GREEN, "✔", msg)
def warning(msg): _log("EmojiSync", Fore.YELLOW, "↻", msg)
def error(msg): _log("EmojiSync", Fore.RED, "✖", msg)
def system(msg): _log("EmojiSync", Fore.MAGENTA, "★", msg)


def _restart() -> None:
    system("Restarting bot to load updated emoji IDs...")
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable] + sys.argv)


async def _request_json(session, method, url, *, retries=4, **kwargs):
    """Request JSON while respecting Discord 429 responses."""
    for attempt in range(retries):
        try:
            async with session.request(method, url, **kwargs) as response:
                if response.status == 429:
                    data = await response.json(content_type=None)
                    retry_after = float(data.get("retry_after", 2))
                    warning(f"Discord rate limit: waiting {retry_after:.2f}s")
                    await asyncio.sleep(retry_after + 0.25)
                    continue

                if response.status >= 500 and attempt < retries - 1:
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue

                body = await response.text()
                try:
                    payload = await response.json(content_type=None)
                except Exception:
                    payload = body
                return response.status, payload
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if attempt == retries - 1:
                error(f"Discord request failed: {type(exc).__name__}: {exc}")
                return 0, None
            await asyncio.sleep(1.5 * (attempt + 1))

    return 0, None


async def _fetch_emoji_image(session, emoji_id: str, animated: bool):
    """Download the original emoji from Discord CDN."""
    extensions = ("gif", "png") if animated else ("png", "webp")

    for ext in extensions:
        url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}"
        try:
            async with session.get(url, allow_redirects=True) as response:
                if response.status == 200:
                    data = await response.read()
                    if data:
                        return data, ("image/gif" if ext == "gif" else "image/png")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            continue

    return None, None


async def _fetch_all_application_emojis(session, app_id: str):
    """Fetch the complete application-emoji collection, not just one page."""
    result = []
    after = None

    while True:
        params = {"limit": 200}
        if after:
            params["after"] = after

        status, data = await _request_json(
            session,
            "GET",
            f"{API_BASE}/applications/{app_id}/emojis",
            params=params,
        )
        if status != 200:
            error(f"Failed to fetch application emojis [HTTP {status}]")
            return result

        items = data.get("items", []) if isinstance(data, dict) else []
        result.extend(items)

        if len(items) < 200:
            break

        after = str(items[-1]["id"])

    return result


async def run_sync(token: str) -> None:
    """Synchronize every custom emoji referenced by utils/emoji.py."""
    enabled = os.getenv("EMOJI_SYNC", "true").strip().lower()
    if enabled != "true":
        info(f"Disabled via EMOJI_SYNC={enabled!r} — skipping.")
        return

    if not token:
        warning("No token provided — skipping EmojiSync.")
        return

    try:
        with open(EMOJI_PY_PATH, "r", encoding="utf-8") as file:
            content = file.read()
    except Exception as exc:
        error(f"Could not read emoji.py ({exc})")
        return

    # Discord custom emoji names are alphanumeric/underscore. Capture both
    # static <:name:id> and animated <a:name:id> definitions.
    matches = sorted(set(re.findall(r"<(a?):([A-Za-z0-9_]+):(\d+)>", content)))
    if not matches:
        info("No custom emojis found in emoji.py — nothing to sync.")
        return

    system(f"Starting Application Emoji Sync — {len(matches)} unique emojis found")

    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
        "User-Agent": "LightCore-EmojiSync/1.0",
    }

    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
        status, bot_data = await _request_json(
            session, "GET", f"{API_BASE}/users/@me"
        )
        if status != 200 or not isinstance(bot_data, dict):
            error(f"Failed to fetch bot info [HTTP {status}]")
            return

        app_id = bot_data.get("id")
        if not app_id:
            error("Discord did not return an application ID.")
            return

        app_emojis = await _fetch_all_application_emojis(session, app_id)
        info(
            f"Found {Fore.YELLOW}{len(matches)}{Style.RESET_ALL} source emojis | "
            f"Application currently has {Fore.GREEN}{len(app_emojis)}{Style.RESET_ALL}"
        )

        updated = False
        skipped = uploaded = fixed = failed = 0

        by_id = {str(item.get("id")): item for item in app_emojis}
        by_name = {item.get("name"): item for item in app_emojis if item.get("name")}

        for animated_str, name, old_id in matches:
            animated = animated_str == "a"
            existing = by_id.get(old_id) or by_name.get(name)

            if existing:
                new_id = str(existing["id"])
                new_name = existing.get("name") or name

                if old_id != new_id or name != new_name:
                    old_token = f"<{animated_str}:{name}:{old_id}>"
                    new_token = f"<{animated_str}:{new_name}:{new_id}>"
                    content = content.replace(old_token, new_token)
                    updated = True
                    fixed += 1
                    warning(f"Repaired {name} -> {new_name}:{new_id}")
                else:
                    skipped += 1
                continue

            info(f"Uploading missing emoji: {name}")
            image_data, mime = await _fetch_emoji_image(session, old_id, animated)
            if not image_data:
                error(f"Could not download source for {name} [ID: {old_id}]")
                failed += 1
                continue

            image_uri = (
                f"data:{mime};base64,"
                f"{base64.b64encode(image_data).decode('ascii')}"
            )

            status, payload = await _request_json(
                session,
                "POST",
                f"{API_BASE}/applications/{app_id}/emojis",
                json={"name": name, "image": image_uri},
            )

            if status in (200, 201) and isinstance(payload, dict) and payload.get("id"):
                new_id = str(payload["id"])
                new_name = payload.get("name") or name
                by_id[new_id] = payload
                by_name[new_name] = payload
                app_emojis.append(payload)

                old_token = f"<{animated_str}:{name}:{old_id}>"
                new_token = f"<{animated_str}:{new_name}:{new_id}>"
                content = content.replace(old_token, new_token)
                updated = True
                uploaded += 1
                success(f"Uploaded {name} -> {new_id}")
            else:
                error(f"Discord rejected {name} [HTTP {status}]: {payload}")
                failed += 1

            # Leave room between writes even when Discord is not rate limiting.
            await asyncio.sleep(0.35)

    if updated:
        try:
            with open(EMOJI_PY_PATH, "w", encoding="utf-8") as file:
                file.write(content)
            success("emoji.py patched with the current application emoji IDs.")
        except Exception as exc:
            error(f"Could not write patched emoji.py ({exc})")
            updated = False

    parts = []
    if skipped:
        parts.append(f"{skipped} already matching")
    if fixed:
        parts.append(f"{fixed} repaired")
    if uploaded:
        parts.append(f"{uploaded} uploaded")
    if failed:
        parts.append(f"{failed} failed")

    system("Sync complete: " + " | ".join(parts or ["nothing to do"]))

    if updated:
        _restart()
