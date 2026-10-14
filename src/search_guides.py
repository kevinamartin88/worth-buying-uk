"""Sourced topic advice retained when an evergreen buying guide is refreshed.

This is local editorial copy: it adds no network dependency to daily publishing.
Retailer cards, prices, tracking and publication dates are left intact.
"""
from __future__ import annotations

import copy
import re

START = '<!-- wb-pressure-advice:start -->'
END = '<!-- wb-pressure-advice:end -->'
FAQ_START = '<!-- wb-pressure-faq:start -->'
FAQ_END = '<!-- wb-pressure-faq:end -->'
REVISION = 'pressure-search-guide-v1'


def pressure_advice(market: str) -> str:
    uk = market == 'uk'
    units = 'bar and litres per hour (l/h)' if uk else 'PSI and gallons per minute (GPM)'
    fuel = 'petrol' if uk else 'gas'
    source = ('https://www.karcher.com/gb/en/home-and-garden/products/pressure-washers-c6843'
              if uk else 'https://www.karcher.com/us/en/home-and-garden/products/pressure-washers-c5182')
    regional = (
        '<p><strong>UK specification example:</strong> Kärcher’s UK range chart lists the K 2 class '
        'at 110 bar and 360 l/h, and the K 4 class at 130 bar and 500 l/h. These are manufacturer '
        'range figures, not our test results or a guarantee for every older K 4 listing. '
        'Check the exact model code and included accessories: Classic, Standard and other bundles differ. '
        f'<a href="{source}">Source: Kärcher UK performance comparison</a>.</p>'
        if uk else
        '<p><strong>US model check:</strong> Kärcher’s US comparison separates pressure, motor type, '
        'weight and accessory connections. It also says its Classic, Compact, K Mini, WCM and K 7 '
        'variations are not currently authorized US models and are incompatible with the US power supply. '
        'A familiar name on an imported listing is not enough: verify a US model and local warranty. '
        f'<a href="{source}">Source: Kärcher US comparison and model notice</a>.</p>'
    )
    return (
        START + '\n<h2>How to choose a pressure washer for patios, cars and driveways</h2>\n'
        '<p>Start with the job you will do most often. A machine that is convenient for washing a car '
        'may feel slow on a large driveway; a bulky engine-powered washer can be more equipment than '
        'you want to store for occasional garden furniture cleaning.</p>\n'
        '<h3>For patios and driveways: compare flow, reach and attachments</h3>\n'
        f'<p>Compare {units} together. Pressure is only one part of the specification: '
        'flow tells you how much water the washer delivers. Compare working or rated figures with '
        'working figures, rather than treating an advertised peak number as sustained performance. '
        'Check hose reach from your water supply and whether a compatible surface-cleaner attachment '
        'is included in the price. Follow the surface and washer manufacturers’ instructions.</p>\n'
        + regional + '\n'
        '<h3>For cars: controllable spray matters more than maximum power</h3>\n'
        '<p>Look for adjustable pressure or an appropriate spray attachment, manageable hose storage '
        'and compatible detergent equipment. Do not choose a washer for a car solely because its '
        'headline pressure is highest. Check the instructions for paintwork, seals and trim before '
        'using it; the right accessory and setting depend on the machine and surface.</p>\n'
        f'<h3>Electric vs {fuel} pressure washers</h3>\n'
        f'<p>Electric and {fuel} machines solve different practical problems. With an electric washer, '
        'check suitable power access and the manufacturer’s cable requirements. With an engine-powered '
        'washer, factor in fuel, engine maintenance, weight and storage as well as the purchase price. '
        'Choose by the actual rated pressure, water flow and equipment supplied, rather than assuming '
        'the power source alone proves which is better.</p>\n'
        '<h3>What makes a cheaper listing good value?</h3>\n'
        '<p>Compare the complete bundle: hose, lance, nozzles, adapters and any surface cleaner. '
        'A second listing of the same model can be worth comparing on condition and accessories, '
        'but it does not represent a different machine. For refurbished stock, check the written '
        'warranty and returns terms. Seller feedback describes the seller’s service; it is not a '
        'product reliability score or evidence that the washer has been tested.</p>\n' + END
    )


