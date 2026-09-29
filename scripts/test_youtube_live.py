from __future__ import annotations

import argparse

from publish_youtube_shorts import CONFIG
from src.youtube import YouTubeClient


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify YouTube OAuth without uploading")
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    args = parser.parse_args()

    if not YouTubeClient.configured(args.market):
        raise RuntimeError(f"YouTube secrets are not configured for {args.market.upper()}")
    client = YouTubeClient.from_env(args.market)
    channel = client.verify_channel(CONFIG[args.market]["channel_id"])
    print(f"Verified {channel['snippet']['title']} ({channel['id']}); no video uploaded.")


if __name__ == "__main__":
    main()
