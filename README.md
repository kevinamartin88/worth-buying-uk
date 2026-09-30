# Zero-Cost Affiliate Engine

## Post-publish SEO checks

The UK and USA Blogger publishing workflows now run `post_publish_seo.py` after a
new or changed article gets a live URL. The manual Blogger reconciliation workflow
runs the same check when it discovers a newly published article. The check verifies
that the public page responds, reports its canonical URL and JSON-LD validity,
looks for its URL in Blogger's `sitemap.xml`, and (when the existing read-only
Search Console secrets are present) reports Google's latest URL Inspection status.
The daily article generator already adds relevant links to published guides, and
the publisher workflows already send live URLs to X and Bluesky when configured.

Sitemap submission is optional. To enable it, run
`python setup_search_console_auth.py --client-secrets client_secret.json --write-sitemaps`
using an account with access to the UK and USA Search Console properties, then
save the resulting `GSC_WRITE_REFRESH_TOKEN` as a GitHub Actions secret. The
also save `GSC_WRITE_CLIENT_ID` and `GSC_WRITE_CLIENT_SECRET` from that same
helper run. Keep the existing `GSC_CLIENT_ID`, `GSC_CLIENT_SECRET`, and
`GSC_REFRESH_TOKEN` for read-only inspection.
`GSC_UK_SITE_URL` and `GSC_US_SITE_URL` remain optional property overrides.

The checks are advisory and do not block Blogger publication, X, Bluesky, or state
saving. Search Console reports the version Google knows about, so a newly
published page may show as undiscovered until Google crawls it. Sitemap submission
does not guarantee indexing. These buying guides are not eligible for Google's
restricted Indexing API; the workflow uses standard sitemaps instead.

A zero-running-cost MVP that:

1. Searches eBay through the official Browse API and can enrich results with `getItem`.
2. Keeps eBay's returned item order (it filters, but does not re-sort).
3. Adds eBay Partner Network affiliate attribution using `affiliateCampaignId`
   and a niche-specific `affiliateReferenceId` / sub-ID.
4. Builds useful evergreen "current picks" pages.
5. Creates or refreshes one Blogger post per niche.
6. Stores lightweight price observations and publication state in the GitHub repository.
7. Runs automatically on GitHub Actions.

The project deliberately does **not** use an AI API, so there is no per-run AI charge.

## What it is not

This does not guarantee income. Revenue requires:
- acceptance into the eBay Partner Network;
- production access to the eBay Buy/Browse API;
- people actually finding/clicking your content;
- qualifying transactions.

The code can be tested in eBay Sandbox before production approval.

## Safety / account security

Never commit passwords, OAuth secrets, client secrets, refresh tokens or API keys.
Store them in GitHub **Actions secrets**.

## Accounts you need

- eBay account
- eBay Developers Program account
- eBay Partner Network (EPN) account
- Blogger / Google account
- GitHub account

## Project structure

```text
.
├── .github/workflows/publish.yml
├── config.yml
├── main.py
├── requirements.txt
├── setup_blogger_auth.py
├── src/
│   ├── blogger.py
│   ├── ebay.py
│   ├── render.py
│   ├── scoring.py
│   └── state.py
├── state/
│   ├── price_history.json
│   └── published.json
├── sample_data/
│   └── item_summaries.json
└── tests/
    └── test_scoring.py
```

## 1. Test it for free without any accounts

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the built-in mock data:

```bash
MOCK_EBAY=1 DRY_RUN=1 python main.py
```

Open the generated files in `out/`.

## 2. Create a Blogger blog

Create a free Blogger blog and choose a simple, honest niche/deals name.

Do not create lots of near-duplicate blogs. This project is designed to maintain
one useful site with evergreen pages.

## 3. Create Google Blogger OAuth credentials

In Google Cloud Console:

1. Create a project.
2. Enable **Blogger API v3**.
3. Configure the OAuth consent screen.
4. Create an OAuth Client ID for a **Desktop app**.
5. Download the client secrets JSON as `client_secret.json`.
6. Do not commit that file.

