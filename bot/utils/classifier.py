# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import re


class MessageClassifier:

    def __init__(self):
        yt_host = r"(?:(?:www|m|music)\.)?"
        self.youtube_playlist_re = re.compile(
            r"^https?://" + yt_host + r"(?:youtube\.com|youtu\.be)/\S*?[?&]list=([A-Za-z0-9_-]+)", re.I
        )
        self.youtube_video_re = re.compile(
            r"^https?://" + yt_host
            + r"(?:youtube\.com/(?:watch\?(?:\S*?&)?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})",
            re.I,
        )
        self.youtube_bare_id_re = re.compile(r"^[A-Za-z0-9_-]{11}$")

        sp = r"^https?://open\.spotify\.com/(?:intl-[a-z-]+/)?"
        self.spotify_track_re = re.compile(sp + r"track/[A-Za-z0-9]+", re.I)
        self.spotify_album_re = re.compile(sp + r"album/[A-Za-z0-9]+", re.I)
        self.spotify_artist_re = re.compile(sp + r"artist/[A-Za-z0-9]+", re.I)
        self.spotify_playlist_re = re.compile(sp + r"playlist/[A-Za-z0-9]+", re.I)

        self.deezer_url_re = re.compile(
            r"^https?://(?:www\.|m\.|link\.)?(?:deezer\.com|dzr\.page\.link)/", re.I
        )
        self.deezer_track_re = re.compile(
            r"^https?://(?:www\.|m\.)?deezer\.com/(?:[a-z]{2}(?:-[a-z]{2})?/)?track/\d+", re.I
        )

        self.soundcloud_re = re.compile(r"^https?://(?:(?:www|m|on)\.)?soundcloud\.com/.+", re.I)

        self.instagram_re = re.compile(
            r"^https?://(www\.)?instagram\.com/(p|reel|reels|tv|stories|share)/.+", re.I
        )
        self.facebook_re = re.compile(r"^https?://(www\.|web\.|m\.)?(facebook\.com|fb\.watch)/.+", re.I)
        self.threads_re = re.compile(r"^https?://(www\.)?threads\.(net|com)/.+", re.I)
        self.bluesky_re = re.compile(r"^https?://(www\.)?bsky\.app/.+", re.I)
        self.tiktok_re = re.compile(r"^https?://(www\.|vm\.|vt\.)?tiktok\.com/.+", re.I)
        self.twitter_re = re.compile(
            r"^https?://(www\.)?(twitter\.com|x\.com)/(?:[A-Za-z0-9_]+|i)/status/\d+", re.I
        )
        self.pinterest_re = re.compile(r"^https?://(www\.)?(pinterest\.[a-z.]+|pin\.it)/.+", re.I)
        self.reddit_re = re.compile(
            r"^https?://((www\.|old\.|new\.|m\.)?reddit\.com/.+|redd\.it/.+)", re.I
        )
        self.snapchat_re = re.compile(r"^https?://([a-z0-9-]+\.)?snapchat\.com/.+", re.I)
        self.linkedin_re = re.compile(
            r"^https?://(([a-z]{2,3}|www)\.)?linkedin\.com/.+|^https?://lnkd\.in/.+", re.I
        )
        self.dailymotion_re = re.compile(
            r"^https?://(www\.|geo\.)?dailymotion\.com/.+|^https?://dai\.ly/.+", re.I
        )
        self.kick_re = re.compile(
            r"^https?://(www\.)?kick\.com/(?!(?:categories|search|auth)(?:[/?#]|$)).+", re.I
        )

        self.terabox_re = re.compile(
            r"^https?://([a-z0-9-]+\.)*"
            r"(terabox\w*|1024tera\w*|terasharelink|terafileshare|"
            r"nephobox|4funbox|mirrobox|momerybox|freeterabox)"
            r"\.(com|app|net|co|link|cc)/.+",
            re.I,
        )

        self.applemusic_url_re = re.compile(
            r"^https?://music\.apple\.com/([a-z]{2})/(song|album|playlist)/[^/?#]+(?:/[^/?#]+)*?/(\d+|pl\.[a-z0-9]+)",
            re.I,
        )
        self.jiosaavn_url_re = re.compile(
            r"^https?://(www\.)?jiosaavn\.com/(song|album|playlist|featured)/", re.I
        )

        self.url_re = re.compile(r"https?://[^\s<>\"'\u200b\u200c\u200d]+", re.I)
        self._trailing_junk = ".,;:!?\"'\u201d\u2019\u2026>"
        self._brackets = {")": "(", "]": "[", "}": "{"}

        self.social_patterns = [
            ("instagram", self.instagram_re),
            ("facebook", self.facebook_re),
            ("threads", self.threads_re),
            ("bluesky", self.bluesky_re),
            ("tiktok", self.tiktok_re),
            ("twitter", self.twitter_re),
            ("pinterest", self.pinterest_re),
            ("reddit", self.reddit_re),
            ("snapchat", self.snapchat_re),
            ("linkedin", self.linkedin_re),
            ("dailymotion", self.dailymotion_re),
            ("kick", self.kick_re),
        ]
        self.social_kinds = {kind for kind, _ in self.social_patterns}
        self.social_labels = {
            "instagram": "Instagram media",
            "facebook": "Facebook media",
            "threads": "Threads media",
            "bluesky": "Bluesky media",
            "tiktok": "TikTok video",
            "twitter": "Twitter/X media",
            "pinterest": "Pinterest media",
            "reddit": "Reddit media",
            "snapchat": "Snapchat media",
            "linkedin": "LinkedIn media",
            "dailymotion": "Dailymotion video",
            "kick": "Kick video",
        }

    def _clean_url(self, url: str) -> str:
        while url:
            last = url[-1]
            if last in self._trailing_junk:
                url = url[:-1]
            elif last in self._brackets and url.count(last) > url.count(self._brackets[last]):
                url = url[:-1]
            else:
                break
        return url

    def extract_urls(self, text: str, extra_urls=()) -> list[str]:
        found: list[str] = []
        for raw in self.url_re.findall(text or ""):
            url = self._clean_url(raw)
            if url:
                found.append(url)
        for raw in extra_urls or ():
            url = self._clean_url((raw or "").strip())
            if url.lower().startswith(("http://", "https://")):
                found.append(url)
        return list(dict.fromkeys(found))

    @staticmethod
    def urls_from_entities(entities) -> list[str]:
        urls = []
        for e in entities or ():
            if getattr(getattr(e, "type", None), "name", "") == "TEXT_LINK" and getattr(e, "url", None):
                urls.append(e.url)
        return urls

    def classify_url(self, url: str) -> str:
        if self.spotify_playlist_re.match(url):
            return "spotify_playlist"
        if self.spotify_album_re.match(url):
            return "spotify_album"
        if self.spotify_artist_re.match(url):
            return "spotify_artist"
        if self.spotify_track_re.match(url):
            return "spotify_track"
        if self.youtube_playlist_re.match(url):
            return "youtube_playlist"
        if self.youtube_video_re.match(url):
            return "youtube_video"
        if self.soundcloud_re.match(url):
            return "soundcloud"
        if self.deezer_track_re.match(url):
            return "deezer_track"
        if self.deezer_url_re.match(url):
            return "deezer_collection"
        if self.terabox_re.match(url):
            return "terabox"

        apple_match = self.applemusic_url_re.match(url)
        if apple_match:
            if apple_match.group(2) == "song" or "i=" in url.split("?", 1)[-1]:
                return "applemusic_track"
            return "applemusic_playlist"

        if self.jiosaavn_url_re.match(url):
            return "jiosaavn_track" if "/song/" in url else "jiosaavn_playlist"

        for kind, pattern in self.social_patterns:
            if pattern.match(url):
                return kind

        return "unsupported_url"

    def is_bare_youtube_id(self, text: str) -> bool:
        if not self.youtube_bare_id_re.match(text):
            return False
        has_symbol = any(c.isdigit() or c in "-_" for c in text)
        return has_symbol or sum(c.isupper() for c in text) >= 2

    def classify(self, text: str, *, strict: bool = False, extra_urls=()) -> tuple[str, str]:
        text = (text or "").strip()
        urls = self.extract_urls(text, extra_urls)

        for url in urls:
            kind = self.classify_url(url)
            if kind != "unsupported_url":
                return kind, url

        if strict:
            return "ignore", text
        if urls:
            return "unsupported_url", urls[0]
        if self.is_bare_youtube_id(text):
            return "youtube_video", text
        return "search", text


classifier = MessageClassifier()
