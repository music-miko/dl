# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import contextlib

from pyrogram import Client

from .. import LOGGER
from ..locale import default_lang, text as t
from ..utils.classifier import classifier
from ..utils.helper import cache, duration_to_seconds, mojibake_fixer, status_reporter
from .api_client import YTAPIError, yt_api
from .downloader import downloader


def _track_meta(entry: dict, result: dict) -> dict:
    api_title = result.get("song_name") or result.get("title")
    title = (entry.get("title") or api_title) if entry.get("artist") else (api_title or entry.get("title"))
    return {
        **entry,
        "title": title,
        "thumbnail": result.get("thumbnail_url") or result.get("thumbnail") or entry.get("thumbnail"),
        "duration": result.get("duration") or entry.get("duration"),
    }


async def resolve_cdn(entry: dict, lang: str = default_lang) -> tuple[str, dict]:
    if entry.get("cdn"):
        return entry["cdn"], entry

    kind = entry["type"]

    if kind == "youtube":
        result = await yt_api.download_youtube(entry["video_id"], is_video=bool(entry.get("is_video")))
        return result.get("cdn"), entry

    if kind == "spotify":
        result = await yt_api.download_spotify(entry["url"])
        return result.get("cdn"), _track_meta(entry, result)

    if kind == "deezer":
        result = await yt_api.download_deezer(entry["url"])
        return result.get("cdn"), _track_meta(entry, result)

    if kind in yt_api.social_platforms:
        method = getattr(yt_api, yt_api.social_platforms[kind])
        result = await method(entry["url"])
        if not result.get("success"):
            reason = result.get("error") or result.get("message") or f"{kind.capitalize()} fetch failed"
            raise YTAPIError(f"Unable to fetch media from {kind.capitalize()}: {reason}")
        entry = {
            **entry,
            "title": result.get("title") or entry.get("title"),
            "thumbnail": result.get("thumbnail") or result.get("thumbnail_url") or entry.get("thumbnail"),
        }

        if kind in yt_api.stream_platforms:
            _check_stream(kind, result, entry, lang)

        if kind in ("instagram", "twitter"):
            caption_text = mojibake_fixer.fix(result.get("caption") or result.get("text"))
            author = result.get("author") or {}
            author_name = mojibake_fixer.fix(author.get("username") or author.get("name"))

            title_bits = [caption_text.strip()] if caption_text else []
            if author_name:
                title_bits.append(f"— @{author_name}" if not author_name.startswith("@") else f"— {author_name}")
            entry["title"] = " ".join(title_bits) or entry.get("title")

            media_list = result.get("media") or []
            if len(media_list) > 1:
                entry["media_group"] = media_list

        return result.get("cdn"), entry

    if kind == "applemusic":
        result = await yt_api.download_applemusic(entry["url"])
        if not result.get("success"):
            raise YTAPIError(f"Unable to fetch from Apple Music: {result.get('error', 'download failed')}")
        entry = {
            **entry,
            "title": result.get("title") or entry.get("title"),
            "artist": result.get("artist") or entry.get("artist"),
            "thumbnail": result.get("thumbnail") or entry.get("thumbnail"),
            "duration": result.get("duration") or entry.get("duration"),
        }
        return result.get("cdn"), entry

    if kind == "jiosaavn":
        result = await yt_api.download_jiosaavn(entry["url"])
        if not result.get("success"):
            raise YTAPIError(f"Unable to fetch from JioSaavn: {result.get('error', 'download failed')}")
        entry = {
            **entry,
            "title": result.get("title") or entry.get("title"),
            "artist": result.get("artist") or entry.get("artist"),
            "thumbnail": result.get("thumbnail") or entry.get("thumbnail"),
            "duration": result.get("duration") or entry.get("duration"),
        }
        return result.get("cdn"), entry

    if kind == "soundcloud_direct_link":
        result = await yt_api.download_soundcloud(entry["url"])
        if not result or not result.get("cdn"):
            raise YTAPIError("SoundCloud fetch failed")
        entry = {
            **entry,
            "title": result.get("title") or result.get("name") or entry.get("title"),
            "artist": result.get("artist") or entry.get("artist"),
            "thumbnail": result.get("thumbnail") or result.get("thumbnail_url") or entry.get("thumbnail"),
            "duration": result.get("duration") or entry.get("duration"),
        }
        return result["cdn"], entry

    raise YTAPIError(f"Unknown result type: {kind!r}")


def _check_stream(kind: str, result: dict, entry: dict, lang: str) -> None:
    if result.get("is_live") or result.get("kind") == "live":
        raise YTAPIError(t("live_not_supported_text", lang))

    cdn = result.get("cdn") or ""
    protocol = str((result.get("stream") or {}).get("protocol") or "")
    entry["hls"] = "m3u8" in protocol or downloader.looks_like_hls(cdn)

    duration = result.get("duration")
    if entry["hls"] and duration_to_seconds(duration) > downloader.hls_max_seconds:
        raise YTAPIError(t("video_too_long_text", lang, hours=downloader.hls_max_seconds // 3600))

    author = result.get("author") or {}
    entry["artist"] = mojibake_fixer.fix(author.get("name") or author.get("username")) or entry.get("artist")
    entry["duration"] = duration or entry.get("duration")


def _resolve_title_artist(entry: dict) -> tuple[str, str, str]:
    platform = entry["type"]
    if platform in ("soundcloud_direct", "soundcloud_direct_link"):
        platform = "soundcloud"
    title = entry.get("title") or "Untitled"
    artist = entry.get("artist") or entry.get("channel") or ""
    if platform in classifier.social_labels and title == "Untitled":
        title = classifier.social_labels[platform]
    return platform, title, artist


async def _fail(status, text: str, silent: bool) -> None:
    if silent:
        if status:
            with contextlib.suppress(Exception):
                await status.delete()
        return
    await status_reporter.update(status, text)


async def run_download(
    client: Client, token: str, *, chat_id: int, status=None, lang: str = default_lang,
    silent_fail: bool = False,
) -> None:
    entry = cache.get(token)
    if not entry:
        await status_reporter.update(status, t("expired_text", lang))
        return

    platform, title, artist = _resolve_title_artist(entry)
    duration = entry.get("duration")
    thumbnail = entry.get("thumbnail")

    await status_reporter.update(status, f"{t('downloading_text', lang)} {title}")

    try:
        cdn_url, entry = await resolve_cdn(entry, lang)
        title = entry.get("title") or title
        artist = entry.get("artist") or entry.get("channel") or artist
        thumbnail = entry.get("thumbnail") or thumbnail
        duration = entry.get("duration") or duration

        if not cdn_url:
            raise YTAPIError("No download link returned")

        await status_reporter.update(status, f"{t('sending_text', lang)} {title}")

        media_group = entry.get("media_group")
        if media_group:
            await downloader.deliver_media_group_to_chat(
                client, chat_id, media_group, caption=title, platform=platform,
            )
        else:
            await downloader.deliver_to_chat(
                client, chat_id, cdn_url,
                title=title, artist=artist, duration=duration,
                thumbnail_url=thumbnail, platform=platform, lang=lang,
                as_video=bool(entry.get("is_video")), is_hls=bool(entry.get("hls")),
            )
        if status:
            await status.delete()

    except YTAPIError as e:
        LOGGER.warning("Download failed for token=%s: %s", token, e)
        await _fail(status, t("failed_text", lang, error=e), silent_fail)
    except Exception as e:
        LOGGER.exception("Unexpected error delivering token=%s", token)
        await _fail(status, t("something_wrong_text", lang, error=e), silent_fail)
