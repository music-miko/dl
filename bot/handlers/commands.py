

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ..core.client import app
from ..utils.helper import user_lang
from ..utils.search_flow import spotify_command, yt_command
from . import commands_registry as registry


async def _lang(message: Message) -> str:
    return await user_lang(message, touch=message.chat.type == ChatType.PRIVATE)


@registry.on(MessageHandler, filters.command("yt") & (filters.private | filters.group))
async def yt_cmd(client, message: Message):
    await yt_command(client, message, await _lang(message))


@registry.on(MessageHandler, filters.command("spotify") & (filters.private | filters.group))
async def spotify_cmd(client, message: Message):
    await spotify_command(client, message, await _lang(message))


registry.attach(app)
