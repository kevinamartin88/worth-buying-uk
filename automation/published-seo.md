# Published SEO and measurement

Both countries share this repository. Keep daily generator schedules unchanged.

The publishers preserve historical content fingerprints and repair only their
owned metadata block on otherwise unchanged/reconciled Blogger posts. The exact
generated `_seo.description` becomes the browser-rendered head description and
Open Graph description; it is never emitted as a meta tag inside the body.

Install `blogger-head-seo.xml` immediately after the theme's `all-head-content`
include. It provides a server-rendered title-based fallback when Blogger's native
Search Description is absent. The fallback is not the exact generated description.
Blogger API v3 does not expose the UI Search Description as a supported writable
post field. Do not claim a native-field write or rely on sitemap submission to
guarantee indexing.

Install `retailer-measurement.js` once in each theme inside a CDATA script. It
reuses the existing gtag and sends `wb_retailer_click` to UK G-KL9MHT5ZJ1 or USA
G-EEYCNV01MN. The shared listener guard prevents duplicate USA pilot listeners.
Mark this exact event as a GA4 key event in both properties. Receiving the event
must be checked in GA4; script presence alone is insufficient evidence.

The hub publisher retains legacy hubs and adds the six requested categories.
Motoring retains its existing permalink. It refreshes a bounded recommendation
selection and adds reciprocal links in an automation-owned footer, preserving
article copy and affiliate URLs. Homepage navigation should use the actual URLs
saved in `state/site_pages_*.json`. Homepage latest-post lists continue to discover
new daily articles automatically.

Verification: publishing safeguards, metadata idempotency/manual-copy preservation,
reciprocal links, all six hubs and regional listener routing. Check raw head tags
and browser-rendered head tags separately. Check both homepages and articles on
desktop/mobile; no theme CSS or article-card layout changes are required.
