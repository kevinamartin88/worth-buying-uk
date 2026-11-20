"""Offline publication backstop. Unsuitable offers become a buying guide, not a failed post."""
from __future__ import annotations

import copy
import html
import re
from html.parser import HTMLParser
from urllib.parse import quote_plus, urlsplit

from src.product_relevance import product_mismatch_reason


class RecommendationTitles(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titles = []
        self.heading = []
        self.capturing = False
        self.current = ''
        self.has_retailer = False

    def finish(self):
        if self.current and self.has_retailer:
            self.titles.append(self.current)
        self.current, self.has_retailer = '', False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('h2', 'h3'):
            self.finish()
            self.heading, self.capturing = [], True
        if attrs.get('data-wb-product-title'):
            self.titles.append(attrs['data-wb-product-title'])
        if tag == 'a':
            try:
                host = (urlsplit(attrs.get('href', '')).hostname or '').lower()
            except ValueError:
                host = ''
            if 'sponsored' in attrs.get('rel', '').split() or any(
                host == domain or host.endswith('.' + domain)
                for domain in ('amazon.com', 'amazon.co.uk', 'ebay.com', 'ebay.co.uk', 'linksynergy.com')
            ):
                self.has_retailer = True

    def handle_endtag(self, tag):
        if tag in ('h2', 'h3') and self.capturing:
            self.current = ' '.join(''.join(self.heading).split())
            self.capturing = False

    def handle_data(self, data):
        if self.capturing:
            self.heading.append(data)


def article_query(article):
    generator = article.get('_generator') or {}
    return str(generator.get('query') or generator.get('topic')
               or (article.get('_seo') or {}).get('primary_keyword')
               or article.get('title') or 'products').replace('-', ' ')


def buying_guide_fallback(query, market, retailer_only=False):
    subject = html.escape(query)
    region = 'UK' if market == 'uk' else 'USA'
    content = (
        f'<p><strong>Compare {subject} for your needs in the {region}.</strong> '
        'Start with the exact product and the complete equipment you will receive, '
        'then compare the current delivered price and return terms.</p>'
        '<h2>Checks that make the comparison useful</h2><ul>'
        '<li><strong>Identify the main product.</strong> A compatible cable, remote, filter, '
        'charger or attachment may name the appliance it works with. Confirm what the offer actually supplies.</li>'
        '<li><strong>Match the model and generation.</strong> Similar names do not guarantee '
        'the same connections, capacity, compatibility or supported services.</li>'
        '<li><strong>Price a usable kit.</strong> Check the supplied equipment and any essential '
        'extras you would need to buy separately. A bare tool can suit someone who already owns its battery.</li>'
        '<li><strong>Check the regional version.</strong> Confirm the plug, voltage, language, '
        'warranty coverage and delivery address are suitable for your market.</li>'
        '<li><strong>Compare the offer terms.</strong> Include delivery, condition, seller, '
        'warranty and return costs. Seller feedback describes transactions, not product performance.</li>'
        '</ul><h2>Choose using the details that matter to you</h2>'
        '<p>Write down the space, compatibility and everyday tasks the purchase must suit. '
        'Compare equivalent models and complete packages against that list. Check any '
        'product-specific reviews for the exact generation, and separate measured results '
        'from a reviewer’s preference or a seller’s claim. A discount is useful only if '
        'the product, condition and total price make sense for your needs.</p>'
    )
    if not retailer_only:
        amazon = 'www.amazon.co.uk' if market == 'uk' else 'www.amazon.com'
        ebay = 'www.ebay.co.uk' if market == 'uk' else 'www.ebay.com'
        amazon_tag = 'worthbuyin008-21' if market == 'uk' else 'worthbuyingus-20'
        campaign = '5339209132' if market == 'uk' else '5339209205'
        route = '710-53481-19255-0' if market == 'uk' else '711-53200-19255-0'
        content += (
            '<h2>Compare current retailer options</h2><p>These links open searches, '
            'rather than a verified offer for a specific product. Check the selected '
            'model, contents, price and availability on the retailer page.</p>'
            f'<p><a href="https://{amazon}/s?k={quote_plus(query)}&amp;tag={amazon_tag}" rel="sponsored nofollow">'
            f'Search Amazon {region}</a> · '
            f'<a href="https://{ebay}/sch/i.html?_nkw={quote_plus(query)}&amp;mkcid=1&amp;mkrid={route}&amp;campid={campaign}&amp;toolid=20014&amp;mkevt=1" rel="sponsored nofollow">'
            f'Search eBay {region}</a></p>'
            '<p>Affiliate links may earn Worth Buying a commission at no extra cost to you.</p>'
        )
    else:
        content += '<p>Use the approved retailer’s current catalogue to check the exact product and offer terms before ordering.</p>'
    return content


def prepare_article_products(article, market):
    """Keep sound articles unchanged; publish useful search/advice copy if a bad pick escaped.

    No network, optional dependency, missing-evidence exception or minimum-pick
    requirement is introduced. The source generators remain the primary filters.
    """
    query = article_query(article)
    parser = RecommendationTitles()
    rejected = []
    try:
        parser.feed(str(article.get('content_html') or ''))
        parser.finish()
    except Exception:
        # This optional safeguard must not turn an HTML inspection problem into
        # a failed publishing day. The replacement contains no specific offers.
        rejected.append({'title': 'Unverified product markup', 'reason': 'Product sections could not be safely checked'})
    for heading in dict.fromkeys(parser.titles):
        title = re.sub(r'^\d+[.)]\s*', '', heading).strip()
        if re.match(r'^(?:how|what|why|should|is |are |check|compare|choose|read|avoid|best.value options|higher.spec options|refurbished and open.box options|popular current listings)', title, re.I):
            continue
        reason = product_mismatch_reason(title, query, market)
        if reason:
            rejected.append({'title': title, 'reason': reason})
    if not rejected:
        return article
    result = copy.deepcopy(article)
    region = 'UK' if market == 'uk' else 'USA'
    title = f'{query.title()}: Buying Checks and Retailer Comparisons ({region})'
    result['content_html'] = buying_guide_fallback(query, market, (article.get('_generator') or {}).get('channel') == 'rakuten')
    result['title'] = title
    for field in ('pinterest_title', 'x_image_title'):
        result[field] = title
    for field in ('pinterest_subtitle', 'x_subtitle'):
        result[field] = 'Compare the exact model, complete package and retailer terms'
    result.pop('_research', None)
    result['x_text'] = f'{title}\n\nCompare the exact model, complete package and current retailer terms.\n{{url}}'
    result['youtube_short_points'] = ['Identify the complete product and model.', 'Check regional compatibility and included equipment.', 'Compare delivered price and return terms.']
    result.setdefault('_seo', {})['description'] = f'{region} {query} buying checks: compare the exact model, complete package, regional version, delivered price and returns.'[:155]
    generator = result.setdefault('_generator', {})
    generator.update(live_ebay_picks=False, pick_count=0)
    if 'offer_count' in generator:
        generator['offer_count'] = 0
    if result.get('_monetisation'):
        result['_monetisation']['retailer_cta_count'] = 0 if generator.get('channel') == 'rakuten' else 2
    result['_product_checks'] = {'version': 1, 'outcome': 'buying-guide-fallback', 'rejected': rejected}
    print(f"[product-check-fallback] {market.upper()} {article.get('slug', '')}: {len(rejected)} unsuitable recommendations replaced with buying guidance")
    return result
