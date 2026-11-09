"""UK editorial improvements retained through normal refreshes, without network calls."""
from __future__ import annotations
import copy
import html
import re
from src.usa_editorial import ADVICE as BASE_ADVICE, SAVVY, SAVVY_EXAMPLES, SAVVY_ACTION

REVISION = 'uk-topic-advice-2026-11-09'
START = '<!-- wb-uk-editorial:start -->'
END = '<!-- wb-uk-editorial:end -->'


def uk_text(text):
    # These are buying principles shared between markets, not US offers or rules.
    replacements = {'liter capacity': 'litre capacity', 'fiber': 'fibre', 'color': 'colour',
        'center': 'centre', 'maneuver': 'manoeuvre', 'organization': 'organisation',
        'organize': 'organise', 'motorized': 'motorised', 'prioritize': 'prioritise',
        'countertop': 'worktop', 'counter space': 'worktop space', 'ZIP code': 'postcode',
        'sales tax': 'any additional checkout charges', 'shipping': 'delivery', 'labor': 'labour',
        'catalog': 'catalogue', 'traveled': 'travelled', 'gasoline': 'petrol',
        'tire': 'tyre', 'customizing': 'customising', 'US-market': 'UK-market'}
    for old, new in replacements.items():
        text = re.sub(r"\b" + re.escape(old) + r"\b", lambda _: new, text)
    return text.replace('$', '£')


# Only market-neutral topics are shared. Electrical safety, furniture,
# refurbished equipment and budget/supporting angles have UK-specific copy.
SHARED = ('air-purifiers', 'backpacks', 'bluetooth-speakers', 'jump-starters',
          'carpet-cleaners', 'dash-cams', 'food-processors', 'large-capacity-air-fryers',
          'office-chairs', 'printers', 'projectors', 'robot-vacuums', 'smart-plugs',
          'webcams', 'wifi-routers', 'wireless-earbuds')
ADVICE = {key: (uk_text(BASE_ADVICE[key][0]), [(uk_text(h), uk_text(p)) for h, p in BASE_ADVICE[key][1]])
          for key in SHARED}
_printer_heading, _printer_sections = ADVICE['printers']
ADVICE['printers'] = (_printer_heading, [(h, p.replace('Two listings of the same Epson model are alternative offers, not two different printer designs.', 'Compare exact model suffixes and cartridge families before treating similar printer names as interchangeable.')) for h, p in _printer_sections])

