# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ..core.client import app
from ..utils.classifier import classifier
from ..utils.helper import not_command_filter, user_lang
from ..utils.search_flow import safe_dispatch
from . import search_registry as registry


@registry.on(
    MessageHandler,
    (filters.private | filters.group) & filters.text & ~filters.via_bot & not_command_filter,
)
async def handle_text(client, message: Message):
    private = message.chat.type == ChatType.PRIVATE

    kind, value = classifier.classify(
        message.text,
        strict=not private,
        extra_urls=classifier.urls_from_entities(message.entities),
    )
    if kind == "ignore":
        return

    lang = await user_lang(message, touch=private)
    await safe_dispatch(client, message, kind, value, lang, passive=not private)


registry.attach(app)
