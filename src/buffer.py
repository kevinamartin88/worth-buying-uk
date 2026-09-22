from __future__ import annotations

import json
import os
import re
import time

import requests


class BufferClient:
    API_URL = "https://api.buffer.com"

    def __init__(self, api_key: str, channel_name: str = "Worth Buying UK") -> None:
        self.api_key = api_key
        self.channel_name = channel_name
        self._channel_id: str | None = None
        self._channel_name: str | None = None

    @classmethod
    def from_env(cls) -> "BufferClient":
        api_key = os.environ["BUFFER_API_KEY"].strip()
        channel_name = os.getenv("BUFFER_CHANNEL_NAME", "Worth Buying UK").strip()
        return cls(api_key=api_key, channel_name=channel_name)

    @staticmethod
    def _normalise_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.casefold())

    def _graphql(self, query: str) -> dict:
        response = requests.post(
            self.API_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"query": query},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"Buffer API error: {payload['errors']}")
        return payload.get("data", {})

    def find_channel_id(self, services: set[str], label: str) -> str:
        account = self._graphql(
            "query { account { organizations { id name } } }"
        )
        organizations = account.get("account", {}).get("organizations", [])
        channels: list[dict] = []

        wanted_services = {service.casefold() for service in services}
        for organization in organizations:
            org_id = json.dumps(organization["id"])
            data = self._graphql(
                f"query {{ channels(input: {{ organizationId: {org_id} }}) {{ id name displayName externalLink descriptor service type isDisconnected isLocked }} }}"
            )
            for channel in data.get("channels", []):
                service = str(channel.get("service", "")).casefold()
                if service in wanted_services:
                    channels.append(channel)

        if not channels:
            raise RuntimeError(f"No {label} channel is connected to Buffer.")

        for channel in channels:
            print(
                "[buffer-channel] "
                f"name={channel.get('name')} "
                f"displayName={channel.get('displayName')} "
                f"externalLink={channel.get('externalLink')} "
                f"descriptor={channel.get('descriptor')} "
                f"service={channel.get('service')} "
                f"type={channel.get('type')} "
                f"disconnected={channel.get('isDisconnected')} "
                f"locked={channel.get('isLocked')} "
                f"id={channel.get('id')}"
            )

        wanted = self.channel_name.casefold()
        exact = [c for c in channels if str(c.get("name", "")).casefold() == wanted]

        selected: dict | None = None
        if exact:
            selected = exact[0]
        else:
            wanted_normalised = self._normalise_name(self.channel_name)
            normalised = [
                c for c in channels
                if self._normalise_name(str(c.get("name", ""))) == wanted_normalised
            ]
            if normalised:
                selected = normalised[0]
            else:
                partial = [
                    c for c in channels
                    if wanted in str(c.get("name", "")).casefold()
                ]
                if partial:
                    selected = partial[0]
                elif len(channels) == 1:
                    selected = channels[0]

        if selected:
            selected_id = str(selected["id"])
            selected_name = str(selected.get("name", self.channel_name))
            print(
                f"[buffer] Selected {label} channel: {selected_name} "
                f"(displayName={selected.get('displayName')}, "
                f"externalLink={selected.get('externalLink')}, "
                f"service={selected.get('service')}, id={selected_id})"
            )
            return selected_id

        available = ", ".join(str(c.get("name", c.get("id"))) for c in channels)
        raise RuntimeError(
            f"Could not uniquely identify Buffer channel '{self.channel_name}'. "
            f"Connected {label} channels: {available}"
        )

    def find_x_channel_id(self) -> str:
        if self._channel_id:
            return self._channel_id
        self._channel_id = self.find_channel_id({"twitter", "x"}, "X/Twitter")
        return self._channel_id

    def find_bluesky_channel_id(self) -> str:
        return self.find_channel_id({"bluesky"}, "Bluesky")

    def get_post(self, post_id: str) -> dict:
        safe_id = json.dumps(post_id)
        data = self._graphql(
            f"""
            query GetPost {{
              post(input: {{ id: {safe_id} }}) {{
                id
                text
                status
                channelId
                dueAt
                sentAt
                sharedNow
                shareMode
                assets {{ id mimeType }}
              }}
            }}
            """
        )
        post = data.get("post")
        if not post:
            raise RuntimeError(f"Buffer post {post_id} was not found.")
        return post

    def wait_for_post(self, post_id: str, timeout_seconds: int = 90) -> dict:
        deadline = time.time() + timeout_seconds
        last: dict = {}
        while time.time() < deadline:
            last = self.get_post(post_id)
            status = str(last.get("status", "")).lower()
            if status in {"sent", "error"}:
                return last
            time.sleep(3)
        return last

    def create_post(
        self,
        text: str,
        mode: str = "shareNow",
        image_url: str | None = None,
        channel_id: str | None = None,
    ) -> dict:
        channel_id = channel_id or self.find_x_channel_id()
        safe_text = json.dumps(text, ensure_ascii=False)
        safe_channel = json.dumps(channel_id)
        assets = ""
        if image_url:
            safe_image = json.dumps(image_url)
            assets = f"assets: [{{ image: {{ url: {safe_image} }} }}]"

        query = f"""
        mutation CreatePost {{
          createPost(input: {{
            text: {safe_text}
            channelId: {safe_channel}
            schedulingType: automatic
            mode: {mode}
            {assets}
          }}) {{
            ... on PostActionSuccess {{
              post {{
                id
                text
                status
                channelId
                dueAt
                sentAt
                sharedNow
                shareMode
                assets {{ id mimeType }}
              }}
            }}
            ... on MutationError {{
              message
            }}
          }}
        }}
        """
        data = self._graphql(query)
        result = data.get("createPost") or {}
        if result.get("message"):
            raise RuntimeError(f"Buffer could not create the post: {result['message']}")
        post = result.get("post")
        if not post or not post.get("id"):
            raise RuntimeError(f"Unexpected Buffer response: {result}")
        return post
