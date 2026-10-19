"""Local, sourced buying advice for priority evergreen search topics."""
from __future__ import annotations

import copy
import html
import re

REVISION = 'priority-search-advice-v1'
TOPICS = {'air-fryers', 'large-capacity-air-fryers', 'smartwatches', 'battery-chargers', 'coffee-machines', 'slow-cookers'}


def air_fryer_advice(market, large=False):
    uk = market == 'uk'
    units = 'litres' if uk else 'quarts'
    intro = ('A large-capacity air fryer should make your usual family meal easier, rather than '
             'simply carry the biggest number on the box. Check how the usable space is divided '
             'before comparing prices.' if large else
             'Start with what you actually cook: one batch of chips, two parts of a meal, or '
             'food on several trays. A basket, dual-drawer model and air-fryer oven use their '
             'space differently, so their headline capacities are not a like-for-like comparison.')
    source = ('https://support.ninjakitchen.co.uk/hc/en-gb/article_attachments/5160587385500/AF400UK_IB_MP_210429_Mv3_LR.pdf'
              if uk else 'https://www.ninjakitchen.com/page/air-fryer')
    example = ('Ninja’s AF400UK manual describes SYNC as coordinating different cooking settings '
               'so both zones finish together. MATCH copies the same settings between zones.'
               if uk else
               'Ninja’s US range identifies Smart Finish and Match Cook as distinct dual-zone features. '
               'Check whether the exact model offers coordinated finishing, copied settings or both.')
    advice = (
        '<h2>How to choose an air fryer for your household</h2>'
        f'<p>{intro}</p>'
        '<h3>Single basket, dual drawer or air-fryer oven?</h3>'
        '<p>A single basket is worth comparing for meals cooked as one batch. Dual drawers let you '
        'separate two foods, but each drawer is smaller than the advertised combined capacity. '
        'An oven-style design offers racks or trays; check their usable dimensions and the '
        'manufacturer’s instructions for cooking on multiple levels.</p>'
        f'<h3>Capacity: look beyond the total {units}</h3>'
        '<p>Check basket or tray width, not only volume. A whole joint, several portions or flat food '
        'can need different shapes of usable space. Ask whether your normal meal fits without '
        'overcrowding or repeated batches. On a dual model, check each compartment separately. '
        'Measure counter depth and allow the clearances specified in the manual.</p>'
        '<h3>Two foods ready together: check the actual controls</h3>'
        '<p>Independent temperature settings, matching settings and synchronized finishing are '
        'different features. They matter when you want the main and side ready at the same time. '
        f'{example} <a href="{source}">Source: Ninja manufacturer guidance</a>. '
        'These are feature examples; they do not establish what another brand or model can do.</p>'
        '<h3>Cleaning and running costs can change the value</h3>'
        '<p>Check whether baskets, crisper plates and trays detach easily, whether replacement '
        'parts are available, and which parts the exact manual allows in a dishwasher. A viewing '
        'window may be convenient, but check how its surfaces are cleaned. Compare the complete '
        'meal rather than assuming a higher-wattage or larger machine always costs less to run.</p>'
        '<h3>New, open-box or refurbished: compare the whole offer</h3>'
        '<p>Check the stated condition, included trays and accessories, warranty and return window. '
        'A colour variant or another listing of the same model is an alternative offer, not '
        'evidence of a different-performing air fryer. Seller feedback concerns the seller; '
        'for cooking performance, look for comments about the exact model and food being cooked.</p>'
    )
    questions = [
        ('What size air fryer do I need?', 'Match the usable basket or tray to your normal meal. '
         'Check each drawer separately and consider whether you would need more than one batch.'),
        ('Is a dual-drawer air fryer better than a single basket?', 'It can be convenient for two '
         'foods with different settings, while a single basket may suit one larger item. Compare '
         'the space you can actually use and whether coordinated finishing is supported.'),
        ('Is an air-fryer oven the same as a basket air fryer?', 'Both may offer air-frying modes, '
         'but racks, trays and drawers have different usable spaces and cleaning requirements. '
         'Compare the exact appliance dimensions and instructions.'),
        ('Does an air fryer always use less electricity?', 'Do not assume a universal saving. '
         'Compare the cooking time, power used and number of batches needed for the same meal.'),
        ('What should I check on a refurbished air fryer?', 'Confirm condition, hygiene, included '
         'parts, warranty and returns. Do not treat a seller rating as a product-performance review.'),
    ]
    desc = (f'Compare {"large capacity " if large else ""}air fryers in the '
            f'{"UK" if uk else "USA"}: basket vs dual drawer vs oven, usable capacity, cleaning, '
            'warranty and current retailer prices.')
    return advice, questions, desc, ['air fryer for family meals', 'dual drawer vs single basket air fryer',
                                     'air fryer oven vs basket', 'air fryer usable capacity']


