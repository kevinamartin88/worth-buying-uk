# Six existing search guides: 28 October 2026

Baseline: direct Google Search Console Web performance, 29 September–26 October
2026 (28-day UI window). The last two days can still be revised. Counts are small;
these are research candidates, not statistically proven title/CTR problems.

| Market | Article | Clicks | Impressions | Average position |
|---|---|---:|---:|---:|
| UK | TVs (mobile URL) | 1 | 20 | 10.7 |
| UK | Tablets | 0 | 19 | 22.8 |
| UK | Tyre inflators | 0 | 19 | 28.6 |
| USA | Cordless drills | 0 | 55 | 30.7 |
| USA | Pressure washers (mobile URL) | 0 | 49 | 39.4 |
| USA | Slow cookers | 0 | 29 | 22.9 |

These pages combine existing search exposure with a specific buying task. TV
position gives a closer ranking opportunity than the UK storage-organiser page
(22 impressions, position 44). USA pages are the highest-impression evergreen
articles without clicks. Mobile and clean URLs should be grouped in follow-up.

`src/search_focus.py` adds locally stored, sourced advice after the existing
enrichment. It changes six titles/descriptions, replaces generic advice/FAQs
where present, and adds practical comparisons and contextual links. Existing
pressure-washer and slow-cooker research stays intact. Ring feedback is attributed
to the exact RTC6000 and is not applied to an unidentified Ring listing. No
hands-on testing or invented owner comments are claimed.

The module has no network/API dependency. Slugs, published post IDs, price-check
dates, prices, product images, affiliate URLs and promotion tokens stay intact.
Daily scheduling, design and new-post selection are unchanged. Existing publisher
workflows update saved posts in place and refresh hub links.

Compare the same six URL groups after 28 settled days: impressions, clicks,
query relevance, position, GA4 engaged visits and retailer clicks. Separate owner
and automated visits where the evidence permits; do not promise a traffic uplift.
