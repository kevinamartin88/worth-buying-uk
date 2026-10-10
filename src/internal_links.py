"""Build reciprocal, same-market links without rewriting article copy."""
from __future__ import annotations

import html
import re

from src.site_pages import category_key

START = "<!-- wb-discovery-links:start -->"
END = "<!-- wb-discovery-links:end -->"
BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
STOP = {"best", "worth", "buying", "guide", "guides", "current", "offers", "approved",
        "retailers", "the", "in", "for", "and", "from", "with", "usa", "uk", "us", "2026"}


def related_graph(catalog: list[dict], limit: int = 3) -> dict[str, list[dict]]:
    graph = {row["slug"]: {} for row in catalog}
    for row in catalog:
        tokens = set(re.findall(r"[a-z]+", row["title"].casefold())) - STOP
        candidates = []
        for other in catalog:
            if row["slug"] == other["slug"] or row["url"] == other["url"]:
                continue
            overlap = len(tokens & (set(re.findall(r"[a-z]+", other["title"].casefold())) - STOP))
            shared = set(row.get("categories", [])) & set(other.get("categories", []))
            # A generic seasonal overlap alone does not justify a recommendation.
            meaningful = shared - {"Seasonal", "Home & Kitchen"}
            cluster_match = bool(row.get("cluster") and row.get("cluster") == other.get("cluster"))
            score = overlap * 3 + len(meaningful) + int(cluster_match)
            if score > 0:
                candidates.append((score, other.get("checked", ""), other["slug"], other))
        candidates.sort(key=lambda entry: entry[:3], reverse=True)
        selected = 0
        for _, _, _, other in candidates:
            if selected >= limit or len(graph[row["slug"]]) >= limit * 2:
                break
            if other["slug"] in graph[row["slug"]] or len(graph[other["slug"]]) >= limit * 2:
                continue
            graph[row["slug"]][other["slug"]] = other
            graph[other["slug"]][row["slug"]] = row
            selected += 1
    return {slug: list(links.values()) for slug, links in graph.items()}


def discovery_html(row: dict, related: list[dict], pages: dict) -> str:
    links = []
    for category in row.get("categories", []):
        page = pages.get(category_key(category)) or {}
        if page.get("url"):
            links.append((page["url"], category + " buying guides"))
    methodology = pages.get("methodology") or {}
    if methodology.get("url"):
        links.append((methodology["url"], "How Worth Buying chooses products"))
    links.extend((other["url"], other["title"]) for other in related)
    links = list(dict.fromkeys(links))
    if not links:
        return ""
    body = " Â· ".join(f'<a href="{html.escape(url, quote=True)}">{html.escape(title)}</a>'
                      for url, title in links)
    return (START + '<aside class="wb-discovery-links" '
            'style="margin:28px 0;padding:16px 18px;background:#f6f8fb;border-left:4px solid #082f5b">'
            '<strong>More from Worth Buying:</strong> ' + body + '</aside>' + END)


def update_discovery_links(content: str, row: dict, related: list[dict], pages: dict) -> str:
    # Replace the previous automation-owned footer, never article copy.
    content = re.sub(r'<aside class="wb-authority-links"[^>]*>.*?</aside>', "", content, flags=re.S).rstrip()
    block = discovery_html(row, related, pages)
    if BLOCK.search(content):
        return BLOCK.sub(lambda _: block, content)
    return content.rstrip() + "\n" + block if block else content