def smartwatch_advice(market):
    advice = (
        '<h2>How to choose a smartwatch that works with your phone</h2>'
        '<p>Phone compatibility comes before the price or the number of advertised features. '
        'A bargain watch is poor value if it cannot pair with your phone or use the features you need.</p>'
        '<h3>iPhone or Android: check the exact watch and software</h3>'
        '<p>Apple publishes a compatibility table covering the watch model, iPhone and software. '
        'For an older or refurbished watch, check its installed watchOS as well as the model: '
        'updated software can change the iPhone requirements. '
        '<a href="https://support.apple.com/en-euro/118490">Source: Apple’s compatibility table</a>.</p>'
        '<p>Google says Pixel Watch 2 needs Android 9.0 or newer and does not support iPhones. '
        'Other generations have different minimums. '
        '<a href="https://support.google.com/googlepixelwatch/answer/12652073?hl=en">'
        'Source: Google’s Pixel Watch compatibility guidance</a>. '
        'Check each Samsung or other-brand model separately rather than assuming all Android '
        'watches have the same requirements.</p>'
        '<h3>Bluetooth vs cellular: decide what you need away from your phone</h3>'
        '<p>Bluetooth and cellular variants are not interchangeable offers. If you want calls or '
        'data without carrying your phone, check the exact LTE model, regional support, carrier '
        'compatibility and ongoing plan cost. Do not pay for cellular hardware if your usual use '
        'is with the phone nearby.</p>'
        '<h3>Battery and comfort: compare your normal day</h3>'
        '<p>Ask whether your preferred display, notifications and workouts fit between charges. '
        'Seller battery claims are not our measured runtime. For used stock, ask about battery '
        'condition and confirm the charging equipment is included. Check case size, strap fit '
        'and replacement-strap availability before choosing by colour or screen size.</p>'
        '<h3>Refurbished watches: check pairing and returns</h3>'
        '<p>Confirm the previous owner’s account lock has been removed, that the watch can pair '
        'normally and that its condition matches the description. Check warranty and returns '
        'before buying. Seller feedback can help assess the transaction, but does not establish '
        'the remaining battery life or the reliability of that particular watch.</p>'
    )
    questions = [
        ('Can I use any smartwatch with an iPhone?', 'No. Check the manufacturer’s model-specific '
         'compatibility requirements. Pixel Watch does not support iPhone, and other brands vary.'),
        ('Will an older Apple Watch work with my iPhone?', 'Check the watch model and installed '
         'watchOS against Apple’s table. Software updates can change which iPhone is required.'),
        ('Is a cellular smartwatch worth paying extra for?', 'Consider it if you want supported '
         'calls or data away from the phone. Check carrier support and plan costs first.'),
        ('What should I check on a refurbished smartwatch?', 'Check account-lock removal, battery '
         'condition, included charger, pairing, cosmetic condition, warranty and returns.'),
    ]
    desc = f'Compare smartwatches in the {"UK" if market == "uk" else "USA"}: phone compatibility, Bluetooth vs cellular, battery checks and refurbished buying advice.'
    return advice, questions, desc, ['smartwatch for iPhone', 'smartwatch for Android',
                                    'Bluetooth vs cellular smartwatch', 'refurbished smartwatch checks']


