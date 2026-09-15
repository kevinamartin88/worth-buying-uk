from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent.parent
DOMAIN_CONFIG = ROOT / "automation" / "domains.json"


def load_domain_config() -> dict:
    return json.loads(DOMAIN_CONFIG.read_text(encoding="utf-8"))


def get_site_config(market: str) -> dict:
    key = market.strip().lower()
    config = load_domain_config()
    if key not in config:
        raise KeyError(f"Unknown market: {market}")
    return config[key]


def get_site_url(market: str) -> str:
    site = get_site_config(market)
    active = str(site.get("active", "blogspot")).strip().lower()
    if active not in {"blogspot", "custom"}:
        raise ValueError(f"Invalid active domain mode for {market}: {active}")
    if active == "custom" and not site.get("custom_domain_connected_to_blogger", False):
        raise RuntimeError(
            f"Refusing to use the {market.upper()} custom domain before it is marked as connected to Blogger"
        )
    key = "custom_url" if active == "custom" else "blogspot_url"
    return str(site[key]).rstrip("/") + "/"


def get_site_host(market: str) -> str:
    return urlsplit(get_site_url(market)).netloc
