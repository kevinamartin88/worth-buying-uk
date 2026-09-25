from __future__ import annotations

from src.search_console import score_topic_query


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


def test_relevant_search_console_query_scores_strongly():
    row = {
        "query": "best dash cams uk",
        "impressions": 250,
        "clicks": 4,
        "ctr": 0.016,
        "position": 11.5,
    }
    assert score_topic_query(DASH_CAMS, row) >= 45


def test_unrelated_search_console_query_does_not_score():
    row = {
        "query": "football results",
        "impressions": 5000,
        "clicks": 100,
        "ctr": 0.02,
        "position": 8,
    }
    assert score_topic_query(DASH_CAMS, row) == 0


def test_tiny_impression_sample_cannot_steer_topic():
    row = {
        "query": "cordless vacuum cleaner",
        "impressions": 3,
        "clicks": 1,
        "ctr": 0.333,
        "position": 2,
    }
    assert score_topic_query(VACUUMS, row) == 0


def test_mid_ranking_high_impression_query_is_an_opportunity():
    weak = {
        "query": "dash cam",
        "impressions": 20,
        "clicks": 1,
        "ctr": 0.05,
        "position": 3,
    }
    opportunity = {
        "query": "dash cam",
        "impressions": 400,
        "clicks": 4,
        "ctr": 0.01,
        "position": 12,
    }
    assert score_topic_query(DASH_CAMS, opportunity) > score_topic_query(DASH_CAMS, weak)