def battery_advice(market):
    advice = (
        '<h2>How to choose a car battery charger or maintainer</h2>'
        '<p>Choose for the battery you actually have, not the biggest current number or a promise '
        'to repair every flat battery. Start with the vehicle and battery manufacturer’s requirements.</p>'
        '<h3>Check voltage and battery chemistry before price</h3>'
        '<p>A 12V, 24V or multi-voltage label is only part of the compatibility check. Flooded '
        'lead-acid, AGM and lithium batteries may require different charge modes. For example, '
        'NOCO’s GENIUS2 guidance separates 12V lead-acid, AGM and lithium modes, with its lithium '
        'mode specified for batteries with a Battery Management System. '
        '<a href="https://no.co/support/genius-battery-chargers/genius/genius2">'
        'Source: NOCO’s mode and compatibility guidance</a>. '
        'That example does not establish that the marketplace chargers above support the same batteries.</p>'
        '<h3>Charger, maintainer or jump starter?</h3>'
        '<p>These solve different problems. Compare a charger for replenishing a compatible battery '
        'and a supported maintenance mode for a vehicle kept parked. A jump starter is a separate '
        'type of product intended to assist starting. Confirm the exact functions in the manual '
        'rather than assuming one device does everything.</p>'
        '<h3>Charging current: match the battery, not the headline</h3>'
        '<p>Compare the supported battery capacity and recommended charging rate with the battery '
        'manufacturer’s requirements. A higher advertised amp rating is not automatically more '
        'suitable. Check input-power requirements, included clamps or leads, connectors and whether '
        'the manual permits the maintenance use you have in mind.</p>'
        '<h3>“Repair” claims need an exact-model check</h3>'
        '<p>A repair or reconditioning mode does not prove a damaged battery can be recovered. '
        'NOCO’s diagnostics distinguish incompatible voltage, a battery that may not hold charge '
        'and temperature conditions. Check the manufacturer’s troubleshooting instructions and '
        'have a suspect battery assessed rather than selecting equipment on a universal repair promise.</p>'
        '<h3>Check what the listing includes</h3>'
        '<p>Compare one unit with one unit: a two-pack is a different offer, not necessarily a '
        'different charger. Check the model, local mains compatibility, warranty, returns and '
        'whether replacement leads are available. Seller feedback describes transactions, not '
        'verification of the device’s charging protection or long-term durability.</p>'
    )
    questions = [
        ('Can I use the same charger for AGM and lithium batteries?', 'Only if the exact charger '
         'and battery instructions support those chemistries and their required modes. Do not '
         'assume compatibility from the voltage alone.'),
        ('Is a battery maintainer the same as a jump starter?', 'No. Maintenance charging and '
         'assistance with starting are different uses. Check the exact product’s supported function.'),
        ('Is a higher-amp car battery charger always better?', 'No. Match charging current and '
         'supported capacity to the battery manufacturer’s requirements and the charger manual.'),
        ('Can a repair mode restore any dead battery?', 'No universal recovery claim is justified. '
         'Follow exact-model diagnostics and have a suspect battery assessed.'),
    ]
    desc = f'Compare car battery chargers in the {"UK" if market == "uk" else "USA"}: voltage, AGM and lithium compatibility, charger vs maintainer, current and buying checks.'
    return advice, questions, desc, ['car battery charger vs maintainer', 'AGM battery charger',
                                    'lithium battery charger compatibility', '12V car battery charger']


