# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import os
import re
import ssl
import yt_dlp
import random
import asyncio
import aiohttp
import certifi
from pathlib import Path

from anamika import config, logger
from anamika.helpers import Track, utils
from py_yt import Playlist, VideosSearch


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.api_keys = [config.YOUTUBE_API_KEY, config.YOUTUBE_API_KEY_2]
        self.api_keys = [key for key in self.api_keys if key]
        self.current_key = 0
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.iregex = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=PL[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\S*"
        )

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def invalid(self, url: str) -> bool:
        return bool(re.match(self.iregex, url))

    def get_api_key(self):
        if not self.api_keys:
            return None
        return self.api_keys[self.current_key]

    def rotate_api_key(self):
        if not self.api_keys:
            return
        self.current_key = (self.current_key + 1) % len(self.api_keys)

    async def api_search(self, query: str) -> dict | None:
        key = self.get_api_key()
        if not key:
            return None
        params = {
            "part": "snippet",
            "q": query,
            "maxResults": 1,
            "type": "video",
            "key": key,
        }
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params,
                ssl=ssl_context,
            ) as resp:
                if resp.status == 403:
                    self.rotate_api_key()
                    return await self.api_search(query)
                if resp.status != 200:
                    return None
                data = await resp.json()
                if not data.get("items"):
                    return None
                return data["items"][0]

    async def get_video_details(self, video_id: str) -> dict | None:
        key = self.get_api_key()
        if not key:
            return None
        params = {
            "part": "contentDetails,statistics,snippet",
            "id": video_id,
            "key": key,
        }
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params=params,
                ssl=ssl_context,
            ) as resp:
                if resp.status == 403:
                    self.rotate_api_key()
                    return await self.get_video_details(video_id)
                if resp.status != 200:
                    return None
                data = await resp.json()
                if not data.get("items"):
                    return None
                return data["items"][0]

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        try:
            result = await self.api_search(query)
            if not result:
                # Fallback to scraper if API fails or no results
                _search = VideosSearch(query, limit=1, with_live=False)
                results = await _search.next()
                if results and results["result"]:
                    data = results["result"][0]
                    return Track(
                        id=data.get("id"),
                        channel_name=data.get("channel", {}).get("name"),
                        duration=data.get("duration"),
                        duration_sec=utils.to_seconds(data.get("duration")),
                        message_id=m_id,
                        title=data.get("title")[:25],
                        thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                        url=data.get("link"),
                        view_count=data.get("viewCount", {}).get("short"),
                        video=video,
                    )
                return None

            video_id = result["id"]["videoId"]
            details = await self.get_video_details(video_id)
            if not details:
                return None

            snippet = details.get("snippet", {})
            content = details.get("contentDetails", {})
            stats = details.get("statistics", {})

            # Convert ISO 8601 duration to seconds
            duration_iso = content.get("duration", "PT0S")
            duration_sec = utils.to_seconds(duration_iso)
            duration = utils.get_readable_time(duration_sec)

            return Track(
                id=video_id,
                channel_name=snippet.get("channelTitle"),
                duration=duration,
                duration_sec=duration_sec,
                message_id=m_id,
                title=snippet.get("title")[:25],
                thumbnail=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                url=f"https://www.youtube.com/watch?v={video_id}",
                view_count=stats.get("viewCount"),
                video=video,
            )
        except Exception as ex:
            logger.warning(f"Search failed: {ex}")
            return None

    async def playlist(
        self, limit: int, user: str, url: str, video: bool
    ) -> list[Track | None]:
        tracks = []
        try:
            # Try using API first
            if "list=" in url:
                playlist_id = url.split("list=")[1].split("&")[0]
                key = self.get_api_key()
                if key:
                    params = {
                        "part": "snippet,contentDetails",
                        "playlistId": playlist_id,
                        "maxResults": limit,
                        "key": key,
                    }
                    ssl_context = ssl.create_default_context(cafile=certifi.where())
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            "https://www.googleapis.com/youtube/v3/playlistItems",
                            params=params,
                            ssl=ssl_context,
                        ) as resp:
                            if resp.status == 403:
                                self.rotate_api_key()
                                return await self.playlist(limit, user, url, video)
                            if resp.status == 200:
                                data = await resp.json()
                                for item in data.get("items", []):
                                    snippet = item.get("snippet", {})
                                    video_id = snippet.get("resourceId", {}).get(
                                        "videoId"
                                    )
                                    tracks.append(
                                        Track(
                                            id=video_id,
                                            channel_name=snippet.get("channelTitle"),
                                            duration="00:00",  # Need separate call for duration
                                            duration_sec=0,
                                            title=snippet.get("title")[:25],
                                            thumbnail=snippet.get("thumbnails", {})
                                            .get("high", {})
                                            .get("url"),
                                            url=f"https://www.youtube.com/watch?v={video_id}",
                                            user=user,
                                            view_count="",
                                            video=video,
                                        )
                                    )
                                return tracks

            # Fallback to scraper
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except Exception as ex:
            logger.warning(f"Playlist failed: {ex}")
        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        url = self.base + video_id
        ext = "mp4" if video else "webm"
        filename = f"downloads/{video_id}.{ext}"

        if Path(filename).exists():
            return filename

        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            },
        }

        if video:
            ydl_opts = {
                **base_opts,
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio)",
                "merge_output_format": "mp4",
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": "bestaudio[ext=webm][acodec=opus]",
            }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError):
                    return None
                except Exception as ex:
                    logger.warning("Download failed: %s", ex)
                    return None
            return filename

        return await asyncio.to_thread(_download)
