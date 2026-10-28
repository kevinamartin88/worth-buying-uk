"""Ensure the six editorial updates survive refreshes without changing offers."""
import copy
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from src.search_focus import FOCUS, START, REVISION
from src.search_guides import enhance_search_guide

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('market,slug', FOCUS)
def test_real_article_refresh_preserves_commercial_and_publication_evidence(market, slug):
    folder = 'articles' if market == 'uk' else 'articles-us'
    original = json.loads((ROOT / folder / (slug + '.json')).read_text(encoding='utf-8'))
    before = copy.deepcopy(original)
    updated = enhance_search_guide(original, market)
    assert original == before
    for field in original.keys() - {'title', 'content_html', '_seo'}:
        assert updated[field] == original[field], field
    assert updated['_seo']['last_checked_iso'] == original['_seo']['last_checked_iso']
    for pattern in [r'<img\b[^>]*>', r'<script\b[^>]*>.*?</script>',
                    r'<a\b[^>]*href="https://(?:www\.)?(?:ebay|amazon)[^"]*"[^>]*>.*?</a>',
                    r'<p><strong>Prices when checked:</strong>.*?</p>']:
        for fragment in re.findall(pattern, original['content_html'], re.S):
            assert fragment in updated['content_html'], fragment[:100]
    assert updated['content_html'].count(START) == 1
    assert FOCUS[(market, slug)]['intro'] in updated['content_html']
    assert updated['_seo']['search_focus_revision'] == REVISION
    assert 90 <= len(updated['_seo']['description']) <= 160
    from src.publication_quality import choose_description
    selected, issues = choose_description(updated, market)
    assert issues == []
    assert selected == updated['_seo']['description']
    assert enhance_search_guide(updated, market) == updated


@pytest.mark.parametrize('market,slug', FOCUS)
def test_daily_generation_keeps_advice_without_research_network_calls(monkeypatch, market, slug):
    import generate_daily_articles as daily

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 28, 12, tzinfo=tz)

        def strftime(self, fmt):
            return super().strftime(fmt.replace('%-d', '%d'))

    monkeypatch.setattr(daily, 'datetime', FixedDateTime)
    monkeypatch.setattr(daily, 'current_picks', lambda *args: [])
    monkeypatch.setattr(daily, 'related_guides', lambda **kwargs: [])
    topic = next(row for row in daily.TOPICS if row[0] == FOCUS[(market, slug)]['topic'])
    article = daily.build_article(topic, market, 2026, is_refresh=True)
    assert article['slug'] == slug
    assert article['content_html'].count(START) == 1
    assert article['title'] == FOCUS[(market, slug)]['title']
    assert article['_promotion']['is_refresh'] is True
    assert article['_generator']['live_ebay_picks'] is False


def test_other_markets_and_event_intents_keep_their_original_copy():
    from src.search_focus import enhance_search_focus
    base = {'slug': 'best-tvs-worth-buying-uk-2026', '_generator': {'topic': 'tvs'},
            'content_html': '<p>Existing event or unrelated copy</p>'}
    assert enhance_search_focus(base, 'us') is base
    for flags in [{'_event': {'type': 'prime'}},
                  {'_generator': {'topic': 'tvs', 'prime_amazon_only': True}},
                  {'_generator': {'topic': 'tvs', 'content_type': 'authority-support'}}]:
        article = {**base, **flags}
        assert enhance_search_focus(article, 'uk') is article