Run:

```bash
python setup_blogger_auth.py --client-secrets client_secret.json
```

A browser window opens. Sign into the Google account that owns the Blogger blog
and approve Blogger access.

The helper prints:
- `BLOGGER_CLIENT_ID`
- `BLOGGER_CLIENT_SECRET`
- `BLOGGER_REFRESH_TOKEN`
- your available Blogger blog IDs

Copy those values into GitHub Actions secrets.

## 4. Connect Google Search Console for first-party SEO signals

The daily article creator can combine Google Trends with your own Search Console
query data. Search Console is read-only in this workflow and is used only to
identify product topics already earning impressions/clicks for WorthBuying.

In the same Google Cloud project (or another project you control):

1. Enable **Google Search Console API**.
2. Create or reuse an OAuth Client ID for a **Desktop app**.
3. Download the client secrets JSON as `client_secret.json`.
4. Do not commit that file.

Run:

```bash
python setup_search_console_auth.py --client-secrets client_secret.json
```

Sign in with the Google account that has access to the Worth Buying UK and USA
Search Console properties. The helper requests only
`https://www.googleapis.com/auth/webmasters.readonly`.

Save the printed values as GitHub Actions secrets:

```text
GSC_CLIENT_ID
GSC_CLIENT_SECRET
GSC_REFRESH_TOKEN
```

The automation normally auto-detects verified properties containing
`worthbuyinguk.co.uk` and `worthbuyingusa.com`. If your Search Console property
uses a different exact property URL, optionally add:

```text
GSC_UK_SITE_URL
GSC_US_SITE_URL
```

Examples include `sc-domain:worthbuyinguk.co.uk` or an exact URL-prefix property.

The topic selector uses Search Console queries from the recent 28-day window with
a small reporting lag. When relevant first-party data exists, Search Console is
weighted more heavily than Google Trends. If Search Console is unavailable or has
too little data, the automation falls back safely to Trends and the existing
curated topic rotation.

## 5. eBay setup

Create eBay Developer credentials.

For initial testing use Sandbox credentials and:

```text
EBAY_ENV=sandbox
```

For earning affiliate commission, join EPN and apply for production access to the
eBay Buy APIs. Once approved, use the **Production App ID (Client ID)** and
**Production Cert ID (Client Secret)**. The client-credentials token is held only
in memory and is never written to repository files or workflow logs.

```text
EBAY_ENV=production
```

Your EPN campaign ID is the 10-digit campaign ID supplied by EPN.

## 6. GitHub Actions secrets

Create a GitHub repository and upload this project.

In:

**Settings → Secrets and variables → Actions → New repository secret**

add:

```text
EBAY_CLIENT_ID
EBAY_CLIENT_SECRET
EPN_CAMPAIGN_ID
EPN_US_CAMPAIGN_ID
AMAZON_CREATORS_CLIENT_ID
AMAZON_CREATORS_CLIENT_SECRET
AMAZON_CREATORS_CREDENTIAL_VERSION
BLOGGER_CLIENT_ID
BLOGGER_CLIENT_SECRET
BLOGGER_REFRESH_TOKEN
BLOGGER_BLOG_ID
RAKUTEN_UK_CLIENT_ID
RAKUTEN_UK_CLIENT_SECRET
RAKUTEN_UK_ACCOUNT_ID
RAKUTEN_US_CLIENT_ID
RAKUTEN_US_CLIENT_SECRET
RAKUTEN_US_ACCOUNT_ID
```

These are the application credentials and account IDs from Rakuten Advertising's
Developer Portal for the Worth Buying UK and Worth Buying USA publisher accounts.
The separate Rakuten article creator exchanges each three-part set for a short-lived
access token and uses it only for that account's Product Search. Credentials and
access tokens are never written to files or logs, and the accounts are never crossed.

