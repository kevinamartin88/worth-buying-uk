"""Persistent buying advice for six pages selected from Search Console.

Local copy adds no API dependency to publishing. Dates, offers and promotion
tokens remain owned by their existing generators.
"""
from __future__ import annotations

import copy
import html
import re

REVISION = 'search-focus-2026-10-28'
START = '<!-- wb-search-focus:start -->'
END = '<!-- wb-search-focus:end -->'
FAQ_START = '<!-- wb-search-focus-faq:start -->'
FAQ_END = '<!-- wb-search-focus-faq:end -->'


def section(heading, paragraphs):
    return '<h2>' + heading + '</h2>' + ''.join(paragraphs)


FOCUS = {
    ('uk', 'best-tvs-worth-buying-uk-2026'): {
        'topic': 'tvs',
        'title': 'TV Buying Guide UK: Screen Size, Gaming & Refurbished Checks',
        'description': 'Compare UK TVs for everyday viewing and gaming. Check screen size, HDMI features, stand width, panel condition and the full delivered price.',
        'intro': 'Choosing a TV for a living room or a console? Compare the space it must fit, the connections you will use and the condition of the actual set before judging the price.',
        'heading': 'Which TV features are worth paying for?',
        'paragraphs': [
            '<h3>For everyday viewing: check fit and the apps you use</h3><p>Measure the available width and the spacing of the feet, not just the diagonal screen size. Leave the ventilation space required by the manual. Check that the exact UK model supports your usual streaming and catch-up services; a familiar smart-TV logo does not settle app availability or how long it will be supported.</p>',
            '<h3>For gaming: a 4K label does not mean 4K at 120Hz</h3><p>Check the supported input signal, refresh rate, VRR and HDMI port together. Samsung specifies 4K at 60Hz on the HDMI inputs of its 50-inch U8000F, so it should not be bought on the assumption of 4K/120Hz input. <a href="https://www.samsung.com/uk/tvs/uhd-4k-tv/u8000f-50-inch-crystal-uhd-4k-smart-tv-ue50u8000fkxxu/">Source: Samsung UE50U8000F specifications</a>. Check every other shortlisted model separately. A console-compatible cable cannot add a feature the TV lacks.</p>',
            '<h3>For discounted or refurbished sets: inspect the panel first</h3><p>A scratch on the casing and discolouration on the screen are different compromises. Ask for photographs of the actual set showing a plain picture, confirm the remote and feet are included, and read the panel-fault and return terms. A low price is less attractive if a visible defect will bother you every evening or return shipping is expensive.</p>',
            '<h3>Include the cost of the complete setup</h3><p>Add delivery, any bracket or replacement feet, and sound equipment you actually need. Before buying a soundbar, compare the TV output with the soundbar input. Our <a href="https://www.worthbuyinguk.co.uk/2026/09/best-soundbars-worth-buying-in-uk-2026.html">UK soundbar buying guide</a> explains the next set of checks. Choose the complete setup rather than the biggest screen that fits the initial budget.</p>',
        ],
        'questions': [
            ('Does every 4K TV support 120Hz gaming?', 'No. Check the exact model and HDMI input specifications for the resolution and refresh rate your console or PC needs.'),
            ('What should I ask about a refurbished TV?', 'Ask about panel marks or discolouration, photographs of the actual set, included remote and stand, warranty, and the cost and conditions of returns.'),
            ('Is a larger TV always better value?', 'Only if it fits your viewing space and needs. Include stand width, installation, delivery and any missing accessories in the comparison.'),
        ],
    },
    ('uk', 'best-tablets-worth-buying-uk'): {
        'topic': 'tablets',
        'title': 'Tablets UK: Streaming, Study & Refurbished Buying Guide',
        'description': 'Choose a UK tablet for streaming or study. Compare software support, storage, Wi-Fi vs cellular, accessories and refurbished condition.',
        'intro': 'A tablet for watching films, schoolwork and replacing a laptop can mean three different purchases. Start with the apps and accessories you need, then compare the exact model and its supported software.',
        'heading': 'Choose a tablet around the job it needs to do',
        'paragraphs': [
            '<h3>Streaming and browsing: check the screen and supported apps</h3><p>Look at the screen specification, speakers, weight and the streaming service requirements for the exact model. Do not infer streaming quality from an Android version or a large memory figure in a marketplace title. A stand or case may matter more for watching a film than storage you will never fill.</p>',
            '<h3>Study and work: price the keyboard and software too</h3><p>Check whether your required apps work on Android, iPadOS or Windows before comparing prices. A tablet advertised with keyboard options may not include a keyboard in the selected offer. Check the stylus model, charging arrangement and whether your course or workplace requires desktop software. An inexpensive tablet is poor value if it cannot run the application you need.</p>',
            '<h3>Software support and storage: match the model number</h3><p>Ask for the model code and installed software, then check the manufacturer support page. Samsung publishes a model-specific update history for the Galaxy Tab A9+ SM-X210; this is more useful than a seller simply calling a device new. <a href="https://doc.samsungmobile.com/SM-X210/028545240104/eng.html">Source: Samsung SM-X210 software history</a>. Check physical storage separately from memory-card expansion, and physical RAM separately from virtual memory. Do not assume a headline capacity is all built in.</p>',
            '<h3>Used stock: battery, accounts and connectivity</h3><p>Confirm battery condition, charging equipment, reset and account-lock removal, and the return window. Wi-Fi-only and cellular versions are different offers; a reference to 5G Wi-Fi does not establish mobile-network support. Check the exact model, SIM support and network compatibility if you need data away from home. For charging on the move, compare connectors and output requirements in our <a href="https://www.worthbuyinguk.co.uk/2026/10/best-power-banks-worth-buying-in-uk-2026.html">UK power bank guide</a>.</p>',
        ],
        'questions': [
            ('Can a tablet replace a laptop for studying?', 'Check the exact applications, keyboard, file handling and external-device requirements of your course. A tablet can suit some tasks without supporting every desktop application.'),
            ('Does 5G in a tablet listing mean it takes a SIM?', 'Not necessarily. Check the model specification for cellular and SIM support; a seller may be describing Wi-Fi connectivity.'),
            ('What should I check on a refurbished tablet?', 'Check software support, battery and screen condition, account-lock removal, real storage, included charger, warranty and returns.'),
        ],
    },
    ('uk', 'best-tyre-inflators-worth-buying-uk'): {
        'topic': 'tyre-inflators',
        'title': 'Tyre Inflators UK: Cordless vs 12V Buying Guide',
        'description': 'Compare cordless and 12V tyre inflators for UK cars. Check hose reach, power, gauge accuracy, duty cycle and what is included before buying.',
        'intro': 'For topping up car tyres at home, a useful inflator needs to reach the valves, use a power source you can rely on and show pressure clearly. The biggest maximum-PSI number is not the most useful comparison.',
        'heading': 'Cordless or 12V: which tyre inflator fits your routine?',
        'paragraphs': [
            '<h3>Cordless convenience versus a car-socket supply</h3><p>A cordless model avoids routing a cable through the car, but its battery must be charged when you need it. A 12V model avoids that battery-maintenance task but needs a compatible socket and enough cable. Check the inflator manual and vehicle socket limits. A USB charging connection does not prove the inflator can run directly from USB.</p>',
            '<h3>Hose reach and gauge accuracy matter in normal use</h3><p>Check whether the hose reaches a valve at the top of the wheel without hanging the pump from the connector. Compare the display units, gauge specification and any auto-stop setting. Confirm pressure with a suitable gauge rather than treating automatic stopping as proof of accuracy. Follow the manufacturer duty-cycle and cooling instructions when inflating several tyres.</p>',
            '<h3>Choose the right pressure, not the pump maximum</h3><p>Use the vehicle manufacturer pressure for the load and tyre size, usually shown on the vehicle label or in its handbook. Michelin recommends checking cold tyres and comparing against that vehicle recommendation, rather than choosing a pressure from the tyre sidewall. <a href="https://www.michelin.co.uk/auto/advice/tyre-pressure/inflate-tyres">Source: Michelin inflation guidance</a>. An inflator cannot repair tyre damage or establish that a repeatedly deflating tyre is safe.</p>',
            '<h3>What owner feedback can help you check</h3><p>On Ring’s RTC6000 product page, owner comments include positive reports about ease of use and a complaint about hose reach at an awkward valve position. These are individual experiences with that exact model, rather than a reliability score for every Ring inflator. <a href="https://shop.ringautomotive.com/rtc6000-cordless-digital-tyre-inflator-and-air-pump.html">Read the RTC6000 owner reviews</a>. Confirm the model number before applying those comments to a listing. For a separate starting problem, see our <a href="https://www.worthbuyinguk.co.uk/2026/09/best-car-jump-starters-worth-buying.html">car jump starter guide</a>; tyre inflation and jump starting are different jobs.</p>',
        ],
        'questions': [
            ('Is a cordless tyre inflator better than a 12V model?', 'Cordless can be easier to move around the car, while a compatible 12V model avoids relying on a charged internal battery. Compare reach, runtime, socket requirements and your routine.'),
            ('Does a higher maximum PSI mean faster inflation?', 'Not by itself. Compare the stated test conditions, supported tyre sizes, inflation performance and duty cycle, rather than maximum pressure alone.'),
            ('Can I use one pressure setting for every car?', 'No. Follow the vehicle manufacturer pressure recommendation for the tyre size and load, and check cold tyres as instructed.'),
        ],
    },
    ('us', 'best-cordless-drills-worth-buying-us'): {
        'topic': 'cordless-drills',
        'title': 'Cordless Drills USA: Bare Tool vs Kit Buying Guide',
        'description': 'Compare US cordless drills for home DIY. Check bare-tool vs kit costs, battery compatibility, chuck size, drilling modes and refurbished accessories.',
        'intro': 'The cheapest drill body is not always the cheapest way to finish a DIY job. Compare a usable kit: drill, compatible battery, charger and the bits or attachments your job needs.',
        'heading': 'How to compare a cordless drill kit with a bare tool',
        'paragraphs': [
            '<h3>Already own batteries? Start with the platform</h3><p>A bare tool can make sense when you already own a compatible battery and charger. Otherwise add both to the price before comparing it with a kit. DEWALT identifies the DCD777B as a tool-only drill/driver with battery and charger sold separately. <a href="https://www.dewalt.com/en-us/product/dcd777b/20v-max-12-compact-drilldriver-tool-only">Source: DEWALT DCD777B product details</a>. A marketplace seller may offer its own bundle, so check the selected listing contents too.</p>',
            '<h3>Drill/driver, hammer drill or impact driver?</h3><p>Choose for the material and fastener, rather than assuming these names are interchangeable. Check the exact tool manual for drilling modes, supported materials and bit requirements. A multi-attachment drill can be useful around corners, but an attachment count does not prove hammer-drilling capability. Chuck size also determines which bit shanks it accepts.</p>',
            '<h3>Compact access versus a bigger specification</h3><p>For furniture assembly and tight cupboards, compare head length, grip and the weight with a battery fitted. Bosch’s GSR12V-140FCB22 system includes right-angle and offset attachments for access in confined spaces. <a href="https://www.boschtools.com/us/en/products/gsr12v-140fcb22-06019F6010">Source: Bosch Flexiclick specifications</a>. Confirm those attachments are supplied with a refurbished offer; the original kit description is not a guarantee of secondhand contents.</p>',
            '<h3>A practical way to compare the total cost</h3><p>For illustration, a $60 bare tool plus a $50 compatible battery-and-charger package costs $110 before bits, delivery and tax. A $100 kit may therefore be the cheaper starting point. Those are example figures, not current offers. Conversely, if you already own the required battery and charger, the bare tool may avoid buying duplicates. Keep model, battery condition, warranty and return terms in the comparison. Planning a separate outdoor-cleaning job? Our <a href="https://www.worthbuyingusa.com/2026/10/best-pressure-washers-worth-buying-in.html">USA pressure washer guide</a> applies the same complete-kit comparison to hoses and accessories.</p>',
        ],
        'questions': [
            ('What does tool only mean on a cordless drill?', 'It normally means the tool body is supplied without the battery and charger. Check the exact seller bundle and budget for compatible power equipment.'),
            ('Is a drill/driver the same as a hammer drill?', 'No. Check the exact model drilling modes and supported materials in its manual; do not infer hammer capability from the voltage or attachment count.'),
            ('Is a refurbished drill kit worth considering?', 'Compare the included battery, charger and attachments, their condition, warranty and returns with the complete price of a new equivalent.'),
        ],
    },
    ('us', 'best-pressure-washers-worth-buying-us'): {
        'topic': 'pressure-washers',
        'title': 'Pressure Washers USA: PSI, GPM & Buying Guide',
        'description': 'Choose a US pressure washer for cars, patios or driveways. Compare rated PSI and GPM, electric vs gas, hose reach, accessories and total cost.',
        'intro': 'A pressure washer for a car and one for a large driveway can be very different purchases. Use PSI and GPM together, then check reach, attachments and the practical cost of owning the machine.',
        'heading': 'Before choosing a pressure washer: three buying decisions',
        'paragraphs': [
            '<h3>Occasional car cleaning or a large paved area?</h3><p>For a car, prioritize a suitable adjustable spray, manageable hose and the surface instructions. For a large paved area, compare rated water flow and a compatible surface-cleaner attachment as well as pressure. A high advertised maximum PSI is not a promise of faster cleaning in every setting.</p>',
            '<h3>Compare like-for-like performance claims</h3><p>Check whether pressure and flow figures are rated together under the same conditions. Do not multiply a peak PSI claim by an unrelated maximum GPM figure and treat the result as a measured performance score. Manufacturer specifications, retailer titles and independent test results are different forms of evidence.</p>',
            '<h3>Price the accessories you will actually use</h3><p>Add a suitable hose, any required adapters, surface cleaner and delivery before choosing between bundles. Check whether the accessory connection matches the exact model. Our <a href="https://www.worthbuyingusa.com/2026/10/best-carpet-cleaners-worth-buying-in.html">carpet cleaner buying guide</a> covers a separate indoor-cleaning job; outdoor pressure washers are not a substitute for carpet-cleaning equipment.</p>',
        ],
        'questions': [],
    },
    ('us', 'best-slow-cookers-worth-buying-us'): {
        'topic': 'slow-cookers',
        'title': 'Slow Cookers USA: Size, Timers & Running Costs',
        'description': 'Choose a US slow cooker for your household. Compare usable quart capacity, manual vs programmable controls, keep-warm, cleaning and running costs.',
        'intro': 'Choose a slow cooker around your normal meal and routine: a manageable pot, controls you will actually use and clear cleaning instructions matter more than the longest feature list.',
        'heading': 'Small household, batch cooking or a meal ready after work?',
        'paragraphs': [
            '<h3>For a small household: avoid buying capacity you cannot use</h3><p>Check the manufacturer recommended fill range against your normal recipe. A larger cooker is not automatically better for small portions. For batch cooking, consider how a full pot will be lifted, cleaned and stored, and how the finished food will be portioned according to appropriate food-safety guidance.</p>',
            '<h3>For a working day: check what the timer actually does</h3><p>Programmable cooking and automatic keep-warm can be useful, but confirm the behavior of the exact model at the end of the cooking time. A manual Warm setting is not proof of automatic switching. Use model and recipe instructions rather than assuming a display or a timer makes any unattended cooking plan suitable.</p>',
            '<h3>A running-cost example you can adapt</h3><p>Electricity cost is energy used in kWh multiplied by your tariff per kWh. If a cooker averaged 0.2kW for six hours, the example would use 1.2kWh; at $0.20 per kWh, that would cost $0.24. This is arithmetic using assumed figures, not a measured result for the products above. A rated wattage is not necessarily the average draw while a thermostat cycles.</p>',
            '<h3>Choose the cooking method before adding more appliances</h3><p>A slow cooker may suit a meal prepared ahead of time; an air fryer serves a different routine when you want a shorter cooking session and a different finish. Compare our <a href="https://www.worthbuyingusa.com/2026/09/best-air-fryers-worth-buying-in-usa-2026.html">USA air fryer buying guide</a> if that better matches your meals. Base the choice on your recipe and cleaning routine, rather than an assumed universal energy saving.</p>',
        ],
        'questions': [],
    },
}


