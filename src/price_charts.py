"""Render real, dated price observations as shareable charts."""
from __future__ import annotations

import hashlib
import html
import json
from datetime import date
from pathlib import Path

from src.price_tracking import valid_observations

ROOT = Path(__file__).resolve().parents[1]
ASSET_BASE = 'https://raw.githubusercontent.com/kevinamartin88/worth-buying-uk/main/'


def chart_path(key: str, market: str, rows: list[dict]) -> Path:
    identity = json.dumps([key, rows], sort_keys=True).encode()
    return Path('assets/price-history') / market / (hashlib.sha256(identity).hexdigest()[:20] + '.png')


def render_chart(key: str, entry: dict, market: str) -> Path | None:
    currency = 'GBP' if market == 'uk' else 'USD'
    rows = valid_observations(entry, currency)
    if len(rows) < 3:
        return None
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    target = ROOT / chart_path(key, market, rows)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 3.2), layout='constrained')
    dates = [date.fromisoformat(row['date']) for row in rows]
    prices = [row['price'] for row in rows]
    ax.plot(dates, prices, marker='o', markersize=4, color='#125a85', linewidth=2)
    ax.set_ylim(bottom=0, top=max(prices) * 1.2)
    ax.set_ylabel(f'Observed listing price ({currency})')
    locator = mdates.AutoDateLocator(minticks=3, maxticks=6)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    title = str(entry.get('title') or 'Tracked listing')
    import textwrap
    ax.set_title('\n'.join(textwrap.wrap(title, 65)), fontsize=10, loc='left')
    ax.grid(axis='y', alpha=.2)
    fig.supxlabel('WorthBuying observations · individual listing, not a market-wide price index', fontsize=8)
    fig.savefig(target, dpi=130)
    plt.close(fig)
    return target


def chart_html(key: str, entry: dict, market: str) -> str:
    rows = valid_observations(entry, 'GBP' if market == 'uk' else 'USD')
    path = chart_path(key, market, rows)
    if len(rows) < 3 or not (ROOT / path).exists():
        return ''
    title = html.escape(str(entry.get('title') or 'Tracked listing'), quote=True)
    checked = rows[-1]['date']
    url = ASSET_BASE + path.as_posix() + '?v=' + checked
    return (f'<figure><img src="{url}" alt="Observed price history for {title}" '
            f'style="width:100%;max-width:800px;height:auto" loading="lazy">'
            f'<figcaption>{len(rows)} dated checks; latest observation {checked}. '
            'Prices may have changed since this check.</figcaption></figure>')
