from src.article_copy import clean_article_disclosures


def test_disclosure_is_visible_and_idempotent():
    content = '<p>Advice.</p><p><strong>Affiliate disclosure:</strong> We earn commission.</p>'
    cleaned = clean_article_disclosures(content)
    assert cleaned.startswith('<p class="wb-affiliate-disclosure">')
    assert cleaned.count("Affiliate disclosure:") == 1
    assert clean_article_disclosures(cleaned) == cleaned
    assert "<p>Advice.</p>" in cleaned


def test_editorial_and_retailer_links_are_preserved():
    content = (
        "<p>Recommendations are independent of affiliate commission rates.</p>"
        '<p><a rel="sponsored nofollow" href="https://example.com">Check price</a></p>'
    )
    cleaned = clean_article_disclosures(content)
    assert content in cleaned
