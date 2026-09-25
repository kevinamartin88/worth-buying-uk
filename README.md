# Zero-Cost Affiliate Engine

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
BLOGGER_CLIENT_ID
BLOGGER_CLIENT_SECRET
BLOGGER_REFRESH_TOKEN
BLOGGER_BLOG_ID
```

The eBay values are:

- `EBAY_CLIENT_ID`: the eBay production App ID (Client ID).
- `EBAY_CLIENT_SECRET`: the matching production Cert ID (Client Secret).
- `EPN_CAMPAIGN_ID`: the UK EPN campaign ID used to request UK affiliate URLs.
- `EPN_US_CAMPAIGN_ID`: the USA EPN campaign ID used to request USA affiliate URLs.

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

Every page includes a clear disclosure before any affiliate links:

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
