"""Reviewed photo sources that survive automatic headline/date refreshes."""
import hashlib
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def configuration(market, slug):
    path = ROOT / 'assets/ai/curated-backgrounds.json'
    if not path.exists():
        return None
    config = json.loads(path.read_text(encoding='utf-8'))
    explicit = config.get(f'{market}:{slug}')
    if explicit:
        return explicit
    if re.search(r'air[- ]?fryers?', str(slug), re.I):
        return config.get('air-fryer-defaults', {}).get(market)
    if re.search(r'smart[- ]?watches?', str(slug), re.I):
        return config.get('smartwatch-defaults', {}).get(market)
    return None


def curated_background(article, market):
    record = configuration(market, article.get('slug', ''))
    if not record:
        return None
    base = (ROOT / 'assets/ai/backgrounds').resolve()
    path = (ROOT / record['path']).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise RuntimeError('Reviewed image source is missing or outside the background directory')
    if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
        raise RuntimeError('Reviewed image source changed; refusing automatic replacement')
    with Image.open(path) as photo:
        photo.verify()
    with Image.open(path) as photo:
        if photo.width < 900 or photo.height < 450:
            raise RuntimeError('Reviewed image source is too small')
    return path
