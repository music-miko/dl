# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from .. import LOGGER
from ..utils.helper import HandlerRegistry

start_registry = HandlerRegistry("bot.handlers.start")
search_registry = HandlerRegistry("bot.handlers.search")
callback_registry = HandlerRegistry("bot.handlers.callback")
inline_registry = HandlerRegistry("bot.handlers.inline")
admin_registry = HandlerRegistry("bot.handlers.admin")
clones_registry = HandlerRegistry("bot.handlers.clones")
lang_registry = HandlerRegistry("bot.handlers.lang")
commands_registry = HandlerRegistry("bot.handlers.commands")

from . import admin, callback, clones, commands, inline, lang, search, start


def attach_shared_handlers(client) -> None:
    for module in (start, commands, search, callback, inline, lang):
        module.registry.attach(client)


LOGGER.info(
    "Handlers loaded -> %s",
    ", ".join(m.registry.name.rsplit(".", 1)[-1] for m in (start, commands, search, callback, inline, admin, clones, lang)),
)
