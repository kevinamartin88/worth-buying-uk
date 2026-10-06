"""Refresh selling prices in existing CFS retailer roundups; keep their URLs."""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from src.article_copy import clean_article_disclosures
from src.article_images import add_required_hero, verify_required_hero
from src.blogger import BloggerClient
from src.cfs_prices import cfs_destination, checked_cfs_price
from src.rakuten import RakutenClient, RakutenProduct
from publish_articles import UK_BLOG_HOSTS

ROOT = Path(__file__).resolve().parent
BLOCK = re.compile(r'<h3>(.*?)</h3>.*?(?=<h[23]\b|$)', re.S)
PRICE = re.compile(r'(<strong>Price when checked:</strong>\s*)(?:£[\d,.]+|Check the current retailer price)(\.)')
CHECK_NOTE = re.compile(r'<p data-wb-cfs-price-check="true">.*?</p>\s*', re.S)


def refresh_content(content, client, now):
    count, verified = 0, 0

    def update(match):
        nonlocal count, verified
        block = match.group(0)
        urls = [html.unescape(value) for value in re.findall(r'href="([^"]+)"', block)]
        tracking = next((url for url in urls if cfs_destination(url)), '')
        if not tracking or not PRICE.search(block):
            return block
        count += 1
        name = html.unescape(re.sub(r'<[^>]+>', '', match.group(1)))
        name = re.sub(r'^\d+\.\s*', '', name)
        product = RakutenProduct(name, 'Choice Furniture Superstore', tracking, currency='GBP')
        ok, reason, final_url = client.validate_product_destination(product)
        price = checked_cfs_price(client, product) if ok else None
        verified += bool(price)
        current = f'£{price}' if price else 'Check the current retailer price'
        print(f"[cfs-price] {name}: {current}" + (f" ({reason})" if not ok else ''))
        return PRICE.sub(lambda part: part[1] + current + part[2], block, count=1)

    result = BLOCK.sub(update, CHECK_NOTE.sub('', content))
    if not count:
        return content, 0, 0
    note = (
        '<p data-wb-cfs-price-check="true"><strong>CFS selling prices checked:</strong> '
        f'{now:%d %B %Y %H:%M} UTC. Quoted prices are the current product-page selling prices, '
        'including displayed reductions, rather than feed reference prices. '
        'Where a current price could not be verified, check the retailer page. '
        'Delivery charges and optional extras may apply.</p>\n'
    )
    position = result.find('<h2>')
    result = result[:position] + note + result[position:] if position >= 0 else note + result
    return result, count, verified


def publish_existing(article, blogger):
    existing = blogger.find_post_by_exact_title(article['title'])
    if not existing:
        raise RuntimeError(f"Existing CFS post not found: {article['title']}; no duplicate created")
    post_id = str(existing['id'])
    before = blogger.get_post_or_none(post_id)
    if not before or not before.get('url'):
        raise RuntimeError('Existing CFS post could not be read')
    content, hero = add_required_hero(clean_article_disclosures(article['content_html']), 'uk', article['slug'], article['title'])
    blogger.update_post_content(post_id, content)
    stored = blogger.get_post_or_none(post_id)
    if not stored or stored.get('url') != before['url'] or stored.get('content') != content:
        raise RuntimeError('CFS price update was not retained with the original permalink')
    verify_required_hero(stored['content'], hero, article['title'])
    print(f"[cfs-published] {stored['url']}")


def main():
    client = RakutenClient.for_market('uk')
    if client is None:
        raise RuntimeError('UK retailer credentials are required')
    blogger = BloggerClient.from_env()
    blogger.resolve_blog(UK_BLOG_HOSTS, 'Worth Buying UK')
    now = datetime.now(timezone.utc)
    article_count = offer_count = verified_count = 0
    for path in sorted((ROOT / 'articles').glob('*.json')):
        article = json.loads(path.read_text(encoding='utf-8'))
        if article.get('_generator', {}).get('channel') != 'rakuten':
            continue
        content, count, verified = refresh_content(article['content_html'], client, now)
        if not count:
            continue
        article['content_html'] = content
        article['source_sha'] = f"{now.isoformat()}-{article['slug']}-cfs-selling-prices-v1"
        article['_generator']['cfs_prices_checked_at'] = now.isoformat()
        publish_existing(article, blogger)
        path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        article_count += 1
        offer_count += count
        verified_count += verified
    print(f'[cfs-refreshed] {article_count} articles; {verified_count}/{offer_count} current selling prices verified')


if __name__ == '__main__':
    main()
