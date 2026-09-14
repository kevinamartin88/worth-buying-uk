from __future__ import annotations

import json
import os

import requests


class BufferClient:
    API_URL = "https://api.buffer.com"

    def __init__(self, api_key: str, channel_name: str = "Worth Buying UK") -> None:
        self.api_key = api_key
        self.channel_name = channel_name
        self._channel_id: str | None = None

    @classmethod
    def from_env(cls) -> "BufferClient":
        api_key = os.environ["BUFFER_API_KEY"].strip()
        channel_name = os.getenv("BUFFER_CHANNEL_NAME", "Worth Buying UK").strip()
        return cls(api_key=api_key, channel_name=channel_name)

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

    def find_x_channel_id(self) -> str:
        if self._channel_id:
            return self._channel_id

        account = self._graphql(
            "query { account { organizations { id name } } }"
        )
        organizations = account.get("account", {}).get("organizations", [])
        x_channels: list[dict] = []

        for organization in organizations:
            org_id = json.dumps(organization["id"])
            data = self._graphql(
                f"query {{ channels(input: {{ organizationId: {org_id} }}) {{ id name service }} }}"
            )
            for channel in data.get("channels", []):
                service = str(channel.get("service", "")).lower()
                if service in {"twitter", "x"}:
                    x_channels.append(channel)

        if not x_channels:
            raise RuntimeError("No X/Twitter channel is connected to Buffer.")

        wanted = self.channel_name.casefold()
        exact = [c for c in x_channels if str(c.get("name", "")).casefold() == wanted]
        if exact:
            self._channel_id = exact[0]["id"]
            return self._channel_id

        partial = [c for c in x_channels if wanted in str(c.get("name", "")).casefold()]
        if partial:
            self._channel_id = partial[0]["id"]
            return self._channel_id

        if len(x_channels) == 1:
            self._channel_id = x_channels[0]["id"]
            return self._channel_id

        available = ", ".join(str(c.get("name", c.get("id"))) for c in x_channels)
        raise RuntimeError(
            f"Could not uniquely identify Buffer channel '{self.channel_name}'. "
            f"Connected X channels: {available}"
        )

    def create_post(self, text: str, mode: str = "shareNow") -> dict:
        channel_id = self.find_x_channel_id()
        safe_text = json.dumps(text, ensure_ascii=False)
        safe_channel = json.dumps(channel_id)
        query = f"""
        mutation CreatePost {{
          createPost(input: {{
            text: {safe_text}
            channelId: {safe_channel}
            schedulingType: automatic
            mode: {mode}
          }}) {{
            ... on PostActionSuccess {{
              post {{ id text status dueAt }}
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
