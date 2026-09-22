from __future__ import annotations

from pathlib import Path

from atproto import Client, client_utils


class BlueskyClient:
    def __init__(self, handle: str, app_password: str, language: str) -> None:
        self.handle = handle.strip()
        self.app_password = app_password.strip()
        self.language = language
        self.client = Client()
        self.client.login(self.handle, self.app_password)

    @staticmethod
    def build_text(title: str, url: str, market_name: str):
        suffix_plain = "\n\nRead the guide: "
        tags_plain = "\n#WorthBuying #BuyingGuide"
        intro = (
            f"🔎 {title}\n\n"
            f"Our latest {market_name} buying guide compares current options, "
            "value and practical buying checks."
        )
        max_intro = max(60, 295 - len(suffix_plain) - len(url) - len(tags_plain))
        if len(intro) > max_intro:
            intro = intro[: max_intro - 1].rstrip() + "…"

        return (
            client_utils.TextBuilder()
            .text(intro)
            .text(suffix_plain)
            .link(url, url)
            .text("\n")
            .tag("#WorthBuying", "WorthBuying")
            .text(" ")
            .tag("#BuyingGuide", "BuyingGuide")
        )

    def publish(
        self,
        title: str,
        url: str,
        market_name: str,
        image_path: Path | None = None,
    ) -> dict:
        text = self.build_text(title, url, market_name)
        if image_path and image_path.exists():
            image_bytes = image_path.read_bytes()
            response = self.client.send_image(
                text=text,
                image=image_bytes,
                image_alt=f"{title} — Worth Buying",
                langs=[self.language],
            )
        else:
            response = self.client.send_post(
                text=text,
                langs=[self.language],
            )

        uri = str(response.uri)
        cid = str(response.cid)
        rkey = uri.rsplit("/", 1)[-1]
        web_url = f"https://bsky.app/profile/{self.handle}/post/{rkey}"
        return {
            "uri": uri,
            "cid": cid,
            "web_url": web_url,
        }
