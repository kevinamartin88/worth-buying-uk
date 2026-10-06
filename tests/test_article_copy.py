from src.article_copy import clean_article_disclosures


def test_disclosure_is_visible_but_does_not_lead_article():
    content = (
        '<p>Useful buyer-first introduction.</p>'
        '<p><strong>Affiliate disclosure:</strong> We earn commission.</p>'
        '<h2>Current picks worth comparing</h2><p>Products.</p>'
    )
    cleaned = clean_article_disclosures(content)
    assert cleaned.startswith("<p>Useful buyer-first introduction.</p>")
    assert not cleaned.startswith('<p class="wb-affiliate-disclosure">')
    assert cleaned.count("Affiliate links:") == 1
    assert cleaned.index("Useful buyer-first introduction") < cleaned.index("Affiliate links:")
    assert cleaned.index("Affiliate links:") < cleaned.index("Current picks worth comparing")
    assert clean_article_disclosures(cleaned) == cleaned


def test_usa_buying_cards_get_disclosure_after_intro():
    content = (
        '<div><p>Buyer first.</p>'
        '<section class="wb-usa-buying-cards"><a rel="sponsored nofollow" href="https://example.com">Buy</a></section>'
        '</div>'
    )
    cleaned = clean_article_disclosures(content)
    assert cleaned.index("Buyer first.") < cleaned.index("Affiliate links:")
    assert cleaned.index("Affiliate links:") < cleaned.index("wb-usa-buying-cards")


def test_editorial_and_retailer_links_are_preserved():
    content = (
        "<p>Recommendations are independent of affiliate commission rates.</p>"
        '<h2>Options</h2>'
        '<p><a rel="sponsored nofollow" href="https://example.com">Check price</a></p>'
    )
    cleaned = clean_article_disclosures(content)
    assert "Recommendations are independent" in cleaned
    assert 'href="https://example.com"' in cleaned
    assert cleaned.startswith("<p>Recommendations are independent")