ADVICE.update({
 'battery-chargers': ('Car battery chargers: match chemistry, voltage and charging routine', [
  ('A maintainer and a rapid charger serve different jobs', 'A 1A maintainer can suit keeping a compatible battery topped up; it should not be compared with a higher-current charger only by price. Check the vehicle manual and battery label for voltage, chemistry and permitted charging method. A product mentioning lithium, AGM or repair mode is not automatically suitable for every battery of those types. Obtain the exact charger instructions before deciding.'),
  ('Choose the connection and storage arrangement', 'Check whether charging in the vehicle is permitted, which clamps or permanent leads are supplied, and the required ventilation and weather protection. Confirm that the charger has suitable UK mains equipment. A pulse-repair claim is not evidence that a damaged battery can be made safe or restored to its original capacity. Repeated starting or charging problems need an appropriate diagnosis rather than another advertised mode.'),
 ]),
 'cordless-drills': ('Cordless drills: compare a usable UK kit before voltage labels', [
  ('Count the battery and charger as part of the purchase', 'List the tool, compatible batteries, UK charger, case and bits supplied. A low tool-body price can be attractive if you already own the correct platform, but is an incomplete comparison for a first drill. Two packs advertised with the same voltage need their capacity, compatibility and condition checked separately. An impressive voltage printed in a marketplace title does not establish torque or real-world performance.'),
  ('Choose the drilling mode for the material', 'Drill/drivers, hammer drills and impact drivers are different tools. Confirm the exact model modes, chuck capacity and supported materials in its manual. For furniture assembly or cupboard access, grip, head length and weight with a battery fitted may matter more than an accessory count. Illustrative arithmetic: a £40 body plus £35 compatible power kit costs £75 before any other required equipment; those figures are examples, not current offers.'),
 ]),
 'electric-blankets': ('Electric blankets: choose the intended use and follow the care instructions', [
  ('An underblanket is different from a heated throw', 'Check where the product is intended to sit, the bed size it fits and whether its instructions permit the use you have planned. Compare the heated area and control zones, not just the outer fabric dimensions. A timer or automatic shut-off does not establish overnight suitability for every blanket. Check compatibility with your mattress or adjustable bed rather than assuming all bedding arrangements are approved.'),
  ('Inspect the product and its support route', 'Find the exact instructions for washing, drying, storage and controller connection. London Fire Brigade advises checking blankets for signs of damage and following their instructions. <a href="https://www.london-fire.gov.uk/safety/the-home/electrical-items/electric-blankets/">Read London Fire Brigade electric-blanket guidance</a>. Check the model against official recall notices and stop using damaged equipment. A cheaper open-box offer needs a clear condition description and the correct controller; price is not a safety assessment.'),
 ]),
 'tower-fans': ('Fans for summer planning: airflow, placement and night-time use', [
  ('Choose a position before choosing a fan type', 'A tower fan can use a narrow patch of floor, while a pedestal fan needs a wider base and an air circulator can suit a different direction of airflow. Measure the space and consider the route of the mains lead. Oscillation range, tilt adjustment and control access affect how useful the fan is in that position. A high speed count does not establish quieter or stronger airflow.'),
  ('Compare a useful setting rather than the quietest headline', 'Check which speed was used for any noise or power claim, and whether display lights can be dimmed for a bedroom. A fan moves air; it is not an air-conditioning unit with a stated cooling capacity. For running-cost comparisons, multiply measured or reasonably estimated kWh by your own electricity tariff and label assumptions clearly. This is advance buying advice for summer 2027, not a prediction of a heatwave or a promise that prices will rise.'),
 ]),
 'gaming-headsets': ('Gaming headsets: check the console, connection and microphone', [
  ('Console compatibility is model-specific', 'A wireless headset can use a USB dongle, Bluetooth or a console-specific connection. Check the exact Xbox, PlayStation, PC and Switch support rather than assuming a similar model name covers every platform. A 3.5mm connection may offer a different feature set from wireless. Confirm which receiver and cables are included, especially with refurbished stock.'),
  ('Choose for your normal session', 'Compare weight, ear-cup fit, replaceable cushions and microphone monitoring. For chatting while playing, check how game and chat audio are mixed on your platform. Simultaneous Bluetooth audio, noise cancellation and virtual surround are separate capabilities. A long battery-life claim needs its test conditions read; lighting and connection choices may change the result. Product specifications alone do not establish microphone clarity or comfort for your head.'),
 ]),
 'lawn-mowers': ('Lawn mowers: compare the complete kit and the garden layout', [
  ('Bare mower and battery kit are not like-for-like offers', 'A bare mower needs its exact battery arrangement and UK charger checked before costing a usable setup. Compare that complete cost with a bundle supplying compatible batteries and a charger, not just another mower-body price. If you already own compatible packs, that can change the calculation. Battery voltage alone does not establish cutting performance or runtime.'),
  ('Match width, handling and maintenance to the lawn', 'Consider narrow paths, storage access, slopes and whether a full grass box is manageable. Check cutting-height adjustment, grass collection and mulching equipment actually supplied. A self-propelled petrol mower has a different maintenance and storage routine from a cordless mower. Compare the maker\'s instructions for your garden and operating conditions rather than assuming a larger engine or wider cut is always better.'),
 ]),
 'leaf-blowers': ('Leaf blowers: blowing, collecting and mulching are separate jobs', [
  ('Check which modes the complete machine supports', 'A blower-only tool moves leaves; a blower-vac also needs a collection arrangement. Confirm the bag, tubes and conversion steps included in a combined model. Wet leaves and gravel paths create different limitations, so read the exact manual rather than treating maximum air speed as a cleaning-performance test. A mulching ratio is not a guarantee for every type or condition of garden debris.'),
  ('Plan power, weight and disposal', 'A cordless tool needs its battery, charger and runtime conditions checked. A mains machine needs safe cable reach and the manufacturer\'s outdoor electrical guidance; a petrol model has fuel, servicing and storage requirements. Compare carrying weight with the collection bag filling, not only the empty tool. Decide where collected leaves will go before paying for a vacuum mode you may not use.'),
 ]),
 'non-slip-hangers': ('Non-slip hangers: compare garment support and the useful pack size', [
  ('Match the hanger to the clothing', 'Slim flocked hangers can help keep some garments in place, but shoulder shape, width and intended load still matter. A trouser bar, skirt clips and a contoured jacket hanger serve different jobs. Do not assume that every non-slip finish suits delicate or damp clothing. Check the garment-care advice and the hanger maker\'s instructions instead of choosing only by the number in the pack.'),
  ('Count useful hangers rather than the largest bundle', 'Work out how many matching hangers you need and whether their width suits the rail depth. Illustrative figures: 50 at £20 is 40p each, while 10 at £6 is 60p each; the bigger pack is cheaper per hanger only if the extra pieces are useful. These are arithmetic examples, not live prices. Check whether selected variants change the pack quantity and whether hooks or clips add bulk to a crowded wardrobe.'),
 ]),
 'streaming-devices': ('Streaming devices: separate media players from remote controls', [
  ('The offers here include controls, not complete streaming players', 'A One For All Smart Streamer or RCA universal streaming remote controls compatible equipment; it does not become a media player by using the word streamer. Confirm which existing TV, player or sound system it supports and how setup works. Compare a replacement remote with other remotes, not with the complete price of a streaming stick or box.'),
  ('For a player, check apps and the whole signal path', 'If you need an actual streaming device, confirm the apps, UK service availability, subscription requirements, HDMI connection and power supply. A 4K label also needs a compatible display, content and connection. Check whether the remote is supplied and which TV controls it supports. Search-result names are not a specification for every item shown; identify the exact model before applying a feature claim.'),
 ]),
 'luggage': ('Cabin luggage: check the booked allowance before the airline label', [
  ('Small under-seat and large cabin bags are different allowances', 'Do not rely on a suitcase title saying easyJet or Ryanair. As checked on 9 November 2026, easyJet lists a 45 × 36 × 20cm small cabin bag and a separately booked large cabin bag up to 56 × 45 × 25cm, including handles and wheels. <a href="https://www.easyjet.com/en/help/baggage/cabin-bags">Check easyJet\'s current cabin-bag rules</a>. The fare or bag booking matters as well as the case dimensions.'),
  ('Measure the packed case and compare your actual booking', 'Ryanair distinguishes its small personal bag from the larger 55 × 40 × 20cm, 10kg cabin bag under Priority &amp; 2 Cabin Bags. <a href="https://help.ryanair.com/hc/en-us/articles/12888036565521-Ryanair-s-Bag-Policy">Read Ryanair\'s current bag policy</a>. Check again for your journey, since rules can change. Expansion, wheels and handles can alter the external size. Compare empty weight, wheel replacement and return logistics alongside the headline capacity.'),
 ]),
 'power-banks-under-80': ('Power banks under 80 pounds: price usable output, cable and charging', [
  ('Capacity and output answer different questions', 'A 20,000mAh label does not establish laptop charging capability. Check the USB-C Power Delivery output, supported profiles and cable requirements for your actual device. Shared-port limits can reduce output when several devices charge together. A built-in cable is convenient only if its connector and power support match what you need.'),
  ('Keep the complete purchase within the budget', 'Add any necessary wall charger, suitable cable and delivery before treating an offer as under £80. Compare the bank\'s accepted input power and recharge time, not just how fast it can charge a phone. For flights, check the printed watt-hour rating and your airline\'s current rules. The budget is a buying limit, not confirmation that every linked listing still fits it today.'),
 ]),
 'value-garden-tool-sets': ('Value garden-tool sets: compare the working tools, not piece counts', [
  ('Count what the set will actually do', 'Separate the fork, trowel, hoe or pruner from gloves, labels and the carry bag when comparing piece counts. Telescopic hand tools and full-size digging tools have different reach and leverage. Check the extended length, locking arrangement and working-head material for the job. A larger assortment adds little value if several pieces duplicate tools you already own.'),
  ('Compare maintenance and replacement costs', 'Look for cleaning instructions, spare blades where applicable and how handles are attached. Confirm which items are supplied in the selected variant. A lower bundle price may be useful for a first small garden, while replacing one worn tool separately can suit an established kit. Two listings of the same three-piece set are alternative offers, not different tool designs or independent durability results.'),
 ]),
 'value-storage-bins': ('Value storage bins: compare a wall system with freestanding boxes', [
  ('Choose the access pattern before the pack quantity', 'A wall-mounted parts rack suits many small items; a large wheeled box suits a different storage job. Check usable bin dimensions, mounting requirements and whether the wall and fixings are appropriate. Compare the number of containers you can reach easily once installed. A forty-five-piece rack should not be compared with a large closet box by the piece count alone.'),
  ('Cost the system you will actually use', 'Add suitable mounting equipment if it is not supplied, and check the stated loading and stacking instructions. For lidded boxes, measure the outside including wheels and handles as well as the interior opening. Do not infer waterproofing, food-contact suitability or a safe load from the plastic appearance. A mixed pack is good value only when its sizes match the contents you need to store.'),
 ]),
})

