"""Cloud-only weekly audience guides and a bounded, recorded growth experiment.

No desktop session or paid language-model API is used. Editorial briefs are
curated; marketplace inventory, prices, images and item details are fetched live.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
from io import BytesIO
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
START = date(2026, 10, 5)
END = date(2026, 10, 19)
STATE = ROOT / "state" / "cloud_editorial.json"
MARKETS = ("uk", "us")
REJECT = re.compile(r"\b(parts? only|spares?|faulty|broken|repair|accessor(?:y|ies)|liners?|replacement basket|cover only|box only|digital download)\b", re.I)
GROWTH_KEYS = ("air-fryers", "air-purifiers", "robot-vacuums")


def load(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def article_dir(market):
    return ROOT / ("articles" if market == "uk" else "articles-us")


def published(market):
    return load(ROOT / "state" / ("articles_published.json" if market == "uk" else "articles_us_published.json"))


def eligible(item, group, market):
    title = str(item.get("title", ""))
    if REJECT.search(title) or not re.search(group["match"], title, re.I):
        return False
    if str((item.get("price") or {}).get("currency")) != ("GBP" if market == "uk" else "USD"):
        return False
    if group.get("new_only") and str(item.get("conditionId")) != "1000":
        return False
    if group.get("capacity"):
        capacities = re.findall(r"\b(\d+(?:\.\d+)?)\s*(?:l(?:itre|iter)?s?|qt|quart[s]?)\b", title, re.I)
        if not capacities or not all(2 <= float(n) <= 5 for n in capacities):
            return False
    # Accessibility claims must be supported by item specifics, not a search hit.
    if group.get("specifics"):
        evidence = " ".join(str(a.get("value", "")) for a in item.get("localizedAspects", []))
        if not re.search(group["specifics"], evidence, re.I):
            return False
    return bool(item.get("itemId") and item.get("image", {}).get("imageUrl"))


def collect(brief, market, slug):
    import generate_daily_articles as daily
    from src.ebay import EbayClient
    from src.product_image_quality import checked_product_image
    client = EbayClient.for_market(market)
    picks, seen = [], set()
    for group in brief["groups"]:
        query = group.get("query_" + market, group["query"])
        # Broaden discovery if narrow marketplace searches have no qualifying
        # inventory. Never relax the brief's capacity, price or photo checks.
        queries = [query, *group.get("fallback_queries_" + market, group.get("fallback_queries", []))]
        selected = None
        for search_query in dict.fromkeys(queries):
            try:
                candidates = daily.current_picks(market, search_query, group["ceiling"][market], slug)
            except (RuntimeError, ValueError) as exc:
                print(f"[editorial-search-skip] {market} {search_query}: {exc}")
                continue
            for candidate in candidates:
                item_id = candidate.get("itemId")
                if not item_id or item_id in seen:
                    continue
                if REJECT.search(str(candidate.get("title", ""))):
                    continue
                try:
                    item = {**candidate, **client.get_item(item_id, affiliate_reference=slug)}
                except (RuntimeError, ValueError, KeyError) as exc:
                    print(f"[editorial-item-skip] {market} {item_id}: {exc}")
                    continue
                if not eligible(item, group, market):
                    continue
                availability = item.get("estimatedAvailabilities", [])
                if availability and not any(a.get("estimatedAvailabilityStatus") == "IN_STOCK" for a in availability):
                    continue
                if daily.listing_score(item, group["ceiling"][market], "GBP" if market == "uk" else "USD", query=search_query) is None:
                    continue
                try:
                    image, _, _ = checked_product_image(item["image"]["imageUrl"])
                except (RuntimeError, ValueError):
                    continue
                item["image"] = {**item["image"], "imageUrl": image}
                selected = {"item": item, "group": group, "query": search_query}
                seen.add(item["itemId"])
                break
            if selected is not None:
                break
        if selected is None:
            raise ValueError(f"No verified, relevant listing with a usable photo for {group['label']}")
        picks.append(selected)
    return picks


def escape(value):
    return html.escape(str(value), quote=True)


def render_brief(brief, market):
    parts = [f"<p>{escape(brief['intro_' + market])}</p>"]
    for title, text in brief["sections"]:
        parts.append(f"<h2>{escape(title)}</h2><p>{escape(text)}</p>")
    sources = brief.get("sources", [])
    if sources:
        parts.append("<h2>Sources and further checks</h2><ul>" + "".join(
            f'<li><a href="{escape(url)}">{escape(label)}</a></li>' for label, url in sources) + "</ul>")
    return "\n".join(parts)


def create_hero(article, market, picks):
    """Render a real listing photo and the actual brand logo, without AI costs."""
    import requests
    from PIL import Image, ImageDraw, ImageFont
    from src.product_image_quality import is_ebay_image, MAX_BYTES
    url = picks[0]["item"]["image"]["imageUrl"]
    if not is_ebay_image(url):
        raise ValueError("Unexpected product-image source")
    payload = bytearray()
    with requests.get(url, timeout=(5, 15), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Product photo unavailable")
        for chunk in response.iter_content(65536):
            payload.extend(chunk)
            if len(payload) > MAX_BYTES:
                raise ValueError("Product photo exceeds image limit")
    canvas = Image.new("RGB", (1600, 900), "#082f5b")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((840, 140, 1500, 800), radius=25, fill="white")
    with Image.open(BytesIO(payload)) as product:
        product = product.convert("RGB")
        product.thumbnail((600, 600), Image.Resampling.LANCZOS)  # Never enlarge.
        canvas.paste(product, (1170 - product.width // 2, 470 - product.height // 2))
    logo_path = ROOT / "assets" / "brand" / ("worth-buying-uk-logo.png" if market == "uk" else "worth-buying-usa-logo.png")
    with Image.open(logo_path) as logo:
        logo = logo.convert("RGBA")
        logo.thumbnail((540, 110), Image.Resampling.LANCZOS)
        draw.rounded_rectangle((70, 55, 660, 205), radius=16, fill="white")
        canvas.paste(logo, (95, 75), logo)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font = ImageFont.truetype(font_path, 48)
    words = article["title"].split()
    lines, line = [], ""
    for word in words:
        test = (line + " " + word).strip()
        if draw.textbbox((0, 0), test, font=font)[2] > 690 and line:
            lines.append(line)
            line = word
        else:
            line = test
    lines.append(line)
    if len(lines) > 7:
        raise ValueError("Hero title needs editorial shortening")
    for index, line in enumerate(lines):
        draw.text((75, 280 + index * 65), line, font=font, fill="white")
    small = ImageFont.truetype(font_path, 27)
    draw.text((75, 810), "PRACTICAL CHECKS · CURRENT LISTINGS", font=small, fill="#7de2dc")
    target = ROOT / "assets" / "ai" / market / (article["slug"] + ".jpg")
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, "JPEG", quality=92)


def build_article(brief, market, picks, today):
    import generate_daily_articles as daily
    from src.product_image_quality import product_image_html
    region = "UK" if market == "uk" else "USA"
    slug = f"{brief['key']}-{region.lower()}"
    title = brief["title_" + market]
    rows, cards = [], []
    for entry in picks:
        item, group, query = entry["item"], entry["group"], entry["query"]
        link, amazon, exact = daily.retailer_urls(item, market, query)
        price = daily.price_text(item, market)
        condition = item.get("condition", "Check listing")
        rows.append(f"<tr><td>{escape(group['label'])}</td><td>{escape(item['title'])}</td><td>{escape(price)}</td><td>{escape(condition)}</td></tr>")
        facts = [(a.get("name"), a.get("value")) for a in item.get("localizedAspects", []) if a.get("name") and a.get("value")][:12]
        cards.append(
            f"<h3>{escape(group['label'])}: {escape(item['title'])}</h3>"
            + product_image_html(item["image"]["imageUrl"], item["title"])
            + f"<p><strong>Price when checked:</strong> {escape(price)}. <strong>Condition:</strong> {escape(condition)}. Delivery charges may be additional.</p>"
            + f"<p>{escape(group['decision'])}</p><p><strong>Check before choosing:</strong> {escape(group['check'])}</p>"
            + "<details><summary>Retailer-supplied item details</summary><ul>"
            + "".join(f"<li>{escape(k)}: {escape(v)}</li>" for k, v in facts) + "</ul></details>"
            + f"<p>{escape(daily.seller_text(item))} Check the exact variant, delivery, returns and warranty before ordering.</p>"
            + f'<p><a href="{escape(link)}" rel="sponsored nofollow">Check this eBay listing</a> · '
            + f'<a href="{escape(amazon)}" rel="sponsored nofollow">Search Amazon for {"this model" if exact else "alternatives"}</a></p>'
        )
    related = daily.related_guides(market=market, current_slug=slug, display=title, query=brief["groups"][0]["query"], category="Home & Kitchen", limit=4)
    content = (
        f"<p><strong>Listing prices checked:</strong> {today.isoformat()}. Prices and stock can change.</p>"
        + daily.editorial_trust_html(market, today.isoformat())
        + render_brief(brief, market)
        + "<h2>Current listings to compare</h2><p>These are retailer-data comparisons, not hands-on tests. Rows represent different buying needs, not a performance ranking. Retailer-supplied specifications are not independent test results.</p>"
        + '<div style="overflow-x:auto"><table><thead><tr><th>Buying need</th><th>Listing</th><th>Item price</th><th>Condition</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
        + "".join(cards) + daily.authority_hub_html(market, brief.get("parent", "air-fryers"))
        + daily.related_guides_html(related)
    )
    return {"slug": slug, "title": title, "source_sha": hashlib.sha256(content.encode()).hexdigest(),
            "mode": "publish", "content_html": content, "primary_category": "Home & Kitchen",
            "labels": ["Home & Kitchen", "Bespoke Buying Guides", region],
            "ai_visual_enabled": False, "pinterest_enabled": True,
            "hero_image_kicker": "PRACTICAL BUYING GUIDE", "pinterest_title": title,
            "pinterest_subtitle": "Practical checks and current products to compare",
            "x_text": f"{title}\n\nPractical checks and current products to compare. Guide contains affiliate links.\n{{url}}",
            "youtube_short_points": [e["group"]["check"] for e in picks][:3],
            "_seo": {"description": brief["intro_" + market][:155], "target_country": "GB" if market == "uk" else "US", "language": "en-GB" if market == "uk" else "en-US", "stable_slug": True, "editorial_method": "curated-brief-and-live-retailer-details"},
            "_generator": {"market": market, "topic": brief["key"], "content_type": "bespoke-weekly", "live_ebay_picks": True, "pick_count": len(picks), "date": today.isoformat()}}


def weekly(now, state, briefs, collector=collect, builder=build_article, hero=create_hero):
    # Wednesday onward permits a recovery run after a temporary outage.
    today = now.date()
    if today < START or now.weekday() < 2 or (now.weekday() == 2 and now.hour < 10):
        return
    week = today.strftime("%G-W%V")
    for market in MARKETS:
        ledger = state.setdefault("weekly", {}).setdefault(market, {})
        if ledger.get("week") == week:
            continue
        index = int(ledger.get("next", 0)) % len(briefs)
        brief = briefs[index]
        try:
            if today > date.fromisoformat(brief["review_by"]):
                raise ValueError("Editorial evidence needs review; retaining a draft rather than publishing stale advice")
            picks = collector(brief, market, f"{brief['key']}-{market}")
            article = builder(brief, market, picks, today)
            hero(article, market, picks)
            save(article_dir(market) / (article["slug"] + ".json"), article)
            ledger.update(week=week, next=index + 1, slug=article["slug"], status="generated-awaiting-publisher", error=None)
        except Exception as exc:
            ledger.update(status="blocked", error=f"{type(exc).__name__}: {exc}", attempted=today.isoformat())
            save(ROOT / "drafts-bespoke" / f"{market}-{brief['key']}.json", {"brief": brief, "mode": "draft", "reason": ledger["error"]})


GROWTH_COPY = {
    "air-fryers": ("Match the basket to the meals you actually cook", "Measure the available counter space, the drawer opening and the ventilation clearance specified in the manual. Compare usable basket shape as well as stated capacity: a tall basket may not fit the same food in one layer as a wider one. Decide whether you need two foods ready together before paying for two drawers. Check the price and availability of replacement baskets and the cleaning instructions for the exact model. For student accommodation, get permission before buying a cooking appliance; rules differ by building. A used listing should state condition, missing parts and warranty clearly."),
    "air-purifiers": ("Compare useful room coverage and ongoing filter costs", "Measure your room and compare the model's clean air delivery rate (CADR) and stated test conditions. Do not assume a headline coverage figure describes quiet overnight operation. Check replacement-filter availability and price, the manufacturer's replacement guidance and power consumption before comparing ownership costs. Look for noise figures tied to the speed you intend to use. Do not treat a purifier as a replacement for controlling pollution sources or ventilation. ENERGY STAR explains CADR and room-sizing considerations in its air-cleaner buying guidance."),
    "robot-vacuums": ("Check the awkward parts of your home first", "Measure furniture clearance and doorway thresholds, and consider where the dock can sit with the clearance its manual requires. Compare the exact model's mapping and no-go-area controls, rug handling, replacement brush and filter availability, and the maintenance needed after each clean. An advertised suction number does not by itself establish cleaning performance. If you have pets or loose cables, check independent evidence for obstacle handling rather than assuming a camera or sensor prevents every accident. A low purchase price can be offset by recurring bag, mop-pad or proprietary consumable costs.")
}


def select_growth(market):
    result = []
    entries = published(market)
    for key in GROWTH_KEYS:
        candidates = []
        for slug, entry in entries.items():
            if entry.get("status") != "published" or not entry.get("url"):
                continue
            filename = str(entry.get("source_file") or f"{slug}.json")
            if Path(filename).name != filename:
                continue
            path = article_dir(market) / filename
            article = load(path)
            topic = article.get("_generator", {}).get("topic")
            # The original September air-fryer guides predate generator metadata.
            if not topic and slug.startswith("best-air-fryers-worth-buying-"):
                topic = "air-fryers"
            if topic == key:
                candidates.append((slug, path, article, entry))
        if candidates:
            result.append(sorted(candidates, key=lambda x: x[0])[0])
    return result


def growth(now, state):
    if not START <= now.date() <= END:
        return
    for market in MARKETS:
        ledger = state.setdefault("growth", {}).setdefault(market, {})
        for slug, path, article, entry in select_growth(market):
            if slug in ledger:
                continue
            key = article.get("_generator", {}).get("topic") or "air-fryers"
            title, text = GROWTH_COPY[key]
            section = f'<section id="wb-practical-comparison"><h2>{escape(title)}</h2><p>{escape(text)}</p>'
            if key == "air-purifiers":
                section += '<p><a href="https://www.energystar.gov/products/air_cleaners">ENERGY STAR air-cleaner buying guidance</a></p>'
            section += "</section>"
            if 'id="wb-practical-comparison"' not in article.get("content_html", ""):
                article["content_html"] += section
                article["source_sha"] = hashlib.sha256(article["content_html"].encode()).hexdigest()
                save(path, article)
            ledger[slug] = {"url": entry["url"], "title": article["title"], "source_file": path.name,
                            "updated": now.date().isoformat(), "status": "source-updated-awaiting-publisher"}
        if len(ledger) < 3:
            state.setdefault("warnings", {})[market] = f"Only {len(ledger)} of three target guides matched existing published source files"


def tagged_url(url, market):
    parts = urlsplit(url)
    expected = "worthbuyinguk.co.uk" if market == "uk" else "worthbuyingusa.com"
    if parts.scheme != "https" or parts.hostname not in {expected, "www." + expected}:
        raise ValueError("Promotion URL does not belong to the intended market")
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.startswith("utm_")]
    query += [("utm_source", "x"), ("utm_medium", "social"), ("utm_campaign", "worthbuying-october-guide-improvements"), ("utm_content", market)]
    return urlunsplit(parts._replace(query=urlencode(query)))


def persist_reservation(state):
    """Persist intent remotely before a non-idempotent external post call."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Live promotions run only inside the configured GitHub workflow")
    save(STATE, state)
    for args in (("git", "add", "state/cloud_editorial.json"),
                 ("git", "commit", "-m", "Reserve cloud guide promotion to prevent retries duplicating posts"),
                 ("git", "push", "origin", "HEAD:main")):
        subprocess.run(args, cwd=ROOT, check=True, capture_output=True)


