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
    text = re.sub(r"\s+", " ", re.sub(r'[®™©]', '', title)).strip()
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


def product_mismatch_reason(title: str, query: str, market: str = '') -> str:
    """Explain confirmed role mismatches without rejecting included accessories.

    Only explicit accessory/region signals are used here. Unknown models remain
    subject to the existing relevance, price, seller and fallback checks.
    """
    text = re.sub(r'\s+', ' ', title).casefold()
    topic = query.casefold().replace('-', ' ')
    core = re.split(r'\b(?:with|including|includes|supplied with)\b', text, maxsplit=1)[0]
    if _BROKEN.search(text):
        return 'broken item or packaging rather than a working product'
    if re.search(r'\bbattery\s+(?:chargers?|maintainers?)\b', topic) and not re.search(r'\bjump[ -]?starters?\b', topic):
        jump_identity = re.search(r'\b(?:jump[ -]?starters?|jumper\s+(?:box|pack))\b', core)
        # A portable starting pack may append "battery charger" to its headline
        # because it also charges USB devices. Keep explicit mains combination
        # chargers, and chargers supplied with a separate starting accessory.
        mains_charger = (re.search(r'\b(?:mains|(?:110|120|230|240)\s*v\s*ac)\b', core)
                         and re.search(r'\bbattery\s+charger\b', core)
                         and not re.search(r'\b(?:power\s*bank|\d+\s*mah|jumper\s+box)\b', core))
        if jump_identity and not mains_charger:
            return 'portable jump starter rather than a battery charger or maintainer'
    if streaming_query(topic) and not any(x in topic for x in ('webcam', 'microphone', 'headset')):
        if not streaming_player(title):
            return 'streaming accessory rather than a complete player'
    if 'air purifier' in topic or 'air cleaner' in topic:
        identity = re.search(r'\b(?:air purifier|air cleaner)\b', core)
        accessory = re.search(r'\b(?:filter|filters|refill|refills|wire kit|capsule|capsules)\b', core)
        if accessory and (not identity or accessory.start() < identity.start()
                          or re.search(r'\b(?:replacement|refill|refills|wire kit|capsules?)\b', core)):
            return 'air-purifier accessory or consumable'
        if re.search(r'\b(?:in.car|car air|vehicle)\b', core) and 'car' not in topic:
            return 'vehicle purifier in a home air-purifier guide'
    if 'coffee' in topic or 'espresso' in topic:
        if re.search(r'\b(?:adapters? kit|filter baskets? kit|basket plus|replacement (?:carafe|filter)|pods? only)\b', core):
            return 'coffee-machine accessory rather than a brewer'
    if 'cordless vacuum' in topic and re.search(r'\bpool\b', core) and 'pool' not in topic:
        return 'pool cleaner rather than a household vacuum'
    if 'cordless vacuum' in topic and 'car' not in topic and re.search(r'\b(?:small mini|mini portable car|handheld only)\b', core):
        return 'mini car-cleaning vacuum rather than the household floor-cleaner recommendation'
    if 'dehumidifier' in topic and re.search(r'\b(?:damp trap|moisture trap|moisture absorber|refill crystals)\b', core):
        return 'passive moisture absorber rather than an electric dehumidifier'
    if 'earbud' in topic and re.search(r'\b(?:charging (?:stand|pad)|wireless (?:fast )?charging pad|case only)\b', core):
        return 'charger or case rather than earbuds'
    if 'slow cooker' in topic and re.search(r'\bsous[ -]?vide\b', core):
        return 'immersion circulator rather than a slow cooker'
    if 'food processor' in topic and re.search(r'\b(?:attachment|replacement (?:bowl|blade)|bowl only|blade only)\b', core):
        return 'processor attachment or spare rather than a standalone appliance'
    if 'straightener' in topic and re.search(r'\b(?:power supply|charging cable|power cord|replacement plates)\b', core):
        return 'straightener power supply or spare rather than a styler'
    if 'toothbrush' in topic and re.search(r'\b(?:smart handle|handle only|replacement handle|heads? only)\b', core):
        return 'toothbrush component rather than a complete brush kit'
    if 'doorbell' in topic and re.search(r'\b(?:add[ -]on chime|chime 2|chime only|indoor chime|mounting wedge|transformer only)\b', core):
        return 'doorbell chime or fitting rather than a video doorbell'
    if 'dash cam' in topic and 'discreet day/night vision camera' in core:
        return 'general surveillance camera without a dash-camera identity'
    if 'smart plug' in topic:
        if market == 'uk' and re.search(r'\b(?:eu|us) plug\b', text):
            return 'non-UK plug variant in a UK guide'
        if 'wireless remote control outlet' in core and not re.search(r'\b(?:wifi|wi-fi|app|alexa|google)\b', text):
            return 'remote-only outlet without the claimed smart-home connectivity'
    if 'power bank' in topic:
        for capacity in re.findall(r'\b([\d,]{6,})\s*mah\b', text):
            if int(capacity.replace(',', '')) > 200_000:
                return 'unsupported extreme battery-capacity claim'
    return ''
