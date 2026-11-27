# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import contextlib
import os

from pyrogram import Client
from pyrogram.types import InputChatPhotoStatic

from .. import LOGGER
from .client import app
from .config import config
from ..utils.errors import describe_error, token_errors
from .mongo import mongo

class CloneManager:
    def __init__(self):
        self.active: dict[int, Client] = {}
        self.profile_photo_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "assets", "arcdlbot_logo.png",
        )
        self.bot_short_description = (
            "Download music & media from YouTube, Spotify, SoundCloud, Instagram, "
            "TikTok, and more — right in Telegram."
        )
        self.bot_description = (
            "Send a song name, or paste a link from YouTube, Spotify, SoundCloud, "
            "Instagram, Facebook, Threads, TikTok, Twitter/X, or Bluesky — I'll fetch "
            "it and send it right back to you.\n\n"
            "Works in groups and inline too.\n\n"
            "This bot is a clone of Arc Downloader, built on the open-source Arc "
            "Downloader framework: github.com/tusar404/ArcDLBot"
        )

    async def load_all(self) -> None:
        docs = await mongo.all_clones()
        for doc in docs:
            await self.start_clone(doc)
        if docs:
            LOGGER.info("Relaunched %d/%d cloned bot(s).", len(self.active), len(docs))

    async def start_clone(self, doc: dict) -> bool:
        bot_id, token = doc["_id"], doc["token"]
        owner_id, username = doc.get("owner_id"), doc.get("username")
        label = f"@{username}" if username else str(bot_id)

        try:
            await self.spinup(bot_id, token, owner_id=owner_id, username=username, persist=False)
        except token_errors as e:
            return await self._recover_token(doc, label, e)
        except Exception as e:
            LOGGER.error("Clone %s (bot_id=%s) not started: %s", label, bot_id, describe_error(e))
            await self._mark(bot_id, "error")
            return False

        await self._mark(bot_id, None)
        return True

    async def _recover_token(self, doc: dict, label: str, error: Exception) -> bool:
        bot_id, token = doc["_id"], doc["token"]

        if not doc.get("managed", True):
            LOGGER.error(
                "Clone %s (bot_id=%s) not started: Telegram rejected its token (%s) and it was not "
                "created through managed bots, so a new token can't be fetched.",
                label, bot_id, describe_error(error),
            )
            await self._mark(bot_id, "token_invalid")
            return False

        LOGGER.warning(
            "Clone %s (bot_id=%s): Telegram rejected the saved token (%s); fetching the current one...",
            label, bot_id, describe_error(error),
        )
        try:
            fresh = await app.get_managed_bot_token(bot_id)
        except Exception as e:
            LOGGER.error(
                "Clone %s (bot_id=%s) not started: token rejected (%s) and a new one couldn't be "
                "fetched via managed bots (%s).", label, bot_id, describe_error(error), describe_error(e),
            )
            await self._mark(bot_id, "token_invalid")
            return False

        if not fresh or fresh == token:
            LOGGER.error(
                "Clone %s (bot_id=%s) not started: token rejected (%s) and Telegram has no newer "
                "token for it (bot deleted?).", label, bot_id, describe_error(error),
            )
            await self._mark(bot_id, "token_invalid")
            return False

        try:
            await self.spinup(
                bot_id, fresh, owner_id=doc.get("owner_id"), username=doc.get("username"), persist=False,
            )
        except Exception as e:
            LOGGER.error(
                "Clone %s (bot_id=%s) not started: the refreshed token failed too (%s).",
                label, bot_id, describe_error(e),
            )
            await self._mark(bot_id, "token_invalid")
            return False

        await mongo.update_clone_token(bot_id, fresh)
        await self._mark(bot_id, None)
        LOGGER.info("Clone %s (bot_id=%s): token refreshed from Telegram and bot started.", label, bot_id)
        return True

    async def apply_token(self, bot_id: int, token: str, *, owner_id: int, username: str | None) -> bool:
        await self.stop(bot_id)
        label = f"@{username}" if username else str(bot_id)
        try:
            await self.spinup(bot_id, token, owner_id=owner_id, username=username, persist=True)
        except Exception as e:
            await mongo.update_clone_token(bot_id, token)
            await self._mark(bot_id, "error")
            LOGGER.error("Clone %s (bot_id=%s): new token saved but the bot didn't start: %s",
                         label, bot_id, describe_error(e))
            return False
        await self._mark(bot_id, None)
        LOGGER.info("Clone %s (bot_id=%s): token updated by Telegram, bot restarted.", label, bot_id)
        return True

    @staticmethod
    async def _mark(bot_id: int, state: str | None) -> None:
        with contextlib.suppress(Exception):
            await mongo.set_clone_status(bot_id, state)

    async def spinup(
        self, bot_id: int, token: str, *, owner_id: int | None = None,
        username: str | None = None, persist: bool = True,
    ) -> Client:
        if bot_id in self.active:
            return self.active[bot_id]

        client = Client(
            f"clone_{bot_id}",
            api_id=config.api_id,
            api_hash=config.api_hash,
            bot_token=token,
            in_memory=True,
        )

        from ..handlers import attach_shared_handlers
        attach_shared_handlers(client)

        await client.start()
        self.active[bot_id] = client

        from ..utils.helper import publish_commands
        await publish_commands(client)

        if persist:
            await mongo.save_clone(bot_id, owner_id, username, token)

        return client

    async def stop(self, bot_id: int) -> None:
        client = self.active.pop(bot_id, None)
        if client:
            with contextlib.suppress(Exception):
                await client.stop()

    async def delete(self, bot_id: int) -> None:
        await self.stop(bot_id)
        await mongo.delete_clone(bot_id)

    async def set_branding(self, client: Client) -> None:
        try:
            await client.set_profile_photo(photo=InputChatPhotoStatic(self.profile_photo_path))
        except Exception:
            LOGGER.exception("Failed to set profile photo for clone bot_id=%s", client.me.id)

        try:
            await client.set_bot_info_short_description(self.bot_short_description)
            await client.set_bot_info_description(self.bot_description)
        except Exception:
            LOGGER.exception("Failed to set bio/description for clone bot_id=%s", client.me.id)


clones = CloneManager()
