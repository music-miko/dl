# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import Message

from .. import LOGGER
from ..dl.actions import run_download
from ..dl.api_client import YTAPIError, yt_api
from ..dl.terabox_flow import terabox_flow
from ..locale import text as t
from .buttons import keyboards
from .classifier import classifier
from .helper import cache, short_duration, truncate


def artist_names(artists) -> str:
    names = []
    for a in artists or []:
        name = a.get("name") if isinstance(a, dict) else a
        if name:
            names.append(str(name))
    return ", ".join(names)


async def start_single_download(
    client, message: Message, entry: dict, lang: str, *, passive: bool = False
) -> None:
    token = cache.put_new(entry)
    status = await message.reply_text(t("starting_text", lang))
    await run_download(
        client, token, chat_id=message.chat.id, status=status, lang=lang, silent_fail=passive,
    )


async def show_paginated_list(
    message: Message, header: str, tracks: list[dict], entry_builder, lang: str
) -> None:
    entries = []
    for tr in tracks:
        built = entry_builder(tr)
        if not (built.get("url") or built.get("video_id")):
            continue
        token = cache.put_new(built)
        entries.append((token, {"title": built.get("title"), "duration": built.get("duration")}))

    if not entries:
        await message.reply_text(t("no_results_text", lang))
        return

    list_token = cache.put_new({"entries": entries})
    await message.reply_text(
        header,
        reply_markup=keyboards.paginated_results_keyboard(list_token, entries, page=0, lang=lang),
        parse_mode=ParseMode.DISABLED,
    )


def spotify_track_entry(tr: dict, fallback_thumb: str | None = None) -> dict:
    return {
        "type": "spotify",
        "url": tr.get("url"),
        "title": tr.get("name"),
        "artist": artist_names(tr.get("artists")),
        "duration": short_duration(tr.get("duration")),
        "thumbnail": tr.get("thumbnail_url") or fallback_thumb,
    }


async def show_spotify_results(message: Message, query: str, lang: str) -> None:
    try:
        results = await yt_api.search_spotify(query)
    except YTAPIError as e:
        if e.status == 404:
            await message.reply_text(t("no_results_text", lang))
            return
        LOGGER.warning("Spotify search failed for %r: %s", query, e)
        await message.reply_text(t("spotify_unavailable_text", lang))
        return

    if not results:
        await message.reply_text(t("no_results_text", lang))
        return

    lines, picks = [], []
    for i, r in enumerate(results, start=1):
        entry = spotify_track_entry(r)
        if not entry["url"]:
            continue
        picks.append((cache.put_new(entry), entry["url"]))

        title = entry["title"] or "Untitled"
        artist = entry["artist"]
        album = (r.get("album") or {}).get("name")
        details = " · ".join(x for x in (album, entry["duration"]) if x)
        lines.append(f"{len(picks)}. {title}" + (f" — {artist}" if artist else "")
                     + (f"\n    {details}" if details else ""))

    if not picks:
        await message.reply_text(t("no_results_text", lang))
        return

    body = t("spotify_results_text", lang, query=truncate(query, 60)) + "\n\n" + "\n".join(lines)
    await message.reply_text(
        body,
        reply_markup=keyboards.spotify_results_keyboard(picks, lang),
        parse_mode=ParseMode.DISABLED,
    )