Rakuten runs as a separate daily publishing stream at 08:15 UTC. It requires at
least three relevant, region-appropriate products from approved advertiser feeds
before creating a standalone retailer roundup. If credentials are absent, the API
is unavailable, or the feed is too limited, the Rakuten article is skipped. The
normal Amazon/eBay article continues unchanged and never receives a Rakuten link.

Worth Buying USA currently gives approved Sharper Image products priority when
they are relevant to the selected topic. Other approved US retailers remain valid
fallbacks, so the autonomous stream does not depend on a single advertiser feed.

New Rakuten roundups are saved in the existing regional article directories so the
established Blogger, X, Bluesky and Pinterest publishing chain can process them.
Recent-topic history prevents near-duplicate roundups, while all outbound Rakuten
links remain the tracking URLs returned by Product Search and are marked
`sponsored nofollow`.

### Weekly Discount Codes pages

The **Weekly discount codes pages** workflow runs every Friday at 06:30 UTC and
can also be started manually. It uses the existing regional Rakuten, eBay and
Blogger secrets listed above, so no additional secret is required. It combines
the official Rakuten Coupon Feed for approved advertisers (network 3 for the UK
and network 1 for the USA) with discounted eBay listings returned by the existing
production Browse API and EPN tracking setup.

Each run creates or refreshes one permanent Blogger Page titled **Discount Codes**
on each regional site when Blogger permits Pages API writes. Expired and not-yet-live
offers are removed, genuine coupon codes are listed before no-code promotions,
and no retailer can occupy more than three of the 30 available positions. The
outbound URLs are validated regional Rakuten or eBay tracking links and retain
`sponsored nofollow`. General voucher websites are not scraped or treated as
confirmation; a code must come from an authorised feed or a retailer-owned source.
If the feed is successfully checked but contains no current approved offers, the
page shows a clear empty-state message instead of leaving expired codes visible.
API or credential failures stop that regional job and leave the existing page
untouched.

If Google permits normal post publishing but rejects Blogger Pages API writes for
an otherwise verified admin account, the workflow falls back to one stable post
titled **Discount Codes** and updates that same post every week. It does not create
a new weekly post. This preserves the permanent navigation target while avoiding
duplicate content.

After saving the secret, open **Actions → Test Rakuten production API → Run
workflow**. The test searches both accounts for `air fryer` and reports only
whether a fresh access token worked and a valid tracked product in the correct
currency was returned. It prints only the advertiser name—not credentials,
access tokens, link URLs, SKUs or the raw API response.

The eBay values are:

- `EBAY_CLIENT_ID`: the eBay production App ID (Client ID).
- `EBAY_CLIENT_SECRET`: the matching production Cert ID (Client Secret).
- `EPN_CAMPAIGN_ID`: the UK EPN campaign ID used to request UK affiliate URLs.
- `EPN_US_CAMPAIGN_ID`: the USA EPN campaign ID used to request USA affiliate URLs.

The optional Amazon Creators API values are:

- `AMAZON_CREATORS_CLIENT_ID`: the Credential ID created in Associates Central.
- `AMAZON_CREATORS_CLIENT_SECRET`: the matching credential secret.
- `AMAZON_CREATORS_CREDENTIAL_VERSION`: `3.1`, `3.2` or `3.3` as shown with the credential.

When these three secrets are present, daily guides request Amazon's current featured-offer
price and show it beside the eBay price only when the exact model number also matches the
Amazon result. If access is unavailable or the model cannot be verified, generation continues
with the eBay price and the normal Amazon search link. Credentials and tokens are never logged.

The UK live test requires the first three. The US campaign secret is required only
when US live-listing generation is enabled. The same production eBay application
credentials can be used for both marketplaces. For Sandbox tests you can leave the
campaign IDs blank.

Add them at **Repository Settings → Secrets and variables → Actions → New
repository secret**. Do not add them as repository variables, workflow inputs, or
plain text in a YAML file.