FURNITURE = {
 'bed-frames': ('Bed frames: check mattress size, base and delivery access', [
  ('Size names do not replace measurements', 'Compare the required mattress dimensions with the exact frame, then measure the complete outer footprint, headboard height and clearance for drawers or doors. Confirm whether the mattress, slats, centre supports and fittings are included. A photograph of a dressed bed is not a contents list. Different sizes of the same frame are variants, not separate construction tests.'),
  ('Plan the route and assembly', 'Check package dimensions against stairs, landings and doorways, and read delivery-service and assembly terms. A metal frame may arrive in several sections; confirm the instructions and required tools. Look at the stated mattress support and load information for the exact size, not a related frame. Save the merchant\'s damage-reporting and return process before ordering a bulky item.'),
 ]),
 'coffee-tables': ('Coffee tables: compare usable space, finish and construction', [
  ('Check the table in the room layout', 'Measure height against your seating and allow space to walk around the table and open nearby drawers. A round top and a rectangular top occupy space differently. Check shelf clearance for the objects you want to store. Read marble effect, veneer and solid timber as different descriptions; a surface photograph does not establish the underlying material.'),
  ('Read the maintenance and delivery details', 'Confirm the finish-care instructions, stated load and assembly arrangement. Check whether the delivery includes placement in the room and how damage is handled. A lower table price can be offset by a delivery charge or difficult return. Compare the exact dimensions and material of each offer rather than treating every oak-coloured or marble-effect item as the same construction.'),
 ]),
 'dining-tables': ('Dining tables: compare everyday seating with the extended footprint', [
  ('Leave room for chairs and movement', 'Measure the top and the space around it with chairs pulled out. A nominal two- or four-seater label does not establish comfort with your own chairs. Check the leg arrangement and knee clearance, especially with a pedestal, drop leaf or extension mechanism. If an offer is an outdoor metal table, compare its intended setting separately from indoor painted furniture.'),
  ('Check what changes when the table opens', 'For a drop-leaf or extending model, compare both closed and open dimensions, support arrangements and storage for any extra leaf. Confirm whether chairs are included. Read surface-care and intended-use instructions rather than inferring heat or weather resistance from the finish. Include delivery, assembly and return logistics in the comparison of a bulky purchase.'),
 ]),
 'sideboards': ('Sideboards: compare internal storage and door clearance', [
  ('An 80cm cabinet and a three-door unit solve different needs', 'Measure the whole footprint and the space needed for doors or drawers to open. Check the internal shelf dimensions, shelf adjustability and the sizes of items you want to store. Oak and walnut colour variants of one range are offers to compare on finish and price; colour does not establish a different storage performance.'),
  ('Look beyond the decorative finish', 'Confirm the structural material, finish-care instructions, stated load limits and any recommended wall restraint. Plan delivery through the property and identify whether assembly is included. Compare the seller\'s process for missing fittings or damaged panels before purchase. A low cabinet price is less useful if its shelves cannot fit your items or the complete unit cannot pass the access route.'),
 ]),
 'wardrobes': ('Wardrobes: measure rail space, door swing and assembly clearance', [
  ('Compare the inside against the clothes you own', 'A two- or three-door label does not tell you the split between hanging space and shelves. Check internal rail height, depth and the width of each compartment. Allow enough depth for your hangers and clothing, then check door swing or sliding-door access. A mirror can be useful, but it does not add hanging capacity.'),
  ('Plan installation before ordering', 'Check ceiling and floor space needed for the stated assembly method, not just the finished wardrobe height. Read any wall-fixing or restraint instructions and confirm suitable installation arrangements. Check package sizes against stairs and landings and identify the merchant\'s delivery service. Save the parts list and damage-reporting terms so a missing panel or fitting can be raised clearly.'),
 ]),
}

