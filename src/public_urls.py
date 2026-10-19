"""Consolidate links we control onto each site's public canonical host."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from src.site_config import get_site_config, get_site_host


def canonical_public_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {'https', 'http'} or parts.username or parts.password:
        return url
    for market in ('uk', 'us'):
        host = get_site_host(market)
        backend = urlsplit(get_site_config(market)['blogspot_url']).hostname
        if parts.netloc.lower() not in {host, host.removeprefix('www.'), backend}:
            continue
        # Preserve campaign parameters and anchors. Never alter affiliate URLs.
        query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                           if not (k == 'm' and v in {'0', '1'})])
        return urlunsplit(('https', host, parts.path, query, parts.fragment))
    return url
