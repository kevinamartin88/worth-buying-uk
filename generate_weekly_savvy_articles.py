from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state" / "weekly_savvy_buyer.json"

THEMES = (
    {
        "slug": "fake-discounts",
        "name": "spotting fake discounts",
        "promise": "separate a genuine saving from a price label designed to create urgency",
        "checks": (
            "Compare the current price with more than one established retailer or marketplace.",
            "Look at the exact model number because an older or stripped-back version may appear cheaper.",
            "Check whether delivery, required accessories or membership fees erase the headline saving.",
            "Pause when a countdown or 'only one left' message is the main reason you want to buy.",
        ),
        "red_flags": "inflated reference prices, permanent sales, unclear model numbers and pressure-heavy countdowns",
    },
    {
        "slug": "reviews",
        "name": "reading product reviews critically",
        "promise": "use reviews as evidence without being misled by star ratings or suspicious praise",
        "checks": (
            "Read recent three- and four-star reviews for balanced comments about everyday use.",
            "Separate reviews for the exact model from reviews grouped across several variants.",
            "Look for repeated details about reliability, sizing, battery life or after-sales support.",
            "Treat vague praise, repeated wording and sudden bursts of reviews as weak evidence.",
        ),
        "red_flags": "review merging, copied wording, incentives that are not disclosed and ratings with no useful detail",
    },
    {
        "slug": "total-cost",
        "name": "calculating total ownership cost",
        "promise": "judge value across the product's useful life rather than by checkout price alone",
        "checks": (
            "List consumables, subscriptions, replacement parts and accessories needed for normal use.",
            "Estimate energy or battery costs where they are material to the purchase.",
            "Check the likely service life and whether repairs or replacement parts are realistically available.",
            "Compare the annual cost of ownership, not merely the initial discount.",
        ),
        "red_flags": "mandatory subscriptions, proprietary consumables, unavailable spares and unusually short support periods",
    },
    {
        "slug": "returns-warranties",
        "name": "checking returns and warranties",
        "promise": "understand what happens if the product is unsuitable, faulty or damaged",
        "checks": (
            "Read the seller's current returns window, exclusions and who pays return delivery.",
            "Check whether the warranty is provided by the retailer, manufacturer or a third party.",
            "Save the listing, order confirmation and any written promises made before purchase.",
            "Confirm how bulky, personalised, hygiene-sensitive or opened products are handled.",
        ),
        "red_flags": "unclear return addresses, warranty wording that cannot be found before payment and sellers avoiding written answers",
    },
    {
        "slug": "refurbished-used",
        "name": "buying refurbished, open-box or used products",
        "promise": "capture the saving while controlling condition, battery and support risk",
        "checks": (
            "Match the condition grade to a written description rather than relying on a label alone.",
            "Check battery health, missing accessories, activation locks and serial-number status where relevant.",
            "Prefer sellers that explain testing, data wiping, warranty cover and returns clearly.",
            "Compare the saving with the price of a new model during normal promotions.",
        ),
        "red_flags": "stock photos only, vague grading, missing serial details and prices too close to new stock",
    },
    {
        "slug": "seller-checks",
        "name": "checking an unfamiliar seller",
        "promise": "evaluate who is taking your money before judging the product offer",
        "checks": (
            "Review recent feedback and focus on disputes involving the same type of product.",
            "Check business contact details, realistic dispatch times and the stated return location.",
            "Use payment methods and marketplaces that provide an appropriate dispute process.",
            "Keep communication and payment inside the platform when buying through a marketplace.",
        ),
        "red_flags": "requests for off-platform payment, recently changed product categories, copied policies and inconsistent contact details",
    },
    {
        "slug": "specifications",
        "name": "comparing specifications that matter",
        "promise": "translate technical numbers into the features that affect everyday use",
        "checks": (
            "Write down the three jobs the product must perform before comparing specification sheets.",
            "Confirm units, test conditions and whether quoted performance is typical or a best-case maximum.",
            "Prioritise fit, compatibility, capacity and usability over features you are unlikely to use.",
            "Verify the exact regional model because ports, plugs, software and included accessories can differ.",
        ),
        "red_flags": "headline numbers without test conditions, ambiguous model suffixes and long feature lists with no practical explanation",
    },
    {
        "slug": "price-comparison",
        "name": "building a fair price comparison",
        "promise": "compare like with like across retailers, bundles and marketplaces",
        "checks": (
            "Use the exact model, capacity, colour and included accessories in every comparison.",
            "Add delivery, installation, protection plans and any required membership cost.",
            "Value bundled extras only if you would otherwise buy them.",
            "Record the price and date so a changing offer does not distort your decision.",
        ),
        "red_flags": "different variants presented as identical, low prices with high delivery fees and bundles padded with low-value extras",
    },
    {
        "slug": "repairability",
        "name": "checking repairability and product support",
        "promise": "avoid a cheap purchase that becomes disposable after one fault or worn part",
        "checks": (
            "Search for replacement batteries, filters, seals, cables and other predictable wear items.",
            "Check the manufacturer's stated software or security-support period for connected products.",
            "Look for service information and realistic repair options in your area.",
            "Consider whether the product can still perform its main job if an app or subscription ends.",
        ),
        "red_flags": "sealed wear parts, no published support period, unavailable consumables and essential features locked to an app",
    },
    {
        "slug": "safety-authenticity",
        "name": "checking safety and authenticity",
        "promise": "spot avoidable risks before buying electrical, branded or safety-critical products",
        "checks": (
            "Confirm the product is intended for your market and supplied with suitable power equipment.",
            "Check current manufacturer notices or official recall information before buying older stock.",
            "Compare packaging, model details and seller claims with the manufacturer's official information.",
            "Be cautious with safety-critical products whose history or authenticity cannot be established.",
        ),
        "red_flags": "altered serial labels, missing instructions, incompatible plugs and prices far below every credible seller",
    },
    {
        "slug": "subscriptions-finance",
        "name": "checking subscriptions and payment plans",
        "promise": "understand the full commitment behind a low monthly or introductory price",
        "checks": (
            "Calculate the full amount payable, including interest, fees and required subscriptions.",
            "Check what functionality remains if you stop paying for the connected service.",
            "Read renewal timing and cancellation steps before accepting a trial.",
            "Compare the financed total with the normal cash price and with keeping your current product.",
        ),
        "red_flags": "pre-ticked trials, unclear renewal prices, essential features behind subscriptions and payment plans longer than the likely useful life",
    },
    {
        "slug": "delivery-condition",
        "name": "protecting yourself at delivery",
        "promise": "create a clear record if an expensive or fragile order arrives late, incomplete or damaged",
        "checks": (
            "Review tracking through the retailer or carrier's official site rather than message links.",
            "Photograph significant packaging damage and check the contents promptly.",
            "Keep packaging until you know the item works and all listed parts are present.",
            "Report problems through the seller's documented process and retain the reference number.",
        ),
        "red_flags": "unexpected payment requests, pressure to confirm receipt before inspection and couriers contacting you through unofficial channels",
    },
    {
        "slug": "needs-checklist",
        "name": "turning needs into a buying checklist",
        "promise": "buy the product that fits your routine instead of the one with the loudest marketing",
        "checks": (
            "Define the problem you need to solve and how often the product will be used.",
            "Separate must-have features from preferences and features you can ignore.",
            "Set a total budget that includes accessories, delivery and ongoing costs.",
            "Write one reason not to buy yet, such as uncertain sizing, compatibility or timing.",
        ),
        "red_flags": "buying for a hypothetical use, upgrading without a clear benefit and changing your requirements to fit a tempting deal",
    },
)