LEGACY = {
 'best-iphone-18-pro-cases-amazon-uk-2026': ('iPhone cases: confirm the exact phone and the selected accessory', [
  ('A model name in a search is not a fit guarantee', 'Check the exact iPhone model in your device settings and compare it with the case maker\'s compatibility list. Pro, Pro Max and other versions should not be treated as interchangeable. Confirm the camera opening, buttons, charging connection and any screen-protector fit. A retailer search can mix case generations or show several variants, so select the actual compatible item before comparing its price.'),
  ('Choose the protection and handling trade-off', 'Compare grip, thickness, raised edges and how the case works with the charger or magnetic mount you already use. Magnetic attachment does not itself establish charging speed or a particular certification. If a drop-test claim matters, look for its stated method rather than treating every rugged label as equivalent evidence. Check whether a screen protector or strap is actually included. Product photos and search links do not establish hands-on protection results for your phone.'),
 ]),
 'best-refurbished-phones-under-400-in-uk': ('Refurbished phones under 400 pounds: budget for condition and support', [
  ('Choose the platform, then compare the complete offer', 'Decide whether you need iOS or Android, the storage and screen size that suit your use, and a current support path for the exact model. Compare the selected phone, delivery and any necessary UK charging equipment against the £400 limit. A search link is not confirmation that every model or condition variant is currently available within that budget.'),
  ('Spend the saving on a clearer ownership proposition', 'Ask for battery evidence, account removal, network restrictions, repair information where available and the written return terms. A more expensive unit with clearer condition evidence can be worth comparing with a cheaper cosmetically graded offer. Check calls, charging, cameras, biometrics and connectivity during the return period using the manufacturer\'s setup instructions. Do not assign an invented number of future update years or treat seller feedback as a product reliability test.'),
 ]),
 'best-apple-samsung-sony-accessories-uk-2026': ('Branded accessories: check the exact ecosystem before buying', [
  ('Choose the function, then verify the generation', 'AirPods, Galaxy Buds, watches and controllers are separate purchase types, rather than competing answers to one need. Check the exact phone, console or operating-system compatibility and which features require the maker\'s app. A familiar brand name does not establish that every accessory works with every device from that brand. Identify the model generation behind each retailer search before comparing features.'),
  ('Compare the complete replacement cost', 'For headphones, check the case, cable, ear tips or cushions included. For a watch, confirm account removal, battery condition, strap fitting and the correct charger. A controller needs its supported platforms and connection mode checked. Search links help locate offers, but do not establish stock, authenticity or a verified price. Seller service feedback and product-performance evidence answer different questions.'),
 ]),
 'best-refurbished-apple-watch-uk-2026': ('Refurbished Apple Watch: check pairing, battery and account removal', [
  ('Start with the iPhone you will pair', 'Confirm the watch model, generation and current iPhone/iOS requirements in Apple\'s support information before choosing by case size. GPS and cellular variants have different requirements; mobile service also needs a compatible plan if you want to use that feature away from the phone. Do not infer UK carrier support from a cellular label on an imported offer.'),
  ('Ask for a usable watch, not only a cosmetic grade', 'Check battery-health information, Activation Lock removal and the included charging equipment. Confirm the case and strap dimensions against what you intend to wear. During the return period, follow Apple\'s setup instructions to test pairing, charging, screen response and the functions you need. A seller-refurbished grade is not automatically Apple Certified Refurbished, and fitness features do not make a watch a substitute for medical assessment.'),
 ]),
 'best-refurbished-iphones-under-300-uk': ('Refurbished iPhones under 300 pounds: compare a complete usable phone', [
  ('Treat the budget as a search limit', 'A model shortlist does not establish that every storage and condition variant is currently available below £300. Add delivery and any necessary charging equipment to the selected offer. Compare battery condition and repairs as well as cosmetic grade; a cheaper phone that needs an immediate battery replacement may not fit the complete budget.'),
  ('Check ownership, network and service history', 'Apple recommends checking Activation Lock, battery health, parts history and network restrictions when buying preowned. Do not buy a device showing iPhone Locked to Owner. Confirm SIM arrangements and compatibility with your provider, then check calls, cameras, biometrics and charging using the normal setup process during the return period. <a href="https://support.apple.com/en-mide/104999">Apple\'s preowned iPhone checklist</a>. Keep these checks tied to the actual unit rather than an average star rating for the model.'),
 ]),
 'best-refurbished-laptops-uk-2026': ('Refurbished laptops: verify the processor generation and supported software', [
  ('A business range name is not a specification', 'ThinkPad, Latitude and EliteBook each cover many generations. Ask for the exact processor, RAM, storage, display resolution, ports and battery condition of the selected unit. Check the tasks and software you need before assuming an older premium chassis is a better purchase than a newer budget machine. Include a suitable UK charger and any needed dock in the price.'),
  ('Check the operating-system support path', 'Microsoft says standard Windows 10 support ended on 14 October 2025. Check the exact laptop\'s official Windows 11 compatibility or another current, appropriate support arrangement; a Windows-installed headline does not answer that question. <a href="https://www.microsoft.com/EN-GB/windows/end-of-support">Microsoft\'s Windows support guidance</a>. For a Mac, verify current macOS and app requirements for the exact generation. Test the keyboard, screen, ports, wireless connection and battery during the return period, and confirm that workplace management or previous-owner accounts have been removed.'),
 ]),
 'best-refurbished-smartphones-uk-2026': ('Refurbished smartphones: choose the platform before the flagship badge', [
  ('Compare the job and the support that remains', 'Choose the operating system, screen size, camera requirements and storage you need, then identify the exact regional model. Check the manufacturer\'s current software and security-support information rather than assuming every old flagship receives the same updates. An older premium camera or processor does not establish better battery endurance or a longer supported life than a newer mid-range phone.'),
  ('Separate the model decision from the individual offer', 'Once you have a shortlist, compare battery evidence, repair history where available, account removal, network restrictions and the supplied UK charging equipment. Save the seller\'s written grade and returns terms. Search links lead to changing offers, so confirm the selected unit and complete cost before paying. This broad guide helps choose a platform; the under-£300 iPhone guide answers a narrower budget question.'),
 ]),
 'best-refurbished-tablets-uk-2026': ('Refurbished tablets: check the generation, apps and accessory cost', [
  ('Choose the software you need before screen size', 'List the apps, work or school requirements and file formats you will use. Then check current operating-system and app support for the exact tablet generation. iPad Air and Galaxy Tab S are families containing different products, not single specifications. Confirm the RAM, storage and connectivity of the selected listing rather than transferring a newer model\'s features to an older one.'),
  ('Price the complete setup and test the unit', 'Check whether the keyboard, stylus, cover and suitable charger are included and compatible with that generation. Similar screen dimensions do not guarantee accessory fitting. Ask about battery condition and account removal, then test charging, touch response, speakers, cameras and wireless connections during the return period. A lower tablet-only price can be outweighed by missing equipment, especially if you intend to replace a laptop.'),
 ]),
 'best-toasters-worth-buying-uk-2026': ('Toasters: compare slot fit and the everyday handling', [
  ('Use the bread you actually buy as the size check', 'Check slot width and depth against your usual bread, bagels or crumpets. A four-slot model may help with several breakfasts, but independent controls for each pair are a separate feature to confirm. A long-slot design uses worktop space differently from a compact two-slice toaster. Extra presets do not, by themselves, demonstrate even browning.'),
  ('Check cleaning, small-item retrieval and repair information', 'Compare crumb-tray access, cancel controls and the intended high-lift mechanism. Follow the model instructions rather than inserting utensils into the appliance. If repairability matters, find the exact model\'s current parts and service information instead of applying a brand\'s general reputation to every range. Keep the existing source-based model comparison below as a shortlist, then verify the live variant and offer.'),
 ]),
 'diamond-jewellery-deals-ebay-uk-2026': ('Diamond jewellery: compare the item evidence before the discount', [
  ('Carat weight and a jewellery description need context', 'Confirm whether the stated weight refers to one stone or the total across several stones. Compare natural and laboratory-grown diamonds separately and identify the actual metal description. A retailer search can mix different stone sizes, settings and conditions, so a claimed percentage discount does not make those items equivalent.'),
  ('Verify the documents and the seller\'s item description', 'If a grading report is claimed, check the report issuer, identifier and whether it matches the actual stone. Do not assume every item has independent grading or that a photograph establishes authenticity. Ask about ring size, alterations, missing stones, clasp condition and the written return terms. This page is a comparison starting point, not a valuation or a promise of investment value.'),
 ]),
 'ps5-vs-ps4-best-value-uk-2026': ('PS5 versus PS4: compare the games you own and the complete setup', [
  ('A disc library changes the hardware choice', 'Check whether the selected console has a compatible disc drive and whether each game or upgrade you want is supported. PlayStation explains that an eligible PS4 disc upgrade requires a PS5 with a disc drive and continued use of the disc. <a href="https://www.playstation.com/en-us/support/games/upgrade-ps4-game-to-ps5-version/">PlayStation\'s PS4-to-PS5 upgrade guidance</a>. Do not assume every game has a free upgrade or that a Digital Edition can use a physical library without appropriate supported hardware.'),
  ('Include controllers, storage and condition', 'Compare the usable storage, included working controller, power and display cables, and any games you would otherwise buy. Check disc reading where applicable, account removal, connectivity and controller operation within the return period. A very low PS4 price can make sense for a specific existing library, but should not be justified by an assumed future support period or compatibility with every new release.'),
 ]),
 'small-home-upgrades-worth-buying-uk-september-2026': ('Small home upgrades: choose one task the product will improve', [
  ('Milk frother or smart plug: start with the daily routine', 'For a frother, decide whether you want a small handheld whisk or a heating-and-frothing jug, then check cleaning and usable capacity. For a smart plug, check the appliance load, UK fitting and whether the required timer or control works without an internet connection. These products do different jobs; the best purchase is the one that removes an actual inconvenience rather than simply adding another gadget.'),
  ('A heated airer needs space and an honest cost calculation', 'Measure the open footprint, load arrangement and ventilation required by the instructions. Compare the capacity with your normal wash, not just the rail count. Electricity cost is kWh used multiplied by your tariff: an assumed 0.3kW average for four hours is 1.2kWh, costing 30p at an illustrative 25p/kWh. These are example assumptions, not a measured result or guaranteed saving for any airer. Check your own tariff and actual drying routine.'),
 ]),
}


