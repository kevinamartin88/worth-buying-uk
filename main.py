from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.ebay import EbayClient
from src.render import render_post
from src.scoring import evaluate_item
from src.state import JsonState


ROOT = Path(__file__).resolve().parent


def load_config() -> dict:
    with open(ROOT / "config.yml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    cfg = load_config()
    mock_ebay = bool_env("MOCK_EBAY", False)
    dry_run = bool_env("DRY_RUN", False)

    price_state = JsonState(ROOT / "state" / "price_history.json", default={})
    publish_state = JsonState(ROOT / "state" / "published.json", default={})

    ebay = EbayClient(
        marketplace=cfg["site"]["marketplace"],
        delivery_country=cfg["site"]["delivery_country"],
        mock=mock_ebay,
        mock_file=ROOT / "sample_data" / "item_summaries.json",
    )

    blogger = None
    if not dry_run:
        from src.blogger import BloggerClient
        blogger = BloggerClient.from_env()

    now = datetime.now(timezone.utc)
    run_stamp = now.strftime("%Y%m%d")
    generated = 0

    for niche in cfg["niches"]:
        slug = niche["slug"]
        affiliate_reference = f"{slug}-{run_stamp}"[:256]

        items = ebay.search(
            query=niche["query"],
            max_price=float(niche["max_price"]),
            require_free_shipping=bool(niche.get("require_free_shipping", False)),
            affiliate_reference=affiliate_reference,
            limit=max(int(niche.get("max_items", 8)) * 4, 20),
        )

        selected = []
        for item in items:
            evaluation = evaluate_item(
                item=item,
                price_history=price_state.data,
                max_price=float(niche["max_price"]),
                min_seller_feedback_percent=float(cfg["site"]["min_seller_feedback_percent"]),
                min_seller_feedback_score=int(cfg["site"]["min_seller_feedback_score"]),
            )

            record_observation(
                price_state=price_state,
                item=item,
                max_points=int(cfg["site"]["history_max_points_per_item"]),
                now=now,
            )

            if evaluation["eligible"] and evaluation["score"] >= float(niche["min_score"]):
                enriched = dict(item)
                enriched["_evaluation"] = evaluation
                selected.append(enriched)

            if len(selected) >= int(niche.get("max_items", 8)):
                break

        title = f'{cfg["site"]["title_prefix"]}: {niche["name"]}'
        html = render_post(
            title=title,
            niche=niche,
            items=selected,
            disclosure=cfg["site"]["affiliate_disclosure"],
            generated_at=now,
            marketplace=cfg["site"]["marketplace"],
        )

        if dry_run:
            out_dir = ROOT / "out"
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / f"{slug}.html"
            out_path.write_text(
                f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title></head><body>{html}</body></html>",
                encoding="utf-8",
            )
            print(f"[dry-run] wrote {out_path}")
            generated += 1
            continue

        should_publish = bool(selected) or bool(cfg["publishing"].get("publish_when_no_items", True))
        if not should_publish:
            print(f"[skip] {slug}: no qualifying items")
            continue

        known_post_id = publish_state.data.get(slug, {}).get("post_id")

        if known_post_id and cfg["publishing"].get("update_existing_posts", True):
            post = blogger.update_post(post_id=known_post_id, title=title, content=html)
            action = "updated"
        else:
            existing = blogger.find_post_by_exact_title(title)
            if existing and cfg["publishing"].get("update_existing_posts", True):
                post = blogger.update_post(post_id=existing["id"], title=title, content=html)
                action = "updated"
            else:
                post = blogger.create_post(title=title, content=html)
                action = "created"

        publish_state.data[slug] = {
            "post_id": post["id"],
            "url": post.get("url"),
            "title": title,
            "last_updated_utc": now.isoformat(),
            "qualifying_items": len(selected),
        }
        print(f"[{action}] {title} -> {post.get('url', post['id'])}")
        generated += 1

    price_state.save()
    publish_state.save()
    print(f"Finished. Generated/updated {generated} niche page(s).")


def record_observation(
    price_state: JsonState,
    item: dict,
    max_points: int,
    now: datetime,
) -> None:
    item_id = item.get("itemId")
    price = safe_float((item.get("price") or {}).get("value"))
    currency = (item.get("price") or {}).get("currency")
    if not item_id or price is None:
        return

    entry = price_state.data.setdefault(item_id, {"title": item.get("title", ""), "observations": []})
    entry["title"] = item.get("title", entry.get("title", ""))
    obs = entry.setdefault("observations", [])
    obs.append({"ts": now.isoformat(), "price": price, "currency": currency})
    if len(obs) > max_points:
        del obs[:-max_points]


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
