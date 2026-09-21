from __future__ import annotations

import argparse

from src.ai_visuals import generate_market


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["uk", "us", "all"], default="all")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    markets = ["uk", "us"] if args.market == "all" else [args.market]
    total = 0
    for market in markets:
        count = generate_market(market, force=args.force)
        total += count
        print(f"Generated {count} new AI hero image(s) for {market.upper()}.")

    print(f"Done. Generated {total} AI hero image(s).")


if __name__ == "__main__":
    main()