def block(config):
    heading, sections = config
    return START + '<h2>' + html.escape(heading) + '</h2>' + ''.join(
        '<h3>' + html.escape(h) + '</h3><p>' + p + '</p>' for h, p in sections) + END


def relevant_uk_product(title, query):
    title, query = title.casefold(), query.casefold()
    if 'streaming' in query and 'remote' in title:
        if re.search(r'remote control|universal remote|replacement remote|remote for', title):
            return False
        if not re.search(r'fire tv stick|roku (?:express|streaming)|chromecast|apple tv (?:4k|hd)', title):
            return False
    if 'smart plug' in query and re.search(r'\b(?:eu|us) plug\b', title):
        return False
    if 'air purifier' in query and re.search(r'\b(?:in[- ]car|car air purifier)\b', title):
        return False
    return True


def enhance_uk_article(article, market):
    if market != 'uk':
        return article
    g = article.get('_generator') or {}
    topic = g.get('topic', '')
    legacy = LEGACY.get(article.get('slug', ''))
    config = legacy or (FURNITURE.get(topic) if g.get('channel') == 'rakuten' else ADVICE.get(topic))
    if not config:
        return article
    result = copy.deepcopy(article)
    content = str(article.get('content_html') or '')
    if topic == 'streaming-devices' and not any(not relevant_uk_product(html.unescape(re.sub('<[^>]+>', '', h)), 'streaming device')
            for h in re.findall(r'<h3[^>]*>.*?</h3>', content, re.S)):
        config = ('Streaming devices: check the apps, display connection and power', [
            ('Identify the complete player in the offer', 'A streaming stick or box must be identified by exact model and generation. A replacement remote controls compatible equipment but is not itself a media player. Confirm which unit, remote, power supply and cables the selected offer includes, rather than relying on a bundle photograph.'),
            ('Match the UK services and display you use', 'Check app availability, service subscriptions and the HDMI and power connections needed for your setup. A 4K label also needs compatible content and a suitable display. Compare supported audio formats and TV controls if those matter to you. A low hardware price does not include every streaming service or guarantee support for every future app.'),
        ])
    advice = block(config)
    if START in content and END in content:
        content = re.sub(re.escape(START) + '.*?' + re.escape(END), lambda _: advice, content, flags=re.S)
    else:
        target = 'How to compare these retailer offers' if g.get('channel') == 'rakuten' else 'How to choose the right option'
        if topic == 'tower-fans':
            target = 'What should you look for?'
        pattern = '<h2>' + re.escape(target) + r'</h2>.*?(?=<h2>|$)'
        if re.search(pattern, content, re.S):
            content = re.sub(pattern, lambda _: advice, content, count=1, flags=re.S)
        elif legacy:
            heading = re.search(r'<h2', content)
            pos = heading.start() if heading else len(content)
            content = content[:pos] + advice + content[pos:]
        else:
            return article  # Preserve existing researched advice without padding.
    if not legacy:
        lead = html.unescape(re.sub('<[^>]+>', '', config[1][0][1])).split('. ')[0].rstrip('.')
        intro = '<p><strong>' + html.escape(config[0].rstrip('?.!') + '. ' + lead + '.') + '</strong></p>'
        content = re.sub(r'<p><strong>(?:Shopping for .*?|' + re.escape(html.escape(config[0].rstrip('?.!'))) + r'\..*?)</strong></p>', lambda _: intro, content, count=1, flags=re.S)
    content = re.sub(r'<h2>eBay UK vs Amazon UK: where should you compare\?</h2>.*?(?=<h2>)', '', content, count=1, flags=re.S)
    if not legacy:
        content = re.sub(r'<h2>Frequently asked questions</h2>(?:\s*<h3>.*?</h3>\s*<p>.*?</p>)*', '', content, count=1, flags=re.S)
        content = re.sub(r' This listing made the shortlist because it passed our automated price, fixed-price and seller-quality checks for [^.]+\.', '', content)
        content = content.replace(' Availability, condition and price can change quickly, so verify the exact model, specification, warranty, delivery and returns on the retailer page.', '')
    if g.get('prime_amazon_only') and not article.get('_event'):
        content = re.sub(r'<h2>Why this Prime guide is Amazon-only</h2>.*?(?=<h2>)', '<h2>Using these Amazon searches</h2><p>These links open UK retailer searches. Confirm the selected model, current price, seller and delivery terms; a search is not a verified discounted offer.</p>', content, count=1, flags=re.S)
    content = re.sub(r'<p class="wb-uk-offer-note">.*?</p>', '', content, flags=re.S)
    def annotate(match):
        heading = match.group(0)
        text = html.unescape(re.sub('<[^>]+>', '', heading)).casefold()
        note = None
        if topic == 'streaming-devices' and not relevant_uk_product(text, 'streaming device'):
            note = 'Remote control accessory: not a complete streaming media player.'
        if topic == 'smart-plugs' and 'eu plug' in text:
            note = 'EU-plug offer: do not treat this as a UK-plug equivalent.'
        if topic == 'air-purifiers' and 'in-car' in text:
            note = 'Car purifier: compare separately from a room air purifier.'
        return heading + ('<p class="wb-uk-offer-note"><strong>' + note + '</strong></p>' if note else '')
    content = re.sub(r'<h3[^>]*>.*?</h3>', annotate, content, flags=re.S)
    result['content_html'] = content
    seo = result.setdefault('_seo', {})
    # Include the actual topic as well as UK context; test through the real
    # publication selector so a generic fallback cannot silently mask errors.
    subject = config[0].rstrip('?.!')
    if topic == 'printers':
        subject = 'Printers: ' + subject.lower()
    if article.get('slug') == 'ps5-vs-ps4-best-value-uk-2026':
        subject = 'PlayStation consoles: ' + subject
    description = 'UK buying guide: ' + subject + '.'
    seo['description'] = description if len(description) <= 155 else description[:154].rsplit(' ', 1)[0].rstrip(' ,.;:') + '…'
    seo['uk_editorial_revision'] = REVISION
    return result