async def dispatch_query(
    client, message: Message, kind: str, value: str, lang: str,
    *, as_video: bool = False, passive: bool = False,
) -> None:
    if kind == "ignore":
        return

    if kind == "youtube_video":
        title, channel, duration, thumb = "YouTube Video" if as_video else "YouTube Audio", "", None, None
        try:
            hits = await yt_api.search_youtube(value, limit=1)
            if hits:
                h = hits[0]
                title, channel, duration, thumb = h["title"], h.get("channel", ""), h.get("duration"), h.get("thumbnail")
        except YTAPIError:
            pass

        await start_single_download(client, message, {
            "type": "youtube", "video_id": value, "is_video": as_video,
            "title": title, "artist": channel, "duration": duration, "thumbnail": thumb,
        }, lang, passive=passive)

    elif kind == "youtube_playlist":
        data = await yt_api.get_youtube_playlist(value)
        tracks = data.get("tracks", [])
        await show_paginated_list(
            message, t("playlist_tracks_text", lang, count=len(tracks)),
            tracks,
            lambda tr: {
                "type": "youtube", "video_id": tr.get("url"), "is_video": as_video,
                "title": tr.get("title"), "artist": tr.get("channel"),
                "duration": tr.get("duration"), "thumbnail": tr.get("thumbnail"),
            },
            lang,
        )

    elif kind == "spotify_track":
        await start_single_download(client, message, {
            "type": "spotify", "url": value, "title": "Spotify Track",
        }, lang, passive=passive)

    elif kind in ("spotify_playlist", "spotify_album", "spotify_artist"):
        item = await yt_api.lookup_spotify(value) or {}
        tracks = (item.get("top_tracks") if kind == "spotify_artist" else item.get("tracks")) or []
        thumb = item.get("thumbnail_url")
        await show_paginated_list(
            message, t("collection_tracks_text", lang, name=item.get("name") or "Spotify", count=len(tracks)),
            tracks, lambda tr: spotify_track_entry(tr, thumb), lang,
        )

    elif kind == "deezer_track":
        await start_single_download(client, message, {
            "type": "deezer", "url": value, "title": "Deezer Track",
        }, lang, passive=passive)

    elif kind == "deezer_collection":
        data = await yt_api.search_deezer(value)
        tracks = (data or {}).get("tracks", [])
        await show_paginated_list(
            message, t("collection_tracks_text", lang, name="Deezer", count=len(tracks)),
            tracks,
            lambda tr: {
                "type": "deezer", "url": tr.get("url"),
                "title": tr.get("title") or tr.get("name"), "artist": tr.get("artist"),
                "duration": short_duration(tr.get("duration")), "thumbnail": tr.get("thumbnail_url"),
            },
            lang,
        )

    elif kind == "soundcloud":
        result = await yt_api.download_soundcloud(value)
        if not result or not result.get("cdn"):
            await message.reply_text(t("soundcloud_fetch_failed_text", lang))
            return
        await start_single_download(client, message, {
            "type": "soundcloud_direct", "cdn": result["cdn"],
            "title": result.get("title") or result.get("name") or "SoundCloud Track",
            "artist": result.get("artist") or "",
            "duration": result.get("duration"),
            "thumbnail": result.get("thumbnail") or result.get("thumbnail_url"),
        }, lang, passive=passive)

    elif kind in yt_api.social_platforms:
        await start_single_download(client, message, {
            "type": kind, "url": value, "title": classifier.social_labels.get(kind, kind.capitalize()),
        }, lang, passive=passive)

    elif kind == "applemusic_track":
        await start_single_download(client, message, {
            "type": "applemusic", "url": value, "title": "Apple Music Track",
        }, lang, passive=passive)

    elif kind == "applemusic_playlist":
        data = await yt_api.search_applemusic(value)
        tracks = (data or {}).get("tracks", [])
        await show_paginated_list(
            message, t("applemusic_tracks_text", lang, count=len(tracks)),
            tracks,
            lambda tr: {
                "type": "applemusic", "url": tr.get("track_url"),
                "title": tr.get("title"), "artist": tr.get("artist"),
                "duration": tr.get("duration"), "thumbnail": tr.get("thumbnail"),
            },
            lang,
        )

    elif kind == "jiosaavn_track":
        await start_single_download(client, message, {
            "type": "jiosaavn", "url": value, "title": "JioSaavn Track",
        }, lang, passive=passive)

    elif kind == "jiosaavn_playlist":
        data = await yt_api.search_jiosaavn(value)
        tracks = (data or {}).get("tracks", [])
        await show_paginated_list(
            message, t("jiosaavn_tracks_text", lang, count=len(tracks)),
            tracks,
            lambda tr: {
                "type": "jiosaavn", "url": tr.get("song_url"),
                "title": tr.get("title"), "duration": tr.get("duration"),
                "thumbnail": tr.get("thumbnail"),
            },
            lang,
        )

    elif kind == "terabox":
        if message.chat.type != ChatType.PRIVATE:
            await message.reply_text(t("terabox_private_only_text", lang))
            return
        status = await message.reply_text(t("starting_text", lang))
        await terabox_flow.run(client, value, chat_id=message.chat.id, status=status, lang=lang)

    elif kind == "unsupported_url":
        await message.reply_text(t("unsupported_link_text", lang))

    else:
        results = await yt_api.search_youtube(value, limit=5)
        entries = []
        for r in results:
            token = cache.put_new({
                "type": "youtube", "video_id": r["video_id"], "is_video": as_video,
                "title": r["title"], "artist": r.get("channel", ""),
                "duration": r.get("duration"), "thumbnail": r.get("thumbnail"),
            })
            entries.append((token, {"title": r["title"], "duration": r.get("duration")}))

        if not entries:
            await message.reply_text(t("no_results_text", lang))
            return

        await message.reply_text(
            t("top_results_text", lang, query=truncate(value, 60)),
            reply_markup=keyboards.results_keyboard(entries, lang=lang),
            parse_mode=ParseMode.DISABLED,
        )


