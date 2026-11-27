# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import html

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ..core.client import app
from ..core.config import config
from ..locale import text as t
from ..utils.buttons import build_clone_keyboard, keyboards
from ..utils.helper import user_lang
from . import start_registry as registry


@registry.on(MessageHandler, filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    lang = await user_lang(message, touch=True)
    user = message.from_user
    is_main = client.me.id == config.bot_id

    body = t(
        "start_text", lang,
        user=html.escape((user.first_name if user else "") or "there"),
        bot_name=html.escape(client.me.first_name or ""),
        bot_username=client.me.username or "",
        updates=keyboards.updates_channel_username,
    )
    await message.reply_text(
        body,
        reply_markup=keyboards.start_keyboard(client.me.username or "", lang, is_main=is_main),
        parse_mode=ParseMode.HTML,
    )

    if is_main and user:
        await message.reply_text(t("clone_prompt_text", lang), reply_markup=build_clone_keyboard(user, lang))


@registry.on(MessageHandler, filters.command("privacy") & filters.private)
async def privacy_cmd(client, message: Message):
    lang = await user_lang(message)
    await message.reply_text(t("privacy_text", lang), reply_markup=keyboards.updates_channel_markup(lang))


registry.attach(app)
