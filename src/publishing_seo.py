"""Non-visual metadata and regional measurement added at the publication boundary."""
from __future__ import annotations

import html
import json
import re

from src.seo import meta_description, plain_text

REVISION = "published-seo-v1"
START = "<!-- wb-published-seo:start -->"
END = "<!-- wb-published-seo:end -->"
BLOCK = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)


def description_for(article: dict, market: str) -> str:
    supplied = plain_text(str((article.get("_seo") or {}).get("description") or ""))
    return supplied or meta_description(article["title"], article["content_html"],
                                        "EBAY_GB" if market == "uk" else "EBAY_US")


def metadata_html(article: dict, market: str) -> str:
    description = json.dumps(description_for(article, market), ensure_ascii=True).replace("<", "\\u003c")
    slug = html.escape(str(article["slug"]), quote=True)
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
{END}'''


def enrich_metadata(content: str, article: dict, market: str) -> str:
    return BLOCK.sub("", content).rstrip() + "\n" + metadata_html(article, market)


def repair_metadata(client, post: dict, article: dict, market: str) -> dict:
    old = str(post.get("content") or "")
    content = enrich_metadata(old, article, market)
    if content == old:
        return post
    client.update_post_content(str(post["id"]), content)
    stored = client.get_post(str(post["id"]))
    if metadata_html(article, market) not in str(stored.get("content") or ""):
        raise RuntimeError("Blogger did not retain the generated metadata bridge")
    return stored