### Safe production API check

After the UK secrets are present, open **Actions → Test eBay production API → Run
workflow**. This manual-only workflow runs `scripts/test_ebay_live.py` and verifies:

1. the OAuth client-credentials flow;
2. a live `EBAY_GB` search for `air fryers`; and
3. a `getItem` request for one returned item.

The log prints only pass/fail signals, the result count, and whether an affiliate
URL was returned. It does not print tokens, credentials, item URLs, seller data, or
the raw eBay response.

### Live listing input for future UK/US articles

Article-generation code can use the same client for either market:

```python
from src.ebay import EbayClient

client = EbayClient.for_market("uk")  # or "us"
items = client.discover(
    query="air fryers",
    max_price=500,
    affiliate_reference="article-air-fryers",
    limit=8,
)
```

`discover()` preserves eBay's search order and enriches each result through
`getItem`. Both calls include the market's EPN context, so returned affiliate URLs
retain campaign and per-article reference tracking. Existing Blogger, X and
Pinterest workflows remain unchanged.

The workflow defaults to `EBAY_ENV=production`. Change it to `sandbox` until
your eBay production access is approved.

## 6. Configure the niches

Edit `config.yml`.

Start with a small number of focused searches. The default file contains examples
for UK technology, toys, tools, home/kitchen and gaming.

Each niche has:
- `name`
- `slug`
- `query`
- `max_price`
- `min_score`
- `max_items`
- optional `require_free_shipping`

The score is used only as a pass/fail filter. Results are not re-sorted.

## 7. Turn on the scheduled workflow

The workflow runs at 07:17 and 19:17 Europe/London time and can also be run
manually.

For public repositories, standard GitHub-hosted Actions runners are normally free.
Remember that scheduled workflows in public repositories can be disabled after a
long period with no repository activity.

## Revenue attribution

Each niche uses an EPN `affiliateReferenceId` like:

```text
tech-laptops-20260913
```

That value is embedded by eBay in the affiliate URL as the sub-ID/custom ID.
Use EPN reporting to identify which categories produce clicks and qualifying sales.

## How selection works

The engine:
- requests only fixed-price items;
- requests delivery to Great Britain;
- optionally requests free shipping;
- uses eBay's returned ordering;
- filters out low-feedback sellers;
- rewards real eBay marketing discounts when returned;
- stores price observations for an item and rewards a meaningful fall versus its
  own observed history;
- never invents a "was" price.

If there are too few good items, the page says so instead of fabricating bargains.

## Affiliate disclosure

The Blogger themes carry a clear, site-wide affiliate disclosure. Generated
article bodies do not repeat that wording on every post, but retailer links
remain marked with `rel="sponsored nofollow"` and retain the correct tracking.

> This page contains affiliate links. If you buy through them, I may earn a
> commission at no extra cost to you.

Keep this visible. You are responsible for complying with applicable advertising,
consumer and affiliate-program rules.

## Zero-cost principle

This MVP intentionally avoids:
- paid hosting;
- paid databases;
- paid AI calls;
- paid schedulers.

If it ever earns money, you can decide later whether a domain or better hosting is
worth paying for.

## Local environment variables

For local production testing you may export the same variables used by GitHub:

```bash
export EBAY_CLIENT_ID="..."
export EBAY_CLIENT_SECRET="..."
export EPN_CAMPAIGN_ID="..."
export BLOGGER_CLIENT_ID="..."
export BLOGGER_CLIENT_SECRET="..."
export BLOGGER_REFRESH_TOKEN="..."
export BLOGGER_BLOG_ID="..."
export EBAY_ENV="sandbox"
```

Then run:

```bash
DRY_RUN=1 python main.py
```

Remove `DRY_RUN=1` only when you intentionally want to publish/update Blogger.

## Disclaimer

This is software, not a promise of profit. Affiliate approvals, API access,
traffic, search visibility, conversions and commission rates are outside the
script's control.
