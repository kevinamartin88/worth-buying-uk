"""Replace only the heroes on the existing USA smartwatch post."""
import argparse
import json
from pathlib import Path

from src.article_images import backfill_hero_if_missing, verify_required_hero
from src.blogger import BloggerClient
from publish_articles import UK_BLOG_HOSTS
from publish_articles_us import USA_BLOG_HOSTS

ROOT = Path(__file__).resolve().parent


def repair(market, blogger):
    slug = 'best-smartwatches-worth-buying-us'
    if market != 'us':
        raise ValueError('This repair is USA only')
    directory = 'articles' if market == 'uk' else 'articles-us'
    article = json.loads((ROOT / directory / f'{slug}.json').read_text(encoding='utf-8'))
    blogger.resolve_blog(UK_BLOG_HOSTS if market == 'uk' else USA_BLOG_HOSTS, f'Worth Buying {market.upper()}')
    existing = blogger.find_post_by_exact_title(article['title'])
    if not existing:
        raise RuntimeError('Original smartwatch post not found; refusing to create a duplicate')
    post_id = str(existing['id'])
    before = blogger.get_post_or_none(post_id)
    if not before or not before.get('url') or not isinstance(before.get('content'), str):
        raise RuntimeError('Original smartwatch post could not be read')
    content, hero, changed = backfill_hero_if_missing(before['content'], market, slug, article['title'])
    if changed:
        blogger.update_post_content(post_id, content)
    stored = blogger.get_post_or_none(post_id)
    if not stored or stored.get('url') != before['url'] or stored.get('content') != content:
        raise RuntimeError('Air-fryer image update was not retained at the original permalink')
    verify_required_hero(stored['content'], hero, article['title'])
    print(f"[smartwatch-hero-verified] {market}: {stored['url']} -> {hero}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--market', choices=('us',), required=True)
    repair(parser.parse_args().market, BloggerClient.from_env())
