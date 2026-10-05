"""Bounded daily rechecks of the exact marketplace listings already observed."""
from __future__ import annotations

import json
import math
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def refresh_tracked_prices(path: Path, market: str, client, *, now=None, limit=20, budget_seconds=90) -> int:
    now = now or datetime.now(ZoneInfo('Europe/London'))
    today = now.date().isoformat()
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return 0
    prefix = f'daily|{market}|'
    currency = 'GBP' if market == 'uk' else 'USD'
    rows = [(key, entry) for key, entry in state.items()
            if key.startswith(prefix) and isinstance(entry, dict)
            and entry.get('tracking_status') != 'ended'
            and entry.get('last_attempt_date') != today
            and not any(obs.get('date') == today for obs in entry.get('observations', []))]
    rows.sort(key=lambda row: row[1].get('last_attempt_date', ''))
    started = time.monotonic()
    updated = 0
    for key, entry in rows[:limit]:
        if time.monotonic() - started >= budget_seconds:
            break
        entry['last_attempt_date'] = today
        item_id = key[len(prefix):]
        try:
            item = client.get_item(item_id, affiliate_reference=entry.get('article_slug', ''))
            if item.get('itemId') != item_id:
                entry['tracking_status'] = 'unverified'
                continue
            ended = item.get('itemEndDate')
            if ended and datetime.fromisoformat(ended.replace('Z', '+00:00')) <= now:
                entry['tracking_status'] = 'ended'
                continue
            availability = item.get('estimatedAvailabilities') or []
            if availability and all(a.get('estimatedAvailabilityStatus') == 'OUT_OF_STOCK' for a in availability):
                entry['tracking_status'] = 'unavailable'
                continue
            price = float((item.get('price') or {}).get('value', 0))
            if not math.isfinite(price) or price <= 0 or (item.get('price') or {}).get('currency') != currency:
                entry['tracking_status'] = 'unverified'
                continue
            observations = [obs for obs in entry.get('observations', []) if obs.get('date') != today]
            observations.append({'date': today, 'ts': now.isoformat(), 'price': price, 'currency': currency})
            entry['observations'] = observations[-90:]
            entry['tracking_status'] = 'active'
            updated += 1
        except Exception as exc:
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            entry['tracking_status'] = 'ended' if status in (404, 410) else 'check-failed'
            print(f'[price-check-warning] {market.upper()}: {type(exc).__name__}, HTTP {status}')
            if status in (401, 403, 429) or status is None:
                break
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(f'[price-history] {market.upper()}: rechecked {updated} tracked listings')
    return updated


def valid_observations(entry: dict, currency: str, today: date | None = None) -> list[dict]:
    """Distinct dated observations in one currency, with a recent latest check."""
    today = today or datetime.now(ZoneInfo('Europe/London')).date()
    if entry.get('tracking_status') in ('ended', 'unavailable'):
        return []
    by_date = {}
    for obs in entry.get('observations', []):
        try:
            checked = date.fromisoformat(obs['date'])
            price = float(obs['price'])
        except (KeyError, TypeError, ValueError):
            continue
        if checked <= today and math.isfinite(price) and price > 0 and obs.get('currency') == currency:
            by_date[checked] = {**obs, 'price': price}
    if not by_date or (today - max(by_date)).days > 7:
        return []
    return [by_date[day] for day in sorted(by_date)]