def coffee_advice(market):
    uk = market == 'uk'
    advice = (
        '<h2>How to choose a coffee machine for your kitchen</h2>'
        '<p>The best-value machine is the one that makes your usual drink without turning every '
        'morning into a project. Start with the number of cups, how you like your coffee and '
        'how much preparation and cleaning you are happy to do.</p>'
        '<h3>Filter, espresso, bean-to-cup or pods?</h3>'
        '<p>A filter machine is worth comparing when you want a jug of black coffee for several '
        'people. A manual espresso machine suits someone willing to learn dosing and preparation; '
        'check whether a grinder is included or needs buying separately. Bean-to-cup machines '
        'reduce some preparation but still need cleaning. Pods can simplify drink preparation, '
        'but check the compatible capsules, their ongoing cost and the drinks the exact model makes.</p>'
        '<p>Check the coffee format as carefully as the machine price. De’Longhi’s guidance, '
        'for example, distinguishes coarser ground coffee for filter machines from finer espresso '
        'grounds and says instant coffee should not be used in its machines. '
        '<a href="https://www.delonghi.com/en-gb/faqs/Can-I-use-instant-coffee-in-my-coffee-machine/a/8441">'
        'Source: De’Longhi coffee-format guidance</a>. Follow the instructions for your exact model.</p>'
        '<h3>A coffee machine for a small kitchen: measure the working space</h3>'
        '<p>Measure width, depth and the height beneath cupboards. Then allow room to lift a water '
        'tank, open a bean hopper or filter lid and remove the drip tray. A compact footprint is '
        'less helpful if the machine must be pulled out every time you refill it. Check your '
        'normal mug height and the manufacturer’s installation clearances too.</p>'
        '<h3>Milk drinks: think about the second cup</h3>'
        '<p>For regular cappuccinos or lattes, check whether the machine has a steam wand, an '
        'automatic milk system or requires a separate frother. Consider the steps needed to '
        'prepare two drinks and clean the milk parts afterwards. A pump-pressure headline alone '
        'does not tell you how convenient the whole routine will be.</p>'
        '<h3>Compare the cost per morning, not just the machine</h3>'
        '<p>Add the likely cost of beans, ground coffee or capsules, plus any grinder, filters '
        'and manufacturer-approved maintenance supplies. Count the drinks you actually make '
        'each week. A cheaper appliance can become the more expensive choice if its consumables '
        'cost more or you need extra equipment to make your preferred drink.</p>'
        '<h3>Cleaning and refurbished buying checks</h3>'
        '<p>Check access to removable parts, the descaling instructions and availability of '
        'replacement filters, jugs or seals. For refurbished stock, confirm condition, included '
        'accessories, warranty and returns; an espresso machine missing its portafilter or milk '
        'jug may need additional spending. Product reviews are most useful when they describe '
        'the exact model, drink and cleaning routine you plan to use.</p>'
    )
    questions = [
        ('Is a filter coffee maker better than an espresso machine?', 'Choose by the drink and '
         'routine you want. Filter coffee suits a jug of black coffee; espresso preparation and '
         'milk drinks involve different equipment, ingredients and cleaning.'),
        ('What should I check for a coffee machine in a small kitchen?', 'Check cupboard height '
         'as well as the footprint, access for refilling and cleaning, cup clearance and the '
         'manufacturer’s installation requirements.'),
        ('Does an espresso machine include a grinder?', 'Some do and some do not. Check the exact '
         'listing and supported coffee format, then include a suitable grinder in the budget if needed.'),
        ('Are pod machines always cheaper to use?', 'Compare the cost of compatible capsules with '
         'the beans or grounds for your usual number of drinks. Purchase price alone cannot settle it.'),
        ('What matters when buying a refurbished coffee maker?', 'Confirm the exact model, '
         'condition, included brewing and milk accessories, cleaning requirements, warranty and returns.'),
    ]
    desc = (f'Compare coffee {"machines in the UK" if uk else "makers in the USA"}: filter vs espresso, '
            'small-kitchen fit, milk drinks, running costs and refurbished buying checks.')
    return advice, questions, desc, ['filter vs espresso coffee machine', 'coffee machine for small kitchen',
                                     'coffee maker running costs', 'refurbished coffee machine checks']


def slow_cooker_advice(market):
    units = 'litres' if market == 'uk' else 'quarts'
    advice = (
        '<h2>How to choose a slow cooker for everyday meals</h2>'
        '<p>Think about the meal you want ready when you get home, how many people it needs to '
        'feed and where the cooker will sit. A larger pot is useful only if it suits your normal '
        'recipes and you have room to lift, wash and store it.</p>'
        f'<h3>Capacity in {units}: compare the pot, not just the headline</h3>'
        '<p>Check the usable fill range in the exact manual rather than treating the advertised '
        'capacity as a serving guarantee. A deep round pot and a wide oval pot can accommodate '
        'different ingredients. For batch cooking, consider how you will portion and store the '
        'finished meal as well as how much fits inside the cooker.</p>'
        '<h3>Manual dial or programmable timer?</h3>'
        '<p>A simple dial may suit a routine where someone is home to switch the cooker off. '
        'A programmable model is worth comparing when you need a defined cooking time, but check '
        'what happens afterwards: automatic keep-warm, a manual warm setting and delayed start '
        'are different functions. Do not assume that every digital display includes all three.</p>'
        '<p>For example, Crock-Pot describes its manual 8-quart model as offering High, Low and '
        'Warm settings. That is a control example for that model, not proof that every listing '
        'above has a timer or automatic keep-warm. '
        '<a href="https://www.crock-pot.com/slow-cookers/7-quart-up/crock-pot-manual-8-quart-slow-cooker/SP_528880.html">'
        'Source: Crock-Pot manual 8-quart model specifications</a>.</p>'
        '<h3>Searing, cleaning and the weight of a full pot</h3>'
        '<p>If you want to brown ingredients in the same vessel, confirm that the exact insert '
        'is approved for your hob or stove. A removable bowl alone does not establish this. '
        'Check which parts are dishwasher-safe, how the handles are held and whether the pot '
        'fits in your sink. Follow the model instructions for cooking and cleaning.</p>'
        '<h3>Compare running costs for your actual recipe</h3>'
        '<p>Compare power use and cooking time for the same meal; a low wattage label alone '
        'does not establish the total cost. A slow cooker and a pressure multi-cooker also '
        'offer different cooking methods. Choose the functions you will use rather than '
        'paying for a longer mode list.</p>'
        '<h3>What makes a cheaper offer worth buying?</h3>'
        '<p>Check the model number, pot and lid condition, included accessories, local voltage, '
        'warranty and returns. With used or refurbished stock, a replacement pot or lid can '
        'change the apparent saving. Reviews are most useful when they discuss the exact model, '
        'normal meal size, controls and cleaning; seller feedback concerns the transaction.</p>'
    )
    questions = [
        ('What size slow cooker should I buy?', 'Compare your usual recipe and the manufacturer’s '
         'recommended fill range. Headline capacity alone does not guarantee a number of servings.'),
        ('Does a slow cooker switch to warm automatically?', 'Only some models do. Check the exact '
         'controls and what happens at the end of the cooking time before relying on this feature.'),
        ('Can I brown ingredients in the slow cooker pot?', 'Only when the manufacturer approves '
         'the exact insert for that hob or stove. Removable does not automatically mean hob-safe.'),
        ('Is a slow cooker the same as a pressure cooker?', 'No. A multi-cooker may offer both '
         'methods, but check the supported modes and recipe instructions for the appliance.'),
    ]
    description = (f'Compare slow cookers in the {"UK" if market == "uk" else "USA"}: capacity, '
                   'manual vs programmable controls, keep-warm, cleaning and current retailer offers.')
    return advice, questions, description, ['slow cooker size', 'manual vs programmable slow cooker',
                                          'slow cooker keep warm', 'slow cooker buying guide']