def weekly_deal_advice():
    return block(('Weekly eBay deals: compare the complete UK offer', [
        ('A listed discount is not an independent price history', 'The percentage shown is calculated from the seller\'s stated reference price. Compare the exact model, condition and contents with another credible current offer before treating it as a saving. A different capacity or a missing battery can explain a lower price. The dated checks here establish what was observed, rather than a promise that stock or price will remain unchanged.'),
        ('Choose the offer you can use and return', 'Add delivery and any required equipment, then read the seller\'s warranty and returns arrangements. Keep marketplace payment and communication on the platform and save the selected offer details. If no listing qualifies after a daily check, that means the feed has no verified qualifying offer at that point; it is not a reason to substitute an unverified deal. Use the topic buying guides to decide whether the product type meets your needs before comparing the discount.'),
    ]))


PRICE_COMPARE = ('Compare three UK offers on the same complete specification', [
 ('Set one baseline before choosing a favourite', 'Write down the exact job and the minimum features it needs. For a cordless drill, distinguish a complete first kit from a replacement body for batteries you already own. For a printer, decide whether automatic two-sided printing and a scanner are requirements. Use those requirements to remove unsuitable products before comparing prices. A low price for something that cannot do the job is not the baseline you need. Keep optional conveniences in a separate column, so a premium feature does not silently become compulsory simply because your favourite model includes it.'),
 ('Compare the offer as well as the product', 'For each option, record the complete model code, condition, capacity and included accessories. Include the seller and date, because a marketplace page can show several offers for one model. A stock photograph may include equipment that is not in the selected bundle. Check the written contents and choose the actual variant before copying the price. If one listing does not identify the generation or condition, mark it unconfirmed rather than assuming it matches the clearer offer. This keeps gaps in the evidence visible instead of rewarding the least informative listing.'),
 ('Work through a complete-kit example', 'Illustrative figures: a £55 drill body plus a £40 compatible battery-and-charger kit totals £95. A £90 complete kit is therefore £5 cheaper for someone buying their first tool, assuming everything else is comparable. For someone who already owns the correct power equipment, the £55 body could be the better option. These are example figures, not live offers. Check delivery and the selected battery capacity as well. The comparison changes if one bundle contains a smaller battery, an incompatible charger or a condition grade that you would not accept.'),
 ('Separate required costs from optional additions', 'List delivery to your postcode and any essential installation, consumables, cables or subscriptions. Check whether the displayed UK price is the final price for your purchase or explicitly excludes charges. Leave optional protection plans and accessories outside the required total unless you deliberately choose them. A free trial is not the same as a permanent included feature, and future cashback should be recorded separately from the amount payable now. Do not count the same coupon twice when the product page already shows the reduced price. Recalculate from the actual basket before choosing.'),
 ('Use condition and returns to break a close tie', 'A new item, an open-box return and a seller-refurbished unit can have different testing, contents and support arrangements. Read what the grade means for that seller and that item. Check who handles a warranty claim, the voluntary return window and the practical return costs. For bulky furniture, collection and packaging matter; for a laptop, battery evidence and account removal may matter more. These details do not prove that one item will last longer, but they explain differences that a price-only table hides. Save the written terms that influence your choice.'),
 ('Decide whether the bundle extra is useful', 'A carry case, second battery or replacement filter has value when it replaces something you would otherwise buy. Do not use the seller\'s claimed accessory value as a saving without checking it. Equally, do not dismiss a useful bundle because its initial price is higher. Write down what you would pay separately for the equipment you actually need. If several extras would stay in a cupboard, compare the simpler package. This is a personal-use calculation rather than an objective ranking of every bundle, and it can legitimately produce a different choice for another buyer.'),
 ('Finish with a dated decision', 'Choose the least expensive complete offer that meets the requirements and has acceptable condition and support evidence. Record the trade-off you accept, such as a heavier machine in exchange for a removable battery, and the information that would change your decision. If an offer disappears, compare its replacement against the same baseline instead of starting again from the newest discount badge. Keep the product page and basket with the date. A good comparison should leave you able to explain both why the chosen item suits the job and why a cheaper apparent alternative does not.'),
])

