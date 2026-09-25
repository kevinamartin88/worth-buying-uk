from __future__ import annotations

import unittest

from src.google_trends import (
    parse_traffic,
    score_topic_against_trend,
    trend_keyword_for_title,
)


DASH_CAMS = (
    "dash-cams",
    "Dash Cams",
    "dash cam",
    450,
    500,
    "Motoring",
    "DASH CAM BUYING GUIDE",
)

VACUUMS = (
    "cordless-vacuums",
    "Cordless Vacuum Cleaners",
    "cordless vacuum cleaner",
    600,
    700,
    "Home & Kitchen",
    "VACUUM BUYING GUIDE",
)

APPLE_WATCHES = (
    "apple-watches",
    "Apple Watches",
    "Apple Watch",
    900,
    1000,
    "Tech",
    "APPLE WATCH BUYING GUIDE",
)


class GoogleTrendsTests(unittest.TestCase):
    def test_parse_traffic(self):
        self.assertEqual(parse_traffic("10K+"), 10_000)
        self.assertEqual(parse_traffic("2.5M+"), 2_500_000)
        self.assertEqual(parse_traffic(""), 0)

    def test_relevant_generic_query_scores(self):
        signal = {"query": "dash cam", "traffic": 100_000}
        self.assertGreater(score_topic_against_trend(DASH_CAMS, signal), 35)

    def test_unrelated_query_does_not_score(self):
        signal = {"query": "football results", "traffic": 1_000_000}
        self.assertEqual(score_topic_against_trend(DASH_CAMS, signal), 0)

    def test_generic_product_wording_can_influence_title(self):
        signal = {"query": "dash cam", "traffic": 100_000, "score": 70}
        self.assertEqual(trend_keyword_for_title(DASH_CAMS, signal), "Dash Cam")

    def test_search_style_wrappers_are_removed_from_title_phrase(self):
        signal = {"query": "best dash cam uk 2026", "traffic": 100_000, "score": 70}
        self.assertEqual(trend_keyword_for_title(DASH_CAMS, signal), "Dash Cam")

    def test_brand_specific_vacuum_query_cannot_rewrite_generic_title(self):
        signal = {"query": "Shark cordless vacuum", "traffic": 100_000, "score": 70}
        self.assertIsNone(trend_keyword_for_title(VACUUMS, signal))

    def test_model_number_cannot_rewrite_title(self):
        signal = {"query": "Apple Watch Series 12", "traffic": 100_000, "score": 70}
        self.assertIsNone(trend_keyword_for_title(APPLE_WATCHES, signal))


if __name__ == "__main__":
    unittest.main()
