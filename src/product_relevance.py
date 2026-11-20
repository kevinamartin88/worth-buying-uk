"""Offline product-role checks shared by the UK and USA streaming guides."""
from __future__ import annotations

import re


def streaming_query(query: str) -> bool:
    return bool(re.search(r"\bstreaming\b", query, re.I))


_PLAYER = re.compile(
    r"\b(?:roku\s+(?:streaming\s+stick|express|ultra|premiere|streambar)|"
    r"fire\s+tv\s+(?:stick|cube)|chromecast|apple\s+tv\s+(?:4k|hd)|"
    r"nvidia\s+shield\s+tv|google\s+tv\s+streamer|"
    r"(?:android|google)\s+tv\s+(?:box|streamer)|"
    r"(?:4k\s+)?streaming\s+(?:media\s+)?(?:player|box|device))\b", re.I
)
_ACCESSORY = re.compile(
    r"\b(?:remote|remotes|cord|cords|cable|cables|adapter|adapters|charger|"
    r"charging|power\s+supply|mount|mounts|bracket|case|cover|battery|batteries|"
    r"replacement|extender|extension)\b", re.I
)
_BROKEN = re.compile(
    r"\b(?:for\s+parts|not\s+working|faulty|broken|empty\s+box|box\s+only|"
    r"manual\s+only|spares\s*(?:or|and|/|&)\s*repairs?)\b", re.I
)


def streaming_player(title: str) -> bool:
    """Require the advertised item to be a player, not its compatible accessory.

    A player's supplied remote/cable is allowed after a bundle word. Names after
    'for' or 'compatible with' cannot establish the identity of an accessory.
    """
    text = re.sub(r"\s+", " ", title).strip()
    if _BROKEN.search(text):
        return False
    core = re.split(r"\b(?:compatible\s+with|for|fits|with|including|includes)\b", text, maxsplit=1, flags=re.I)[0]
    player = _PLAYER.search(core)
    if not player:
        return False
    accessory = _ACCESSORY.search(core)
    if not accessory:
        return True
    if accessory.start() < player.start() or re.search(r"\bonly\b|\breplacement\b", core, re.I):
        return False
    # Some complete-player headlines list a voice remote without the word
    # 'with'. Keep explicit player/device headlines, but reject ambiguous
    # 'Roku Streaming Stick remote control' accessory titles.
    return bool(re.search(r"\b(?:device|player|box)\b", core[:accessory.start()], re.I))


def streaming_player_aspects(item: dict) -> bool:
    """Reject a contradictory retailer Type even when the title names a player."""
    for aspect in item.get('localizedAspects') or []:
        if str(aspect.get('name') or '').casefold() != 'type':
            continue
        value = str(aspect.get('value') or '')
        core = re.split(r"\b(?:with|including|includes)\b", value, maxsplit=1, flags=re.I)[0]
        if _ACCESSORY.search(core):
            return False
    return True