def pressure_faq(market: str) -> str:
    uk = market == 'uk'
    unit = 'bar' if uk else 'PSI'
    flow = 'litres per hour' if uk else 'GPM'
    fuel = 'petrol' if uk else 'gas'
    questions = [
        (f'How much {unit} do I need in a pressure washer?',
         f'There is no single {unit} figure that suits every surface. Compare rated pressure with '
         f'water flow in {flow}, the nozzle and the manufacturer’s recommended use. A higher peak '
         'pressure alone does not tell you how well the washer will suit your job.'),
        ('What should I look for in a pressure washer for patios?',
         'Check the patio material first, then compare flow, hose reach and compatible surface-cleaner '
         'attachments. Check what is included: buying the attachment separately can change which '
         'bundle is better value.'),
        ('Can I use the same pressure washer for my car and driveway?',
         'It may be suitable for both if the manufacturer supports those uses and the correct '
         'attachments and settings are available. Do not use an aggressive driveway setting on '
         'paintwork; check the instructions for each surface.'),
        (f'Is an electric or {fuel} pressure washer better?',
         'Compare the specific machines. Check performance figures, power or fuel access, storage '
         'and maintenance. An occasional car-cleaning job and a large outdoor cleaning task can '
         'justify different choices.'),
        ('Are seller ratings the same as pressure-washer reviews?',
         'No. Seller feedback helps assess a transaction, while product reviews should concern '
         'the exact model. Look for useful details about setup, hose handling, repairs and long-term '
         'use, and keep different models or bundles separate.'),
    ]
    return FAQ_START + '\n<h2>Pressure washer questions answered</h2>\n' + '\n'.join(
        f'<h3>{question}</h3>\n<p>{answer}</p>' for question, answer in questions
    ) + '\n' + FAQ_END


def enhance_search_guide(article: dict, market: str) -> dict:
    """Enhance only the selected topic; unrelated articles stay byte-for-byte equal."""
    if (article.get('_generator') or {}).get('topic') != 'pressure-washers':
        from src.topic_advice import enhance_topic_advice
        return enhance_topic_advice(article, market)
    if market not in {'uk', 'us'}:
        return article
    result = copy.deepcopy(article)
    content = str(result.get('content_html') or '')
    advice = pressure_advice(market)
    faq = pressure_faq(market)
    if START in content and END in content:
        content = re.sub(re.escape(START) + '.*?' + re.escape(END), lambda _: advice, content, flags=re.S)
    elif '<h2>How to choose the right option</h2>' in content:
        content = re.sub(r'<h2>How to choose the right option</h2>.*?(?=<h2>)',
                         lambda _: advice + '\n', content, count=1, flags=re.S)
    else:
        # Unexpected older copy can keep its original text and still gain advice.
        content = advice + '\n' + content
    if FAQ_START in content and FAQ_END in content:
        content = re.sub(re.escape(FAQ_START) + '.*?' + re.escape(FAQ_END), lambda _: faq, content, flags=re.S)
    elif '<h2>Frequently asked questions</h2>' in content:
        content = re.sub(r'<h2>Frequently asked questions</h2>.*?(?=<p style="margin:18px 0"|<h2>|</div>\s*<script|$)',
                         lambda _: faq + '\n', content, count=1, flags=re.S)
    else:
        content = faq + '\n' + content
    result['content_html'] = content
    seo = result.setdefault('_seo', {})
    seo['description'] = (
        'Compare pressure washers for UK patios, cars and driveways. Check bar, water flow, electric vs petrol models, accessories and current retailer prices.'
        if market == 'uk' else
        'Compare pressure washers for US cars, patios and driveways. Check PSI, GPM, electric vs gas models, US compatibility and current retailer prices.'
    )
    seo['secondary_keywords'] = list(dict.fromkeys(list(seo.get('secondary_keywords') or []) + [
        'pressure washer for patios', 'pressure washer for cars', 'pressure washer for driveways',
        'electric vs petrol pressure washer' if market == 'uk' else 'electric vs gas pressure washer',
    ]))
    seo['editorial_revision'] = REVISION
    return result

