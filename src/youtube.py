from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
TOKEN_URI = "https://oauth2.googleapis.com/token"
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}


@dataclass(frozen=True)
class YouTubeAuth:
    client_id: str
    client_secret: str
    refresh_token: str


class YouTubeClient:
    """Small, channel-safe wrapper around the YouTube Data API."""

    def __init__(self, auth: YouTubeAuth):
        credentials = Credentials(
            token=None,
            refresh_token=auth.refresh_token,
            token_uri=TOKEN_URI,
            client_id=auth.client_id,
            client_secret=auth.client_secret,
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )
        credentials.refresh(Request())
        self.service = build(
            "youtube",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    @staticmethod
    def _refresh_token_name(market: str) -> str:
        return "YOUTUBE_UK_REFRESH_TOKEN" if market == "uk" else "YOUTUBE_US_REFRESH_TOKEN"

    @classmethod
    def configured(cls, market: str) -> bool:
        names = (
            "YOUTUBE_CLIENT_ID",
            "YOUTUBE_CLIENT_SECRET",
            cls._refresh_token_name(market),
        )
        return all(os.getenv(name, "").strip() for name in names)

    @classmethod
    def from_env(cls, market: str) -> "YouTubeClient":
        if market not in {"uk", "us"}:
            raise ValueError(f"Unsupported YouTube market: {market}")
        values = {
            "client_id": os.getenv("YOUTUBE_CLIENT_ID", "").strip(),
            "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET", "").strip(),
            "refresh_token": os.getenv(cls._refresh_token_name(market), "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(
                "YouTube OAuth is not configured for this market. Missing: "
                + ", ".join(missing)
            )
        return cls(YouTubeAuth(**values))

    def current_channel(self) -> dict:
        response = self.service.channels().list(part="id,snippet", mine=True).execute()
        items = response.get("items", [])
        if len(items) != 1:
            raise RuntimeError(
                "The YouTube OAuth token did not resolve to exactly one channel. "
                "Create a separate refresh token while the intended Brand Account is selected."
            )
        return items[0]

    def verify_channel(self, expected_channel_id: str) -> dict:
        channel = self.current_channel()
        actual = str(channel.get("id", ""))
        if actual != expected_channel_id:
            title = channel.get("snippet", {}).get("title", "unknown channel")
            raise RuntimeError(
                f"YouTube token belongs to {title} ({actual}), not expected channel "
                f"{expected_channel_id}. Upload stopped before publishing."
            )
        return channel

    def upload_video(
        self,
        video_path: Path,
        *,
        title: str,
        description: str,
        tags: list[str],
        privacy_status: str = "public",
        max_retries: int = 6,
    ) -> dict:
        if privacy_status not in {"public", "private", "unlisted"}:
            raise ValueError(f"Unsupported privacy status: {privacy_status}")
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags,
                "categoryId": "26",
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }
        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                chunksize=8 * 1024 * 1024,
                resumable=True,
            ),
        )
        response = None
        retry = 0
        while response is None:
            try:
                _, response = request.next_chunk()
            except HttpError as exc:
                status = getattr(exc.resp, "status", None)
                if status not in RETRIABLE_STATUS_CODES or retry >= max_retries:
                    raise
                retry += 1
                time.sleep(random.uniform(0, min(2**retry, 30)))
        return response
