from __future__ import annotations

import argparse
import json

from src.article_images import ROOT, require_hero_image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=("uk", "us"), required=True)
    args = parser.parse_args()

    article_dir = ROOT / ("articles" if args.market == "uk" else "articles-us")
    checked = 0
    missing: list[str] = []

    for path in sorted(article_dir.glob("*.json")):
        article = json.loads(path.read_text(encoding="utf-8"))
        if str(article.get("mode", "publish")).strip().lower() != "publish":
            continue
        if article.get("ai_visual_enabled", True) is False:
            continue

        slug = str(article.get("slug", "")).strip()
        if not slug:
            missing.append(f"{path.name}: missing slug")
            continue

        try:
            require_hero_image(args.market, slug)
        except RuntimeError as exc:
            missing.append(str(exc))
            continue
        checked += 1

    if missing:
        details = "\n".join(f"- {item}" for item in missing)
        raise RuntimeError(
            f"Required hero-image verification failed for {args.market.upper()}:\n{details}"
        )

    print(
        f"[image-gate-ok] {args.market.upper()}: "
        f"{checked} publishable article hero image(s) verified."
    )


if __name__ == "__main__":
    main()