PRICE_TRAPS = ('Spot the offer differences hidden behind a UK discount badge', [
 ('Trap one: a similar model is presented as the same product', 'Read the complete model suffix, storage, capacity and generation. A retailer may sell an older or lower-specification variant beside a newer one with almost the same name. Check the manufacturer information for each exact version rather than transferring features from the more expensive product. If the listing is vague, ask which version will be supplied and save the answer. A difference in colour is usually a variant choice; a different processor, battery bundle or connectivity version can change the usefulness of the purchase. Do not treat those differences as a saving without examining them.'),
 ('Trap two: the lowest price omits essential equipment', 'A tool-only drill, a camera without a recorder and a tablet without its required keyboard can all appear cheap beside complete setups. List what you need to perform the job and mark what each offer includes. Then price the missing compatible equipment from a source you would actually use. Do not assume an inexpensive generic accessory fits because its photograph looks similar. If you already own the required equipment, record that fact; the bare product may genuinely suit you. The trap is comparing incomplete and complete offers without noticing the difference.'),
 ('Trap three: a percentage does the thinking for you', 'A large advertised reduction does not establish a low current market price. Check what reference price the seller uses and compare the actual product with another credible offer. Keep a seller-listed discount separate from an independently observed price history. A product can be heavily reduced and still be poor value for your needs. Conversely, an item without a dramatic badge can be a sensible purchase. Ask whether you would still choose the same exact model at the same final total if the sale message disappeared. If the answer changes, investigate the product decision before paying.'),
 ('Trap four: delivery or a membership reverses the result', 'Illustrative figures: a £70 item with £12 delivery costs £82, while an £80 item delivered free costs £80. Those are arithmetic examples, not current offers. Enter your actual postcode, since delivery coverage and charges can vary. If a membership is necessary for the price, decide whether you already hold it or would buy it solely for this order. Check whether the displayed UK price explicitly excludes any charges. Record a future voucher or cashback separately from the payable total, since it may arrive later or carry additional conditions.'),
 ('Trap five: a bundle creates a saving you would never use', 'Count only extras that meet a real need. A bag, spare cable or set of low-quality bits should not be valued at the seller\'s claimed retail total without a check. Compare the same product in a simpler package and price the few extras you actually want. For a consumable bundle, confirm that the refills match the exact machine and will be usable within the relevant storage guidance. Buying more of the wrong item is not a lower unit cost. Write down which accessories would replace a planned purchase and which would simply add clutter.'),
 ('Trap six: a countdown replaces a missing answer', 'A time limit does not settle a question about condition, compatibility or the return route. Save the details you have, identify the one fact most likely to change the purchase and ask through the official retailer or marketplace channel. Do not move payment away from a trusted platform to obtain a small extra discount. Check the seller behind the offer rather than assuming every listing on a familiar marketplace has identical terms. If the evidence remains unclear, compare a better-described alternative. The aim is a usable purchase, not winning a race against an animated timer.'),
 ('A practical way to use this guide', 'Choose one live offer and write six short answers: exact version, complete contents, actual comparison price, delivered total, useful extras and unresolved questions. Keep unknown costs marked unknown rather than turning them into zero. Compare those answers with a second offer that clearly meets the same need. If the cheaper option remains cheaper after the missing equipment and delivery are included, it may be worth considering. If its advantage depends on assumptions, finish those checks first. Keep the date and written evidence so that a changed variant or coupon does not silently alter the result.'),
])


