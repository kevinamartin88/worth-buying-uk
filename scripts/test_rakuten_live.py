from __future__ import annotations

import argparse

from src.rakuten import RakutenClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", required=True, choices=("uk", "us"))
    args = parser.parse_args()

    client = RakutenClient.for_market(args.market)
    if client is None:
        raise SystemExit(
            f"RAKUTEN_{args.market.upper()}_CLIENT_ID, CLIENT_SECRET and ACCOUNT_ID are required"
        )

    product = client.search_one("air fryer")
    if product is None:
        print(
            f"[rakuten-live] {args.market.upper()} authentication succeeded, but no approved "
            "product matched the test query."
        )
        return

    print(
        f"[rakuten-live] {args.market.upper()} PASS: authenticated Product Search returned one valid "
        f"GBP tracked product from {product.merchant}."
    )


if __name__ == "__main__":
    main()
