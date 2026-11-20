# Product checks and uninterrupted daily publishing

Both markets use the same offline role checks in `src/product_relevance.py`.
They detect the known accessory, product-type, regional-plug and extreme-capacity
mismatches documented in the November 2026 audit. They do not establish every
manufacturer specification, current stock position or seller claim.

## Coverage

- Daily guides and weekly supporting guides: shared marketplace selection and
  final article check after optional researched-guide preservation.
- Bespoke weekly guides: shared current-pick lookup and detailed listing checks.
- Amazon event guides: shared offer checks with the actual UK/USA market; the
  existing Amazon-only search fallback remains available.
- Approved-retailer guides: shared product-role filtering before offer selection;
  the separate stream still tries another eligible topic when a feed is limited.
- Weekly eBay deals: shared checks on discovery and every refreshed item, using
  the original topic query. An empty valid-deal set renders normally.
- Older niche publisher: shared checks before scoring; no qualifying picks use
  buying guidance with regional tracked retailer searches.
- Monthly price reports: historical mismatches are removed before statistics
  and price-mover selection. Existing minimum-evidence rules remain intact.
- UK/USA Blogger publishers and the existing email/manual fallback route: the
  same final content backstop runs before metadata and tracking are added.
- Post-publication verification uses the same checked article, so it cannot
  restore a superseded description from an unsuitable source product list.

## Fallback policy

Selection filters remove unsuitable offers first. The daily generator retains
its existing guide/search fallback when fewer than three qualifying picks remain.
The final content backstop replaces a product list containing a known mismatch
with practical buying guidance and clearly labelled retailer searches. It does
not turn a rejected offer or optional HTML-inspection error into a failed day,
invent a replacement product, price, rating or customer review, or change a
publish-mode article to a draft. Rakuten-only pages do not gain Amazon/eBay links.

Existing article slugs, labels and promotion tokens are retained. Sound article
objects are returned unchanged, preserving existing content fingerprints. No
publishing schedules, credentials, API limits or workflow definitions change.
The fallback is an internal product safeguard, not a guarantee against unrelated
authentication, required-image or service failures.

Tests cover rejected offers in both markets, legitimate complete products and
bundles, the existing article corpus, malformed optional markup, tracked search
fallbacks, actual publisher completion and duplicate prevention on reruns.