def topic_fragments(topic, market):
    if topic in {'air-fryers', 'large-capacity-air-fryers'}:
        return air_fryer_advice(market, topic == 'large-capacity-air-fryers')
    if topic == 'smartwatches':
        return smartwatch_advice(market)
    if topic == 'coffee-machines':
        return coffee_advice(market)
    if topic == 'slow-cookers':
        return slow_cooker_advice(market)
    return battery_advice(market)


def enhance_topic_advice(article, market):
    topic = (article.get('_generator') or {}).get('topic')
    if market not in {'uk', 'us'} or topic not in TOPICS:
        return article
    # Event and supporting pages retain their own intent and publication rules.
    generator = article.get('_generator') or {}
    if article.get('_event') or generator.get('prime_amazon_only') or generator.get('content_type') == 'authority-support':
        return article
    result = copy.deepcopy(article)
    advice, questions, description, keywords = topic_fragments(topic, market)
    start = f'<!-- wb-topic-advice:{topic}:start -->'
    end = f'<!-- wb-topic-advice:{topic}:end -->'
    fs = f'<!-- wb-topic-faq:{topic}:start -->'
    fe = f'<!-- wb-topic-faq:{topic}:end -->'
    advice = start + advice + end
    faq = fs + '<h2>Buying questions answered</h2>' + ''.join(
        f'<h3>{html.escape(q)}</h3><p>{html.escape(a)}</p>' for q, a in questions
    ) + fe
    content = str(result.get('content_html') or '')
    if start in content and end in content:
        content = re.sub(re.escape(start) + '.*?' + re.escape(end), lambda _: advice, content, flags=re.S)
    elif '<h2>How to choose the right option</h2>' in content:
        content = re.sub(r'<h2>How to choose the right option</h2>.*?(?=<h2>)', lambda _: advice, content, count=1, flags=re.S)
    else:
        content = advice + content
    if fs in content and fe in content:
        content = re.sub(re.escape(fs) + '.*?' + re.escape(fe), lambda _: faq, content, flags=re.S)
    elif '<h2>Frequently asked questions</h2>' in content:
        content = re.sub(r'<h2>Frequently asked questions</h2>.*?(?=<p style="margin:18px 0"|<h2>|</div>\s*<script|$)',
                         lambda _: faq, content, count=1, flags=re.S)
    else:
        content = faq + content
    result['content_html'] = content
    seo = result.setdefault('_seo', {})
    seo['description'] = description
    seo['editorial_revision'] = REVISION
    seo['secondary_keywords'] = list(dict.fromkeys(list(seo.get('secondary_keywords') or []) + keywords))
    return result

