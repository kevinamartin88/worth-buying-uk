from src.social_copy import clean_social_template


def test_affiliate_label_is_replaced_but_link_is_preserved():
    assert clean_social_template("Ad/Affiliate 🔗 {url}") == "Read the guide 🔗 {url}"
    assert clean_social_template("Affiliate 🔗 {url}") == "Read the guide 🔗 {url}"
