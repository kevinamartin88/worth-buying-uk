"""Repair nine affected heroes with verified product photos before AI fallback."""
import json
import os
from pathlib import Path
from src.ai_visuals import generate_image

SLUGS = {
    'uk': ['best-non-slip-hangers-worth-buying-uk-2026-daily-2026-11-22',
           'best-seasonal-hobby-kits-worth-buying-uk', 'best-soundbars-worth-buying-uk-2026',
           'best-video-doorbells-worth-buying-uk-2026-daily-2026-11-23'],
    'us': ['best-electric-blankets-worth-buying-us-2026-daily-2026-11-23',
           'best-gaming-headsets-worth-buying-us',
           'best-non-slip-hangers-worth-buying-us-2026-daily-2026-11-22',
           'best-robot-vacuum-cleaners-worth-buying-us-2026-daily-2026-11-21',
           'best-soundbars-worth-buying-us-2026'],
}
for market, slugs in SLUGS.items():
    for slug in slugs:
        folder = 'articles' if market == 'uk' else 'articles-us'
        article = json.loads((Path(folder) / (slug + '.json')).read_text(encoding='utf-8'))
        generate_image(article, market, Path('assets/ai') / market / (slug + '.jpg'),
                       os.environ['CLOUDFLARE_ACCOUNT_ID'], os.environ['CLOUDFLARE_API_TOKEN'], force=True)
        print('Repaired', market, slug)
