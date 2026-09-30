from __future__ import annotations

import re


_AFFILIATE_LINK_LABEL = re.compile(
    r"(?im)^(?:ad\s*/\s*)?affiliate\s*🔗\s*",
)


def clean_social_template(template: str) -> str:
    """Remove repeated disclosure labels while retaining the destination link."""
    return _AFFILIATE_LINK_LABEL.sub("Read the guide 🔗 ", template)
