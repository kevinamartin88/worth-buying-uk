# WorthBuying cloud editorial

The `Cloud bespoke guides and traffic improvement` GitHub Actions workflow uses
GitHub-hosted Linux runners and existing eBay, Blogger and Buffer integrations.
No open desktop or paid language-model API is required.

## Schedules and scope

- Wednesday, from 10:00 Europe/London: at most one bespoke source article per
  market per ISO week. A later scheduled opportunity can recover a failed market.
- Tuesday/Thursday, from 11:00 Europe/London: a bounded promotion experiment from
  5 to 19 October 2026. At most one experiment post per market per date, and each
  selected guide is promoted only once in this experiment.
- Six existing guides (air fryers, air purifiers and robot vacuums on each site)
  receive an additional practical comparison section without replacing their
  URLs, product descriptions, images or prices. Existing publishers handle the
  changes and verify saved Blogger content.
- Four curated audience briefs start with student air fryers, student homeware,
  easy-grip cutlery and small-bedroom air purifiers. The queue cycles back to
  refresh those stable pages after four successful editions; it does not invent
  unlimited fresh topics or claim to carry out new independent product tests.
  Add researched briefs to `automation/bespoke_briefs.json` to expand the queue.

Current stock, item details and product photographs are fetched from the regional
eBay API. Every product group must produce a relevant listing with a usable photo.
New-only adaptive cutlery also needs relevant item-specific evidence. Insufficient
matches, missing images and expired editorial evidence create a blocked draft,
not a generic replacement article. Existing product-photo checks are retained.
Hero images are composed from a real product photo and the actual regional logo.

## Records and failure handling

`state/cloud_editorial.json` records generation, source edits, promotion outcomes
and Google Search Console snapshots. Generated is not the same as published.
The separate publisher's matching source SHA is required before promotion.
Accepted by Buffer is not necessarily delivered; provider status is retained.

Before a Buffer call, promotion intent is committed and pushed. An ambiguous
response remains marked unknown and is never automatically replayed. This favours
an occasional missed promotion over duplicate external posts.

Run summaries and 14-day artifacts retain blocked drafts and execution results.
The account's GitHub Actions notification settings control email alerts. No paid
service, account upgrade or new credentials are created by this workflow.

Search Console snapshots measure Google web-search clicks and impressions only.
Cloudflare site visits, affiliate outbound clicks and confirmed sales are not
inferred from those numbers and are not yet joined into a single cloud report.

## Remaining desktop dependencies

- The existing EmailOctopus newsletter composition/scheduling task still uses an
  authenticated desktop browser. Emails already scheduled in EmailOctopus send
  in the cloud, but future weekly preparation is not yet server-side.
- Search Console manual Request indexing is a browser operation, not the URL
  Inspection API. Accepted sitemaps support normal discovery without a desktop;
  these workflows do not claim to automate manual indexing requests.

The two desktop bespoke/growth heartbeat schedules should be paused after the
cloud workflow is deployed and its initial run verified, to avoid duplicates.
