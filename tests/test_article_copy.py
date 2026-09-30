from src.article_copy import clean_article_disclosures


def test_repeated_article_disclosures_are_removed_but_product_copy_remains():
    content = (
        "<p>Useful buying advice.</p>"
        "<p><em>Some links in this article are affiliate links. We may earn a commission.</em></p>"
        "<p><strong>Affiliate disclosure:</strong> We may receive commission from purchases.</p>"
        '<p><a rel="sponsored nofollow" href="https://example.com">Check price</a></p>'
    )

    cleaned = clean_article_disclosures(content)

    assert "affiliate" not in cleaned.casefold()
    assert "commission" not in cleaned.casefold()
    assert "Useful buying advice" in cleaned
    assert 'rel="sponsored nofollow"' in cleaned