def promote(now, state, reserve=persist_reservation):
    if not START <= now.date() < END or now.weekday() not in (1, 3) or now.hour < 11:
        return
    from src.buffer import BufferClient
    api_key = os.getenv("BUFFER_API_KEY", "").strip()
    if not api_key:
        state.setdefault("warnings", {})["promotion"] = "BUFFER_API_KEY unavailable; no promotion attempted"
        return
    for market in MARKETS:
        history = state.setdefault("promotions", {}).setdefault(market, {})
        day = now.date().isoformat()
        if day in history:
            continue  # Includes uncertain requests: never blindly send again.
        entries = published(market)
        targets = list(state.get("growth", {}).get(market, {}).items())
        already = {v.get("slug") for v in history.values()}
        candidates = [(s, e) for s, e in targets if s not in already and entries.get(s, {}).get("status") == "published"]
        if not candidates:
            continue
        slug, entry = candidates[0]
        source = load(article_dir(market) / entry["source_file"])
        if entries[slug].get("source_sha") != source.get("source_sha"):
            continue  # Wait until the changed guide is confirmed published.
        url = tagged_url(entries[slug]["url"], market)
        client = BufferClient(api_key, "Worth Buying UK" if market == "uk" else "Worth Buying USA")
        channel = client.find_x_channel_id()  # Resolve correct account before reservation.
        text = f"{entry['title'][:120]}\n\nCompare the practical checks before buying. Guide contains affiliate links.\n{url}"
        history[day] = {"slug": slug, "status": "reserved-outcome-unknown", "url": url}
        reserve(state)
        try:
            response = client.create_post(text=text, mode="shareNow", channel_id=channel)
            history[day].update(status="accepted", post_id=str(response["id"]), provider_status=response.get("status"))
        except Exception as exc:
            history[day].update(status="outcome-unknown", error=type(exc).__name__)
        save(STATE, state)


