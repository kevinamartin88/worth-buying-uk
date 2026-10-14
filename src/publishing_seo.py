"""Non-visual metadata and regional measurement added at the publication boundary."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from src.seo import meta_description, plain_text
from src.publication_quality import choose_description, duplicate_descriptions, repair_affiliate_links

REVISION = "published-seo-v1"
START = "<!-- wb-published-seo:start -->"
END = "<!-- wb-published-seo:end -->"
BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)


def description_for(article: dict, market: str) -> str:
    return choose_description(article, market, duplicate_descriptions(market))[0]


def metadata_html(article: dict, market: str) -> str:
    description = json.dumps(description_for(article, market), ensure_ascii=True).replace("<", "\\u003c")
    slug = html.escape(str(article["slug"]), quote=True)
    # Reuse the theme's installation guard: an existing listener stays active;
    # a theme without it gets a post-level fallback, without a second event.
    measurement = (Path(__file__).resolve().parents[1] / 'automation/retailer-measurement.js').read_text(encoding='utf-8')
    # The theme supplies a server-rendered fallback. This bridge uses the exact
    # generated description in the rendered head, without placing meta in body.
    return f'''{START}
<script class="wb-published-seo" data-wb-article="{slug}">
(function() {{
  if (!/\\/\\d{{4}}\\/\\d{{2}}\\/[^/]+\\.html$/.test(location.pathname)) return;
  var description = {description};
  [['name','description'],['property','og:description']].forEach(function(pair) {{
    var selector = 'meta[' + pair[0] + '="' + pair[1] + '"]';
    var tags = document.head.querySelectorAll(selector);
    var tag = tags[0] || document.createElement('meta');
    tag.setAttribute(pair[0], pair[1]); tag.setAttribute('content', description);
    if (!tags.length) document.head.appendChild(tag);
    for (var i=1; i<tags.length; i++) tags[i].remove();
  }});
}})();
</script>
<script class="wb-retailer-fallback">
{measurement}
</script>
{END}'''


def enrich_metadata(content: str, article: dict, market: str) -> str:
    return repair_affiliate_links(BLOCK.sub("", content), market, str(article['slug'])).rstrip() + "\n" + metadata_html(article, market)


def repair_metadata(client, post: dict, article: dict, market: str) -> dict:
    old = str(post.get("content") or "")
    content = enrich_metadata(old, article, market)
    if content == old:
        return post
    try:
        client.update_post_content(str(post["id"]), content)
        stored = client.get_post(str(post["id"]))
        if metadata_html(article, market) not in str(stored.get("content") or ""):
            raise RuntimeError("Blogger did not retain the generated metadata bridge")
        return stored
    except Exception as exc:
        print(f'[publication-warning] {market.upper()} {article["slug"]}: metadata/tracking repair unconfirmed ({type(exc).__name__}); retaining the published post')
        return post