ANGLES = (
    ("before-you-shop", "Before You Shop", "prepare a short evidence-based plan before opening retailer tabs"),
    ("compare-options", "How to Compare Your Options", "reduce a crowded shortlist to products that genuinely fit your needs"),
    ("avoid-traps", "Common Traps to Avoid", "recognise the sales tactics and missing details that lead to poor purchases"),
    ("final-checklist", "The Final Five-Minute Checklist", "make a calm final check before committing money"),
)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def selected_topic(week: int) -> tuple[dict, tuple[str, str, str]]:
    index = (week - 1) % 52
    return THEMES[index // 4], ANGLES[index % 4]


def market_details(market: str) -> dict[str, str]:
    if market == "uk":
        return {
            "name": "Worth Buying UK",
            "region": "UK",
            "site": "https://www.worthbuyinguk.co.uk/",
            "currency": "£",
            "spelling": "authorised",
            "articles": "articles",
        }
    return {
        "name": "Worth Buying USA",
        "region": "US",
        "site": "https://www.worthbuyingusa.com/",
        "currency": "$",
        "spelling": "authorized",
        "articles": "articles-us",
    }


def list_html(items: tuple[str, ...] | list[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def build_article(market: str, publish_date: date) -> dict:
    if market not in {"uk", "us"}:
        raise ValueError(f"Unsupported market: {market}")

    iso_year, week, _ = publish_date.isocalendar()
    theme, angle = selected_topic(week)
    angle_slug, angle_title, angle_promise = angle
    details = market_details(market)
    region = details["region"]
    title = f"Savvy Buyer Saturday: {angle_title} for {theme['name'].title()} ({region})"
    slug = slugify(
        f"savvy-buyer-{theme['slug']}-{angle_slug}-{market}-{iso_year}-week-{week:02d}"
    )
    checks = theme["checks"]
    final_checks = (
        "I have identified the exact model or version.",
        "I have compared the total delivered cost with at least one credible alternative.",
        "I understand the current returns, warranty and support arrangements.",
        "I have checked the seller and saved the important product claims.",
        "I would still choose this product without the countdown, badge or claimed saving.",
    )
    content = f"""
<p><strong>Savvy Buyer Saturday</strong> is {html.escape(details['name'])}'s weekly guide to making calmer, better-informed purchases. This week focuses on <strong>{html.escape(theme['name'])}</strong>: how to {html.escape(theme['promise'])}.</p>
<p>The aim is not to find the cheapest listing at any cost. A savvy purchase balances price, suitability, seller reliability, support and the likely cost of owning the product. Use this guide as a practical framework and always check the live product information and current policies before paying.</p>
<h2>This week's buying lesson</h2>
<p>{html.escape(angle_promise.capitalize())}. Start by writing down what evidence would make the purchase sensible and what information would make you walk away. This small pause makes it easier to compare offers on their merits rather than reacting to urgency.</p>
<h2>Four details worth checking</h2>
{list_html(checks)}
<p>For a fair comparison, apply the same checks to every shortlisted option. If one seller does not provide enough detail, treat that missing information as a disadvantage rather than filling the gap with assumptions.</p>
<h2>Warning signs to slow down for</h2>
<p>Be particularly cautious about {html.escape(theme['red_flags'])}. One warning sign does not automatically prove that an offer is poor, but several together are a good reason to pause, ask questions or choose a clearer alternative.</p>
<p>Do not move payment or communication away from a trusted platform merely to obtain a small extra discount. Use an appropriate payment method, keep copies of the listing and order details, and never share security codes with a seller or caller.</p>
<h2>Compare value, not just price</h2>
<p>Write the delivered price in one column, then add realistic extras: required accessories, installation, consumables, subscriptions and likely replacement parts. A {html.escape(details['currency'])}10 saving can disappear quickly if the cheaper option is missing an essential item or is difficult to return.</p>
<p>Suitability matters too. The better-value choice is normally the least expensive product that reliably meets your real requirements—not the cheapest product overall and not automatically the model with the longest feature list.</p>
<h2>Your five-minute checkout checklist</h2>
{list_html(final_checks)}
<p>If any answer is no, leave the item in your basket while you check. A genuine good-value purchase should still make sense after a short pause.</p>
<h2>Questions savvy buyers ask</h2>
<h3>Should I always wait for a sale?</h3>
<p>No. Waiting is useful when the purchase is optional and the normal price is clear. For an urgent replacement, availability, reliability and support may matter more than chasing the lowest historic price.</p>
<h3>How many options should I compare?</h3>
<p>Three credible options are often enough: a good-value baseline, the model you currently prefer and one strong alternative. Comparing dozens can create noise without improving the decision.</p>
<h3>What evidence should I keep?</h3>
<p>Keep the order confirmation and copies of important claims about model, condition, delivery, warranty and included accessories. Use the seller's official support route if a problem develops.</p>
<h2>The Worth Buying verdict</h2>
<p>A savvy buyer is not someone who never spends money. It is someone who knows what they need, checks the evidence and recognises when an attractive offer is not genuinely good value. This week's rule is simple: <strong>clarity beats urgency</strong>.</p>
<p>Browse the latest product-specific guides on <a href="{html.escape(details['site'])}">{html.escape(details['name'])}</a> when you are ready to compare individual categories.</p>
<p><em>This article provides general shopping guidance. Product details, prices, seller terms and consumer protections can change, so verify the current information relevant to your purchase.</em></p>
""".strip()

    return {
        "slug": slug,
        "source_sha": f"savvy-{iso_year}-w{week:02d}-{market}-v1",
        "mode": "publish",
        "title": title,
        "labels": ["Savvy Buyer", "Buying Advice", "Consumer Tips", region],
        "pinterest_enabled": True,
        "pinterest_title": title,
        "pinterest_subtitle": f"A practical weekly checklist for {theme['name']}",
        "x_image_title": f"Savvy Buyer: {angle_title}",
        "x_kicker": "SAVVY BUYER SATURDAY",
        "x_subtitle": f"This week's guide to {theme['name']}",
        "x_text": (
            f"🛒 Savvy Buyer Saturday: {angle_title}\n\n"
            f"A practical guide to {theme['name']}—what to check, warning signs to notice, "
            f"and a five-minute checklist before you buy.\n\nRead the full guide 👇\n{{url}}\n"
            "#BuyingTips #SavvyShopping"
        ),
        "content_html": content,
    }


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def generate(run_date: date) -> int:
    iso_year, week, _ = run_date.isocalendar()
    key = f"{iso_year}-W{week:02d}"
    state = load_state()
    generated = 0

    for market in ("uk", "us"):
        if state.get(market, {}).get("week") == key:
            print(f"[savvy-skip] {market.upper()}: article already generated for {key}")
            continue

        article = build_article(market, run_date)
        output_dir = ROOT / market_details(market)["articles"]
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{article['slug']}.json"
        if target.exists():
            raise RuntimeError(f"Refusing to overwrite existing article: {target}")
        target.write_text(
            json.dumps(article, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        state[market] = {
            "week": key,
            "date": run_date.isoformat(),
            "slug": article["slug"],
            "title": article["title"],
        }
        generated += 1
        print(f"[savvy-created] {market.upper()}: {target.relative_to(ROOT)}")

    save_state(state)
    print(f"Weekly savvy-buyer generation complete: {generated} article(s) created.")
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description="Create weekly UK and USA savvy-buyer articles.")
    parser.add_argument(
        "--date",
        help="Optional ISO date for testing; defaults to the current UTC date.",
    )
    args = parser.parse_args()
    run_date = date.fromisoformat(args.date) if args.date else datetime.now(timezone.utc).date()
    generate(run_date)


if __name__ == "__main__":
    main()