def search_metrics(now, state):
    """Read-only snapshots using the repository's existing Search Console access."""
    if now.date() < START or state.get("metrics_finished"):
        return
    from src.search_console import build_service, choose_site
    service = build_service()
    if service is None:
        state.setdefault("warnings", {})["metrics"] = "Search Console credentials unavailable; search performance not measured"
        return
    end = now.date() - timedelta(days=3)
    start = end - timedelta(days=13)
    for market in MARKETS:
        try:
            site = choose_site(service, market)
            if not site:
                raise ValueError("No verified property available")
            result = service.searchanalytics().query(siteUrl=site, body={"startDate": str(start), "endDate": str(end), "type": "web", "dimensions": ["date"], "rowLimit": 100}).execute()
            rows = result.get("rows", [])
            snapshot = {"start": str(start), "end": str(end), "source": "Google Search Console web search", "clicks": sum(r.get("clicks", 0) for r in rows), "impressions": sum(r.get("impressions", 0) for r in rows), "rows": rows}
            metrics = state.setdefault("search_metrics", {}).setdefault(market, {})
            metrics.setdefault("baseline", snapshot)
            metrics["latest"] = snapshot
        except Exception as exc:
            state.setdefault("warnings", {})[f"metrics_{market}"] = f"Search metrics unavailable: {type(exc).__name__}"
    if now.date() >= END:
        state["metrics_finished"] = True


