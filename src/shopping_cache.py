"""Short-lived public demand observations; never store account credentials."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parents[1] / "state" / "google_shopping_cache.json"
MAX_AGE = 24 * 60 * 60
COOLDOWN = 6 * 60 * 60


def read_cache() -> dict:
    try:
        value = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cache(value: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cached_topics(topics: list[tuple], market: str) -> list[tuple[tuple, dict]]:
    entries = read_cache().get(market, {}).get("entries", {})
    result = []
    now = time.time()
    for topic in topics:
        entry = entries.get(str(topic[2]).strip().casefold(), {})
        try:
            age = now - float(entry.get("checked_at", 0))
            signal = entry["signal"]
            score = float(signal["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if market == "us" and signal.get("geo") != "US":
            continue
        if 0 <= age < MAX_AGE and math.isfinite(score) and score > 0:
            result.append((topic, {**signal, "cached": True, "observed_at": entry["checked_at"]}))
    return sorted(result, key=lambda pair: -float(pair[1]["score"]))


def cooling_down(market: str) -> bool:
    try:
        return float(read_cache().get(market, {}).get("retry_after", 0)) > time.time()
    except (TypeError, ValueError):
        return False


def remember(market: str, ranked: list, rate_limited: bool = False) -> None:
    cache = read_cache()
    state = cache.setdefault(market, {})
    now = time.time()
    entries = state.setdefault("entries", {})
    entries = {
        key: value for key, value in entries.items()
        if isinstance(value, dict) and isinstance(value.get("checked_at"), (int, float))
        and 0 <= now - value["checked_at"] < MAX_AGE
    }
    for _, signal in ranked:
        entries[str(signal["query"]).strip().casefold()] = {
            "checked_at": now, "signal": signal,
        }
    state["entries"] = entries
    if rate_limited:
        state["retry_after"] = now + COOLDOWN
    save_cache(cache)