def enhance_uk_savvy(article, market):
    if market != 'uk':
        return article
    configs = {**SAVVY, ('price-comparison', 'compare-options'): PRICE_COMPARE,
               ('price-comparison', 'avoid-traps'): PRICE_TRAPS}
    key = next((k for k in configs if '-' + k[0] + '-' + k[1] + '-' in article.get('slug', '')), None)
    if not key:
        return article
    heading, sections = configs[key]
    sections = list(sections)
    if key in SAVVY:
        sections += SAVVY_EXAMPLES[key] + [('Put the checks into practice', SAVVY_ACTION[key])]
    if key[0] == 'safety-authenticity':
        sections = [(h, p.replace('https://www.cpsc.gov/Recalls', 'https://www.gov.uk/product-safety-alerts-reports-recalls').replace('Check CPSC recalls', 'Check UK product safety alerts and recalls').replace('220–240 volts and not for USA', '120 volts and not intended for UK mains').replace('US power', 'UK power')) for h, p in sections]
    config = (uk_text(heading), [(uk_text(h), uk_text(p)) for h, p in sections])
    result = copy.deepcopy(article)
    result['content_html'] = ('<!-- wb-savvy-disclosure: footer --><p>Before you buy, use these practical checks to compare the exact UK offer. '
        'The worked examples use assumed figures; confirm the current item, delivered price and seller terms before ordering.</p>' + block(config) +
        '<p>Browse the <a href="https://www.worthbuyinguk.co.uk/">Worth Buying UK product buying guides</a> for category-specific comparisons.</p>')
    subject = {'price-comparison': 'price comparison', 'repairability': 'repairability and product support',
               'specifications': 'specifications', 'safety-authenticity': 'safety and authenticity'}[key[0]]
    result.setdefault('_seo', {})['description'] = 'UK ' + subject + ' advice: ' + config[0].lower().rstrip('?.!') + '.'
    result['_seo']['uk_editorial_revision'] = REVISION
    return result