def reconcile_publication(state):
    for market in MARKETS:
        entries = published(market)
        for slug, record in state.get("growth", {}).get(market, {}).items():
            source = load(article_dir(market) / record["source_file"])
            remote = entries.get(slug, {})
            if remote.get("status") == "published" and remote.get("source_sha") == source.get("source_sha"):
                record.update(status="published", url=remote.get("url"))
        record = state.get("weekly", {}).get(market, {})
        slug = record.get("slug")
        if slug and record.get("status") != "blocked":
            source = load(article_dir(market) / f"{slug}.json")
            remote = entries.get(slug, {})
            if remote.get("status") == "published" and remote.get("source_sha") == source.get("source_sha"):
                record.update(status="published", url=remote.get("url"))


def report(state, now):
    lines = ["# WorthBuying cloud editorial", f"Run: {now.isoformat()}",
             "Runs on GitHub-hosted infrastructure; no desktop session required.",
             "Generated/source-updated means awaiting the separate publisher, not confirmed live."]
    for kind in ("weekly", "growth", "promotions", "search_metrics", "warnings"):
        lines += [f"## {kind}", "```json", json.dumps(state.get(kind, {}), indent=2), "```"]
    if now.date() >= END:
        lines += ["Growth experiment finished. No further experiment promotions will be sent.",
                  "Google search clicks, Cloudflare visits, retailer clicks and sales are different measures. No traffic or sales lift is claimed by this job."]
    text = "\n".join(lines)
    save(ROOT / "state" / "cloud_editorial_report.json", {"run": now.isoformat(), "state": state})
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Validate briefs and show plan without API calls or writes")
    args = parser.parse_args()
    briefs = load(ROOT / "automation" / "bespoke_briefs.json")
    now = datetime.now(ZoneInfo("Europe/London"))
    if args.preview:
        assert len({b["key"] for b in briefs}) == len(briefs)
        for b in briefs:
            assert b["groups"] and b["title_uk"] and b["title_us"] and b["sections"]
            for g in b["groups"]:
                re.compile(g["match"])
        print(json.dumps({"topics": [b["key"] for b in briefs], "markets": MARKETS, "growth_end": str(END)}, indent=2))
        return
    state = load(STATE)
    try:
        reconcile_publication(state)
        weekly(now, state, briefs)
        growth(now, state)
        search_metrics(now, state)
        promote(now, state)
    finally:
        save(STATE, state)
        report(state, now)


if __name__ == "__main__":
    main()