def enhance_search_focus(article: dict, market: str) -> dict:
    config = FOCUS.get((market, article.get('slug')))
    generator = article.get('_generator') or {}
    if (not config or generator.get('topic') != config['topic'] or article.get('_event')
            or generator.get('prime_amazon_only') or generator.get('content_type') == 'authority-support'):
        return article
    result = copy.deepcopy(article)
    content = str(result.get('content_html') or '')
    intro = '<p><strong>' + html.escape(config['intro']) + '</strong></p>'
    # The generator's opening sales summary is always the first strong paragraph.
    # Do not alter price-checked paragraphs, product cards or the review methodology.
    if re.match(r'^\s*<p><strong>.*?</strong></p>', content, re.S):
        content = re.sub(r'^\s*<p><strong>.*?</strong></p>', lambda _: intro, content, count=1, flags=re.S)
    else:
        # USA buying-card articles wrap the intro after a dated badge. Replace
        # only the generated shopping summary, leaving that badge untouched.
        content = re.sub(r'<p><strong>Shopping for .*?</strong></p>', lambda _: intro,
                         content, count=1, flags=re.S)
    block = START + section(config['heading'], config['paragraphs']) + END
    if START in content and END in content:
        content = re.sub(re.escape(START) + '.*?' + re.escape(END), lambda _: block, content, flags=re.S)
    elif '<h2>How to choose the right option</h2>' in content:
        content = re.sub(r'<h2>How to choose the right option</h2>.*?(?=<h2>|$)', lambda _: block,
                         content, count=1, flags=re.S)
    else:
        # Already researched pressure-washer/slow-cooker advice stays intact.
        marker = '<h2>Current picks worth comparing</h2>'
        content = content.replace(marker, block + marker, 1) if marker in content else content + block
    if config['questions']:
        faq = FAQ_START + '<h2>Buying questions answered</h2>' + ''.join(
            '<h3>' + html.escape(q) + '</h3><p>' + html.escape(a) + '</p>'
            for q, a in config['questions']) + FAQ_END
        if FAQ_START in content and FAQ_END in content:
            content = re.sub(re.escape(FAQ_START) + '.*?' + re.escape(FAQ_END), lambda _: faq, content, flags=re.S)
        else:
            content = re.sub(r'<h2>Frequently asked questions</h2>.*?(?=<p style="margin:18px 0"|<h2>|$)',
                             lambda _: faq, content, count=1, flags=re.S)
    result['content_html'] = content
    result['title'] = config['title']
    seo = result.setdefault('_seo', {})
    seo['description'] = config['description']
    seo['search_focus_revision'] = REVISION
    return result