async def safe_dispatch(client, message: Message, kind: str, value: str, lang: str, **kwargs) -> None:
    try:
        await dispatch_query(client, message, kind, value, lang, **kwargs)
    except YTAPIError as e:
        LOGGER.warning("Request failed (%s): %s", kind, e)
        if not kwargs.get("passive"):
            await message.reply_text(str(e))
    except Exception as e:
        LOGGER.exception("Unexpected error handling message from %s", message.chat.id)
        if not kwargs.get("passive"):
            await message.reply_text(t("something_wrong_text", lang, error=e))


def command_input(message: Message) -> tuple[str, list[str]]:
    parts = (message.text or "").split(None, 1)
    if len(parts) > 1 and parts[1].strip():
        return parts[1].strip(), classifier.urls_from_entities(message.entities)

    replied = message.reply_to_message
    if replied:
        body = (replied.text or replied.caption or "").strip()
        return body, classifier.urls_from_entities(replied.entities or replied.caption_entities)
    return "", []


async def yt_command(client, message: Message, lang: str) -> None:
    arg, extra = command_input(message)
    if not arg:
        await message.reply_text(t("yt_usage_text", lang), parse_mode=ParseMode.DISABLED)
        return

    kind, value = classifier.classify(arg, extra_urls=extra)
    if kind not in ("youtube_video", "youtube_playlist", "search"):
        await message.reply_text(t("yt_only_text", lang), parse_mode=ParseMode.DISABLED)
        return

    await safe_dispatch(client, message, kind, value, lang, as_video=True)


async def spotify_command(client, message: Message, lang: str) -> None:
    arg, extra = command_input(message)
    if not arg:
        await message.reply_text(t("spotify_usage_text", lang), parse_mode=ParseMode.DISABLED)
        return

    kind, value = classifier.classify(arg, extra_urls=extra)
    if kind.startswith("spotify_"):
        await safe_dispatch(client, message, kind, value, lang)
    elif kind == "search":
        try:
            await show_spotify_results(message, value, lang)
        except Exception as e:
            LOGGER.exception("Spotify search crashed for %r", value)
            await message.reply_text(t("something_wrong_text", lang, error=e))
    else:
        await message.reply_text(t("spotify_only_text", lang), parse_mode=ParseMode.DISABLED)
