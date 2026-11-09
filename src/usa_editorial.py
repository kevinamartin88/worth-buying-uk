"""Local, topic-specific editorial advice; no API dependency or schedule changes.

Keep factual listing cards, owner evidence and dates. Replace only named generic
template sections. Unknown topics and other markets pass through unchanged.
"""
from __future__ import annotations

import copy
import html
import re

REVISION = 'usa-topic-advice-2026-11-09'
START = '<!-- wb-usa-editorial:start -->'
END = '<!-- wb-usa-editorial:end -->'

# Each entry answers a different purchasing decision. Copy describes checks,
# rather than inventing hands-on results, verified stock or model capabilities.
ADVICE = {
 'coffee-machines': ('Compare coffee-machine searches by brewing routine', [
  ('Choose the brewing method before the promotion', 'Filter coffee, capsule brewing and espresso are different routines. List the drink and batch size you make most often, then check the exact model\'s supported method. A broad retailer search can mix machines, grinders and accessories. Identify a complete US-market machine before comparing its advertised saving.'),
  ('Include the cleaning and consumables', 'Budget for the compatible coffee format, filters, descaling products and any optional milk-system parts. Check the space needed to fill the tank and remove the drip tray under your cabinets. For espresso, a low machine price is not the complete setup cost if you still need a suitable grinder. A historical event page does not establish current stock or an active discount.'),
 ]),
 'air-purifiers': ('Choose a purifier by room, airflow and filter supply', [
  ('Room coverage needs a stated basis', 'Measure the room before comparing coverage claims. Look for a published clean air delivery rate (CADR), the room-size assumptions and the fan setting used. A tiny personal purifier and a room purifier solve different problems. A HEPA label on filter material alone does not establish how quickly the complete machine cleans a room.'),
  ('Budget for the filter you can actually buy', 'Find the exact replacement filter code, price and recommended replacement interval before ordering. Compare a year of consumables as well as the machine price. For bedroom use, check noise at a useful cleaning speed, not only the quietest setting. EPA explains that filtration complements source control and ventilation; it does not remove every pollutant. <a href="https://www.epa.gov/indoor-air-quality-iaq/air-cleaners-and-air-filters-home">EPA guidance on air cleaners</a>.'),
 ]),
 'backpacks': ('Choose a backpack around what you carry', [
  ('Check the laptop compartment separately', 'The overall liter capacity does not tell you whether a laptop fits. Measure the computer, including any protective sleeve, and compare the compartment dimensions and opening. A roomy main compartment can still have a narrow device pocket. For commuting, put a loaded water bottle, charger and lunch box into your space plan rather than choosing by the laptop-size headline alone.'),
  ('Think about the journey with the bag loaded', 'Compare strap adjustment, back padding, access to tickets and whether the bag stands securely when opened. Water-resistant fabric is not a promise of waterproof seams or zippers. A travel backpack also needs to fit your airline\'s current personal-item limit; check the packed dimensions. Choose organization you will use, since extra pockets can take space away from bulky clothing.'),
 ]),
 'blenders': ('Personal smoothie cup or full-size blender jar?', [
  ('Buy for the batch you make most often', 'A personal cup is convenient when the same container becomes your drink bottle. A larger pitcher is more flexible for several servings, but check its usable fill line rather than its brim capacity. Compare the Ninja Blast-style portable cup with a countertop pitcher on charging, batch size and washing routine; a bigger motor headline does not make them interchangeable.'),
  ('Check the recipe limits before choosing power', 'Read the exact model instructions for ice, frozen fruit, hot liquids and maximum run time. Do not assume a sealed personal cup can blend hot soup. Check whether the blade assembly, lid seals and container are separately replaceable. For a refurbished machine, inspect the jar and blade condition and confirm that the supplied cup is approved for that motor base.'),
 ]),
 'bluetooth-speakers': ('Choose a speaker for a desk, kitchen or day outside', [
  ('Portability is more than battery hours', 'Compare weight, handle or strap, charging connector and the conditions behind the advertised runtime. Playback volume and lighting can change endurance. For an outdoor speaker, check the exact water and dust rating and whether charging ports need covers closed. A splash-resistant product should not be treated as suitable for every poolside or beach situation.'),
  ('Check how your devices will connect', 'Bluetooth pairing, stereo pairing and multi-speaker party modes are different features. Confirm that two speakers can pair in the mode you want and that their generations are compatible. For a TV or desktop, check wired inputs and any stated latency limitations. A built-in microphone or voice-assistant feature also needs explicit confirmation; it cannot be inferred from Bluetooth alone.'),
 ]),
 'jump-starters': ('Match a jump starter to the vehicle and storage routine', [
  ('A peak-amp headline is only a starting point', 'Check the manufacturer\'s supported gasoline or diesel engine sizes, battery voltage and operating-temperature range against your vehicle. A compact emergency pack, a workshop booster and a battery charger serve different routines. Confirm that the clamps, charging cable and instructions are included, especially with refurbished stock. Follow the vehicle and jump-starter manuals for connection and use.'),
  ('An emergency pack needs a maintenance plan', 'Choose somewhere to store it within its stated temperature limits and set a reminder to check its charge as instructed. A pack left discharged may be unavailable when needed. USB charging and tire-inflator extras can be useful, but compare their specifications separately. Repeated starting problems need investigation; buying a larger jump starter does not identify the underlying fault.'),
 ]),
 'car-phone-mounts': ('Choose the mounting position before the phone holder', [
  ('Test the position with the parked car', 'Work out where the screen can be seen without obstructing the road, controls or airbags, and check applicable local mounting rules. Vent clips, dashboard pads and suction mounts require different surfaces. A heavy phone can pull on a weak vent, while a curved or textured dashboard may not suit an adhesive pad. Check removal instructions before sticking anything to trim.'),
  ('Include the case in the fit check', 'Measure the phone with its normal case fitted. Confirm clamp width, access to buttons and cable clearance. Magnetic attachment and wireless charging are separate capabilities: check compatible case requirements, charging power and the car adapter supplied. For shared cars, easy adjustment may matter more than the strongest advertised magnet. Judge stability after fitting while parked, before relying on the mount.'),
 ]),
 'car-vacuums': ('Choose a car vacuum for the debris and access you need', [
  ('Crumbs, sand and pet hair ask different things', 'A narrow crevice tool helps between seats; a suitable brush matters for hair on upholstery. Check which tools are actually in the bundle and whether the hose reaches the footwells without moving the power source. Advertised Pa figures do not establish cleaning performance across different test methods. Container size and filter access can matter more during a messy family-car clean.'),
  ('Cordless convenience has a runtime trade-off', 'Compare runtime in the mode you expect to use, recharge time and whether the battery is replaceable. A 12V model needs adequate cable reach and the vehicle socket requirements checked. Look up the filter part number and cleaning instructions: a clogged or damp filter is a maintenance issue, not a reason to buy by the biggest suction claim. Keep wet pickup separate unless expressly supported.'),
 ]),
 'carpet-cleaners': ('Spot cleaner, upright extractor or commercial machine?', [
  ('Choose the cleaning task first', 'A portable spot cleaner suits upholstery and isolated spills; a larger carpet extractor is a different storage and maneuvering commitment. A wet/dry vacuum or steam machine should not automatically be treated as an equivalent carpet washer. Check which surfaces and cleaning solutions the exact machine and flooring manufacturer permit. Hose tools, upholstery attachments and a floor head may be separate purchases.'),
  ('Plan for the dirty-water side of the job', 'Compare clean and dirty tank capacity, the weight when full, cable reach and access for rinsing the hose and nozzle. A large tank reduces refills but adds lifting. Check the solution dilution and ongoing detergent cost rather than assuming any household cleaner is suitable. Leave time for drying and follow material-care instructions; extraction does not establish that every stain or odor will be removed.'),
 ]),
 'cordless-vacuums': ('Choose a cordless vacuum for your floors and storage', [
  ('The floor head matters as much as the motor', 'Match the supplied head to hard floors, rugs and the hair you regularly remove. Check whether the head is powered and whether a mini motorized tool is included for stairs or upholstery. A low headline weight may exclude the floor head and battery. Compare the assembled machine and hand-unit balance if you will carry it upstairs.'),
  ('Read the runtime conditions and replacement costs', 'Maximum battery life can refer to a low-power setting with a simple tool. Look for runtime in the mode and head combination you need, then check charging time and replacement battery availability. Inspect the dustbin opening, brush access and filter-washing instructions. A refurbished vacuum should have its battery condition and included charger stated clearly; cosmetic grading alone does not answer those questions.'),
 ]),
 'dash-cams': ('Check what a dash-cam kit records and how it is powered', [
  ('Front-only and multi-channel kits need different checks', 'Confirm the number of cameras supplied, not just supported. Rear-camera cable length, connector type and mounting position matter in a long vehicle. Resolution may differ when several cameras record together, so compare the actual recording modes. Check whether a compatible high-endurance memory card is included and which capacity and formatting instructions the manufacturer specifies.'),
  ('Parking recording is a separate installation question', 'Do not assume a USB-powered camera will record with the ignition off. Check the required hardwire kit, battery-protection settings and installation instructions. For reviewing footage, compare screen, app and card-reader access rather than treating Wi-Fi as cloud storage. Date, time and loop-recording setup deserve an arrival check before you depend on the camera for a journey.'),
 ]),
 'dehumidifiers': ('Compare moisture removal, drainage and room conditions', [
  ('Pints per day and bucket size are different', 'Moisture-removal capacity describes a test rate; the tank size determines how often you empty collected water. ENERGY STAR notes that changed test temperatures can make older and newer capacity figures difficult to compare directly. Check the stated test basis, operating-temperature range and your room conditions rather than choosing by square-foot coverage alone. <a href="https://www.energystar.gov/products/dehumidifier_testing_and_capacity">ENERGY STAR capacity guidance</a>.'),
  ('Plan where the water will go', 'For continuous drainage, check whether the unit relies on a gravity hose or has a pump, and what hose is included. A pump claim needs its lift-height limit checked. For a bedroom or office, compare noise and fan settings as well as the humidity controls. A dehumidifier can manage moisture; it does not repair a leak or establish the cause of damp.'),
 ]),
 'electric-blankets': ('Check blanket type, controls and care instructions', [
  ('A heated throw and a fitted bed blanket serve different uses', 'Confirm whether the product is intended to go over you, under a sheet or on a particular mattress. Compare the heated area, not only the fabric dimensions, and check whether a larger bed size has separate controls. Automatic shutoff is useful only when its timing suits the intended use. Do not infer overnight suitability from the number of heat settings.'),
  ('The instructions are part of the purchase', 'Obtain the exact care and use instructions before ordering, including washing, drying, folding and permitted bedding arrangements. Inspect used or open-box stock carefully and check the model against recall notices. CPSC\'s electrical-safety checklist stresses following blanket instructions. <a href="https://www.cpsc.gov/s3fs-public/513.pdf">CPSC home electrical safety checklist</a>. Stop using damaged equipment and follow the manufacturer\'s guidance; a bargain price is not evidence of safety.'),
 ]),
 'food-processors': ('Food processor or small food chopper?', [
  ('Match the bowl to your usual preparation', 'A 3.5-cup chopper and an 8- or 9-cup processor are different tools, even when both chop vegetables. Check usable capacity for liquids, the feed-tube opening and whether ingredients can be added during operation. For a family batch of slaw, slicing and shredding discs may be more useful than a small footprint. For a little sauce, a huge bowl can add unnecessary washing.'),
  ('Compare the included blades and storage', 'List the tasks you need: chopping, slicing, shredding or dough. Confirm which approved accessories perform them and which are included with the exact model. Check lid interlocks and the availability of replacement bowls and pushers. Refurbished bundles can omit discs or storage boxes. A high wattage or large accessory count does not prove the machine is suited to every recipe.'),
 ]),
 'game-controllers': ('Start with the game platform and connection', [
  ('PC, Xbox, Switch and mobile support are separate claims', 'Read the exact compatibility list, including operating system and connection mode. A controller advertised for PC is not automatically compatible with a console from the same ecosystem. Check whether wireless use requires a supplied dongle, Bluetooth or a proprietary adapter, and whether a wired-only tournament model suits your seating position. Button layouts and headset support can differ by platform.'),
  ('Choose the controls you will actually use', 'Compare grip size, stick layout, trigger adjustment and rear-button mapping before paying for competitive features. Check whether remapping requires desktop software and whether profiles remain on the controller. A headline polling rate depends on supported connection and software settings; it is not a measured reduction in your complete game latency. For refurbished units, ask about stick drift, button function and included receiver.'),
 ]),
 'garden-tool-sets': ('Choose useful garden tools rather than the biggest set', [
  ('Count working tools separately from extras', 'A set\'s piece count may include gloves, labels and a carry bag. Compare the trowel, fork, cultivator and pruner you actually need, then check handle length and storage. A small container garden has different needs from heavy digging. A lightweight gift set should not be assumed to replace full-size ground-working tools.'),
  ('Think about grip, cleaning and replaceable parts', 'Check how handles are attached and whether the pruner has a clearly described locking mechanism and replacement blades. For limited storage, a compact bag can help; for wet soil, easy cleaning may matter more. Follow tool-care instructions and dry equipment before storing it. Judge the materials stated for each working head rather than treating a color finish or decorative case as evidence of durability.'),
 ]),
 'large-capacity-air-fryers': ('Large capacity: compare cooking area before total quarts', [
  ('Two drawers and one large cavity solve different meals', 'Draw a typical dinner as a space plan: the protein, vegetables and any side that need different temperatures. Separate drawers can help with two cooking programs, but check the actual synchronization controls. A single large basket can suit a wide piece of food that would not fit either smaller drawer. Total quarts do not establish the usable flat cooking area.'),
  ('Measure the machine with doors and drawers open', 'Check the required ventilation clearances, countertop depth and washing-up space. An oven-style air fryer needs room for its door, racks and drip tray; a basket model needs space to pull the drawer out safely. Compare the actual parts that need cleaning after your normal meal. These links are searches, so confirm the exact model and live offer before applying any capacity claim.'),
 ]),
 'loungewear': ('Choose loungewear by fabric, fit and washing routine', [
  ('Use garment measurements instead of the size label alone', 'Compare waist, rise, inseam and top length with clothing you already find comfortable. Check whether the seller gives body measurements or finished-garment measurements. A relaxed cut, elastic waist and drawstring solve different fit issues. For a two-piece set, consider whether both halves will fit; buying separates may be more useful than accepting a poorly fitting top or bottom.'),
  ('Fabric composition tells you what to check next', 'Read the fiber percentages and care label, then decide whether warmth, stretch or a lighter feel matters most. Brushed fleece, knit cotton and satin-style fabric are not equivalent just because all are sold as lounge sets. Check pocket depth, cuff style and return conditions. Product photographs cannot establish softness, opacity or resistance to pilling, so look for comments about the exact fabric and variant.'),
 ]),
 'luggage': ('Choose luggage around the trip and airline limits', [
  ('Measure the outside, including wheels and handles', 'Compare the airline\'s current allowance with the complete case dimensions and empty weight. A manufacturer\'s cabin-size label is not universal airline approval. Expandable sections can move a packed case outside the limit. If you travel with several airlines, check the most restrictive journey rather than choosing the largest nominal capacity.'),
  ('Check the parts you will handle repeatedly', 'Look at wheel layout, handle adjustment, opening style and access to contents in a small hotel room. A clamshell case needs a different floor space from a top-opening bag. For a set, confirm which case sizes you would actually use. Warranty coverage, replacement wheels and zipper support can be more useful than an extra unused piece. No shell material alone guarantees that checked luggage will arrive undamaged.'),
 ]),
 'mesh-wifi': ('Mesh Wi-Fi: check the layout and backhaul first', [
  ('Place nodes where they can still communicate', 'A mesh kit needs a useful connection between nodes as well as coverage for your devices. Plan locations with power and check whether Ethernet backhaul is supported if your home is wired. More nodes are not automatically better in a small space. Thick walls, floor layout and interference make a square-foot coverage headline an estimate rather than a guarantee.'),
  ('Compare ports and the features that cost extra', 'Check how many usable Ethernet ports remain after the internet connection, especially if you need a wired computer or console. Confirm compatibility before adding a node to an existing mesh system. Read the subscription terms for security and parental controls. The fastest advertised wireless link rate is not a promise of that speed at every device or an improvement beyond your internet plan.'),
 ]),
 'office-chairs': ('Choose an office chair that adjusts to your body and desk', [
  ('Seat depth and arm height matter alongside capacity', 'Measure your desk clearance and compare seat-height and seat-depth ranges. A wide, high-capacity seat may be a poor fit if its front edge presses behind your knees or the arms stop you reaching the desk. Check whether the arms adjust, flip up or remain fixed. A maximum-weight claim is not an independent comfort test.'),
  ('Plan for assembly and the return journey', 'Check the chair\'s assembled dimensions, base width and caster suitability for your floor. Lumbar support can be fixed, adjustable or simply shaped padding; inspect the actual mechanism. Look up return shipping and disassembly requirements before buying a bulky chair online. A footrest and deep recline are extras, not proof of good working posture or suitability for a full day at your desk.'),
 ]),
 'printers': ('Compare the cost of printing your normal month', [
  ('Ink costs can outweigh the machine price', 'Estimate pages per month and the share printed in color. Find the exact replacement cartridges, their stated yields and whether the offer includes starter or full cartridges. Compare ordinary cartridge purchase with any optional subscription, including what happens if you cancel. A cheap printer is less useful if you cannot obtain affordable ink for the exact regional model.'),
  ('List the document jobs you need', 'Automatic two-sided printing, an automatic document feeder and two-sided scanning are separate features. Check each one explicitly if you handle forms or multi-page documents. For occasional home use, consider the maintenance instructions and time between prints. Open-box listings need their ink, printhead condition and setup accessories checked. Two listings of the same Epson model are alternative offers, not two different printer designs.'),
 ]),
 'projectors': ('Plan the room before comparing projector headlines', [
  ('Throw distance and screen size decide placement', 'Check the exact model\'s throw calculator or distance chart against your room and intended image size. Allow for cables, ventilation and a stable mount. Digital keystone correction can help alignment, but it is not a substitute for a workable placement plan. A projector that accepts a 4K signal is not necessarily using a native 4K imaging panel.'),
  ('Brightness figures need comparable units', 'Compare the published measurement method rather than mixing generic lumen claims with standardized ratings. Ambient light and screen choice affect the result, so an impressive dark-room photo is not proof of daytime suitability. Check fan noise, focus controls and the streaming apps you need. An external streaming device may require another power supply, HDMI connection and a way to route sound.'),
 ]),
 'robot-vacuums': ('Robot vacuum: check navigation, obstacles and dock upkeep', [
  ('Map the obstacles in your own home', 'Measure thresholds, furniture clearance and narrow routes before comparing navigation claims. Check how the model handles no-go areas, multiple floors and rugs. A camera or laser-navigation headline does not establish reliable small-object avoidance. Cables and pet mess need particular caution; review the exact manufacturer limitations and prepare the floor as instructed.'),
  ('A self-emptying dock still needs maintenance', 'Budget for bags, filters, brushes and any approved cleaning solution. A mop pad dragged behind a vacuum is different from an actively washing system; confirm rug behavior and whether pads lift or need removal. Compare dock dimensions, water-tank handling and access for cleaning. Refurbished bundles should specify the dock, ramp, power cable and consumables rather than showing them only in stock photography.'),
 ]),
 'security-cameras': ('Camera-only, recorder kit or Wi-Fi system?', [
  ('Check what creates and stores the recording', 'A camera pack may require a compatible recorder and power supply that are not included. Confirm the signal format, connector, cable and recording resolution for wired DVR systems. For Wi-Fi cameras, distinguish local card, hub and cloud storage. A memory-card slot does not by itself establish continuous recording or remote access without a subscription.'),
  ('Work through installation and ongoing cost', 'Measure cable reach or check solar-panel placement, battery maintenance and Wi-Fi at the intended mounting point. A solar label does not remove all charging or placement constraints. Compare the actual retention, detection and notification features included without payment. Color variants of one model should be compared as offers; they do not establish different camera performance.'),
 ]),
 'smart-plugs': ('Check the appliance load and smart-home ecosystem', [
  ('A plug must suit the actual appliance', 'Read the maximum load, permitted appliance types and indoor or outdoor rating in the exact model instructions. Do not infer suitability for heaters or motor loads from a headline amp rating alone. Check plug orientation and dimensions so that one smart plug does not block the neighboring outlet. A power strip and a single-outlet plug have different placement needs.'),
  ('Remote control, energy monitoring and local control differ', 'Confirm Wi-Fi band, hub requirements and compatibility with your existing voice assistant or smart-home platform. A timer does not guarantee operation when the internet is unavailable; check the documented behavior. Energy monitoring needs to be explicitly listed. Before buying a multipack, consider whether every planned location has reliable coverage and whether each outlet can be controlled independently.'),
 ]),
 'smartwatches': ('Choose a smartwatch for your phone and charging routine', [
  ('Phone compatibility comes before the watch face', 'Check the supported phone operating systems and which features depend on the brand\'s companion app. An LTE model also needs a supported carrier and plan if you want mobile service away from the phone. Do not assume the cellular feature is unlocked and usable with every US carrier. Check the exact regional model number, particularly on imported or refurbished listings.'),
  ('Battery and health claims need context', 'Compare runtime with your intended always-on display, GPS and mobile-data use, not just the longest advertised mode. Measure case size and check replacement strap fitting and charger inclusion. Fitness and wellness features should be evaluated against their documented intended use; they do not make a watch a substitute for medical assessment. For secondhand stock, ask about battery condition and account removal.'),
 ]),
 'soundbars': ('Match the soundbar connections to your TV', [
  ('Check the cable path before the channel count', 'Confirm whether your TV and soundbar share HDMI ARC/eARC, optical or another supported connection. Bluetooth does not automatically provide the same TV controls or audio-format support. Check the TV\'s audio-output options and the soundbar\'s supported formats. A high channel number can describe virtual processing, so identify the speakers physically included.'),
  ('Decide where the extra speakers will go', 'A separate subwoofer needs floor space and usually power; rear speakers introduce their own placement and cable questions. Compare dialogue controls for everyday television rather than paying only for cinema-format badges. Measure the bar against the TV feet and remote sensor. A refurbished offer should name the remote, subwoofer and cables supplied, since replacing a missing paired component may change the value substantially.'),
 ]),
 'ssds': ('Choose an SSD that fits the socket and workload', [
  ('M.2 describes a shape, not a complete interface', 'Check the computer or console documentation for supported interface, physical length and clearance. A 2.5-inch SATA drive and an M.2 NVMe drive are not direct substitutes. An enclosure can be sold alongside search results for complete drives; verify that storage is actually included. For a laptop upgrade, check whether mounting hardware and any required thermal parts are already present.'),
  ('Capacity and advertised speed need a use case', 'Allow for the operating system, games or project files and keep a backup before replacing a drive. Compare sustained-write information and warranty terms if you regularly move large files. A peak sequential-read claim is not a prediction of every application\'s loading speed. For used drives, ask for health and usage information; a low price alone does not establish remaining endurance.'),
 ]),
 'stand-mixers': ('Tilt-head or bowl-lift: choose for the bowl and counter', [
  ('Plan the batch and access space', 'Compare the bowl size with the maker\'s recipe limits, particularly for dough. A large bowl is not automatically easier for small batches. Measure clearance with a tilt-head raised or a bowl-lift lowered, and consider whether you can move the assembled machine. The mixer\'s weight may be welcome for stability but inconvenient if it must be stored in a cupboard after every use.'),
  ('Attachments must match the exact model', 'List the bowl, whisk, paddle and dough hook included. Do not assume bowls and beaters fit every mixer from the same brand, or that an attachment hub guarantees compatibility with every accessory. Check the manufacturer\'s model-specific compatibility information. With older or refurbished machines, inspect the bowl locking arrangement and ask about operation under load rather than relying only on a photograph of the motor running.'),
 ]),
 'steam-mops': ('Check the floor before choosing steam equipment', [
  ('Start with the flooring care instructions', 'Confirm that the flooring manufacturer permits steam and which settings or methods are allowed. A sealed appearance does not establish that every wood, laminate or vinyl floor is suitable. A steam mop is also different from a carpet extractor: a carpet-glider accessory does not turn it into a machine that washes and removes dirty water.'),
  ('Compare the pad and water routine', 'Check heat-up time, tank access, cable reach and the cost of replacement pads. A detachable handheld unit may help with a separate task, but verify the surfaces and attachments approved for it. Use only the water and additives specified by the manufacturer. A spinning head or high steam claim is not independent evidence of sanitizing performance under your household conditions.'),
 ]),
 'storage-bins': ('Choose bins by the shelf and contents, not just quarts', [
  ('Measure the usable opening and the outside with the lid', 'Tapered walls, handles and lids mean the interior and exterior measurements differ. Check whether the object fits through the opening and whether the closed bin fits your shelf. Multipack quantities also need reading carefully: a six-pack of small boxes is not comparable with six larger boxes just because the bundle price is lower.'),
  ('Think about access once the stack is full', 'A stackable lid is useful only if you can safely lift the loaded upper bins to reach the lower one. Compare latch style, visibility and labels for the intended storage. Do not infer waterproofing, food-contact suitability or a load rating from the plastic appearance. For heavy contents, follow the stated capacity and stacking instructions rather than filling every available inch.'),
 ]),
 'tablets': ('Choose a tablet around the apps and accessories you need', [
  ('Windows and Android are different buying decisions', 'A Windows detachable and an Android media tablet can look similar while running different software. List the exact apps, work logins and file formats you need, then check compatibility. For laptop replacement, confirm the keyboard, trackpad, ports and charging arrangement. A product photograph with a keyboard or stylus does not prove those accessories are included.'),
  ('Check the model code and update support', 'Screen size and storage are only part of the comparison. Verify RAM, regional connectivity, expandable-storage support and the maker\'s update policy for the exact model. A high-resolution display does not establish performance for every app. For a refurbished tablet, ask about battery condition, account removal and the supplied charger; compare the cost of a complete usable setup before choosing the cheapest body.'),
 ]),
 'tvs': ('Compare a TV for the room, sources and actual panel features', [
  ('Match indoor or outdoor use to the stated rating', 'An outdoor TV rated for partial sun should not be treated as suitable for every exposed location. Check mounting, weather protection and operating limits in the manual. Indoors, compare screen dimensions with your furniture and viewing position. Two sizes from the same range are variants, and their specifications can differ; confirm the exact size and model code.'),
  ('Check the signal path for games and sound', 'Read the native panel refresh rate, supported input formats and which HDMI ports provide them. A motion-processing label is not proof of a native high-refresh panel. Confirm the apps you need, plus ARC/eARC compatibility if using a soundbar. For refurbished offers, compare warranty, stand and remote inclusion and ask about screen condition rather than treating the original launch specification as a condition report.'),
 ]),
 'tyre-inflators': ('Choose an inflator for reach, tire size and duty cycle', [
  ('Maximum PSI is not an inflation-speed test', 'Compare the supported tire sizes, test conditions, hose length and continuous-use limit. A cordless inflator is easier to move around a vehicle, but needs charging; a 12V unit needs suitable socket power and cable reach. Check whether its chuck can reach the valve comfortably and whether the display can be read in that position.'),
  ('Use the vehicle\'s pressure recommendation', 'Follow the vehicle label or owner\'s manual for the load and tire size. NHTSA recommends checking tire pressure when cold; the tire sidewall maximum is not your normal target. <a href="https://www.nhtsa.gov/vehicle-safety/tires">NHTSA tire guidance</a>. An automatic cutoff is convenient but does not diagnose damage or a repeated leak. Include a separate pressure check and follow the tool\'s cooling instructions.'),
 ]),
 'video-doorbells': ('Buy a complete doorbell before comparing chime accessories', [
  ('A chime is not a camera doorbell', 'Identify the outdoor camera/button unit in the bundle. Add-on indoor chimes, mounting wedges and transformers can appear in doorbell searches but do not replace that unit. Match accessories to the exact model and generation. Arlo describes Chime 2 as an alert accessory used with compatible Arlo devices. <a href="https://www.arlo.com/en_gb/support/faq/device-features/arlo-chime-2-faq">Arlo Chime 2 compatibility</a>.'),
  ('Check power, recording and the doorway view', 'Confirm battery charging or wired power requirements before ordering, including any transformer and chime compatibility. Compare the view of parcels near the threshold as well as the horizontal view. Read the current recording-storage and subscription terms: live viewing, saved clips and advanced alerts can have different requirements. A no-subscription headline does not establish that every advertised feature is included without payment.'),
 ]),
 'webcams': ('Choose a webcam for the meeting setup you use', [
  ('Resolution, frame rate and field of view work together', 'Check the supported combinations, not just the maximum of each specification. Your meeting app and connection can affect what is transmitted. A wide view can show more of the room than you want; compare crop or field-of-view controls. For a laptop at a desk, mounting stability and camera height may improve the result more than a resolution upgrade.'),
  ('Check focus, microphones and software separately', 'Autofocus, auto framing and exposure adjustment are different features. Confirm which require the maker\'s software and whether it supports your operating system. A webcam microphone may be unnecessary if you already use a headset. Check privacy-shutter operation and cable length, particularly with a refurbished unit. Product resolution alone does not establish low-light picture quality or microphone clarity.'),
 ]),
 'wifi-routers': ('Choose a router for your internet connection and home layout', [
  ('Check the handoff from the modem or provider equipment', 'Confirm the connection type, WAN port speed and any provider settings required. A router is not automatically a replacement for a cable modem or fiber terminal. If you keep the provider router, understand the supported access-point or bridge arrangement rather than accidentally creating a configuration you cannot manage. Count the wired ports needed by your actual devices.'),
  ('Read speed labels as capabilities, not guaranteed results', 'Advertised aggregate Wi-Fi rates combine capabilities that one device may not use simultaneously. Check your clients\' supported bands and the router\'s update policy. Large or difficult layouts may benefit from a compatible mesh arrangement rather than simply buying a higher headline rate. Compare subscription features, parental controls and security-update availability as well as antennas and gaming labels.'),
 ]),
 'wireless-earbuds': ('Choose earbuds by fit, controls and daily use', [
  ('A secure fit is part of the sound and noise-control decision', 'Check the supplied tip sizes and the retailer\'s return conditions for opened in-ear products. Active noise cancellation, passive isolation and transparency mode are distinct features. Do not assume one set fits every ear or that a noise-cancellation claim proves comfort on a long call. A lighter bud and a smaller charging case may matter more for everyday pocket use.'),
  ('Separate earbud runtime from case top-ups', 'Compare playback time with the features you will enable, then check the extra charges available from the case. Confirm your phone\'s supported features, multipoint behavior and charging connector. Water resistance applies only within the exact rating and instructions; the case may have a different rating. Search links below require a live model and price check, rather than establishing a current discounted offer.'),
 ]),
}

# Narrower and merchant pages must answer a different question from the pillar.
VARIANTS = {
 'car-vacuums-under-90': ('Keep a car-vacuum purchase within the complete $90 budget', [
  ('Build the price around a usable kit', 'Start with the vacuum, then add any required charger, filter, crevice tool, shipping and sales tax. A sub-$90 product price is not proof that the complete checkout fits the budget. The links and historic checks below need reconfirming before payment. Prefer a clear, complete offer over an apparently stronger suction figure with missing accessories.'),
  ('Spend on the job the cheaper machine must finish', 'For crumbs between seats, reach and a useful nozzle can matter more than a large Pa claim. For embedded pet hair, check the supplied brush and relevant owner reports rather than assuming a mini handheld can replace a larger cleaner. Price a replacement filter now. If cleaning a whole car requires several charges, consider whether corded access better suits your routine.'),
 ]),
 'refurbished-cordless-drills': ('Inspect a refurbished drill as a complete working system', [
  ('Ask about the battery, not just cosmetic grading', 'Identify the tool and battery model numbers, the included charger and any attachment set. A clean body does not establish battery endurance. Compare the seller\'s stated testing and warranty with the cost of replacing the battery. A refurbished bare tool can make sense for an existing battery platform; it can be poor value as a first purchase if power equipment is missing.'),
  ('Use the return window for model-specific checks', 'Follow the manual to check controls, chuck operation and supplied attachments without exceeding the stated use conditions. Save the listing\'s condition description and contact the seller through the platform if anything differs. Compare a new complete kit before paying extra for a famous tool body. Seller feedback describes service history, not a measurement of this drill\'s torque or remaining life.'),
 ]),
 'value-cordless-drills': ('Value drill buying: compare the first job and the next battery', [
  ('Price the system you will own after checkout', 'For a first drill, compare a complete kit with the tool-only price plus compatible battery and charger. For an existing platform, avoid paying for duplicate equipment unless it adds useful capacity. Include the correct bits for your planned material. Illustrative arithmetic: a $60 body plus $50 power kit totals $110 before tax; those are examples, not current offers.'),
  ('Pay for a required mode before convenience extras', 'Furniture assembly, drilling wood and masonry work need different checks. Confirm the exact model\'s supported modes and materials; attachment count and battery voltage do not establish hammer capability. A compact tool may be easier in a cupboard, while a bundle of unused accessories adds little value. Use the main drill guide for the broad comparison and this page for the complete-kit budget.'),
 ]),
 'value-video-doorbells': ('Budget doorbell buying: price the camera, power and recording', [
  ('Start with the outdoor camera unit', 'Do not use an add-on chime\'s price as the price of a complete video doorbell. Confirm the camera/button, mounting hardware, battery or power arrangement and any required hub. A chime can help you hear visitors indoors, but compatibility is model-specific and it is an additional system component.'),
  ('Compare a year of the features you need', 'Write down whether you need live viewing only, saved event clips, longer history or particular alerts. Read the current plan terms for the exact model and add any necessary subscription to the hardware total. A cheaper camera can become the more expensive option for your chosen recording setup. Conversely, an optional plan adds no value if its features do not match your needs.'),
 ]),
}

RETAILER_ADVICE = {
 'air-purifiers': ('Separate replacement filters from complete air purifiers', [
  ('Read this feed as a mix of machines and maintenance items', 'The Ionic Comfort wire kit, Airfree carbon capsules and HEPA replacement filters listed here are consumables or parts. They are not complete room purifiers and should not be compared with a machine on purchase price alone. The personal purifier is a different product type again. Identify what is actually supplied before following any offer.'),
  ('For an existing machine, start with its exact filter code', 'Match the model and revision to the manufacturer\'s parts information. Compare the number of usable replacements in the pack and delivery cost, rather than the lowest feed price. If you need a complete room cleaner, look for a stated CADR and filter supply instead. <a href="https://www.epa.gov/indoor-air-quality-iaq/air-cleaners-and-air-filters-home">EPA explains room filtration and its limits</a>.'),
 ]),
 'cordless-vacuums': ('Read a retailer vacuum offer as a particular bundle', [
  ('Find the model and tools behind the feed name', 'Retailer feed names can be abbreviated. Open the merchant listing and identify the exact model, floor head, charger, battery and attachments included. A handheld cleaner is not a substitute for an upright floor-cleaning kit simply because both are cordless. Compare the merchant\'s full contents list with your floor and stair-cleaning needs.'),
  ('Check the ongoing ownership details', 'Locate the replacement filter and battery before ordering, and compare the merchant\'s returns and warranty terms for that offer. If the feed does not specify runtime conditions, do not assume its longest headline applies with a powered head. Use the main vacuum guide for the broader type comparison; this page helps assess the individual retailer package and its maintenance costs.'),
 ]),
 'dash-cams': ('Check the retailer dash-cam package before installation', [
  ('Count the supplied cameras and cables', 'Confirm whether the offer includes a rear camera, its cable, memory card and power adapter. A listing that supports a rear camera may still sell only the front unit. Check card requirements and how footage is exported. A low package price loses its advantage if the extra camera or required cable must be bought separately.'),
  ('Ask what is needed for parked-car recording', 'Check whether a separate hardwire kit is required and who will install it according to the maker\'s instructions. Do not treat Wi-Fi as proof of remote cloud access. Compare app support, warranty and the return process with the exact merchant; a feed description is a starting point, not a complete installation specification.'),
 ]),
 'dehumidifiers': ('Check drainage and specification gaps in a retailer offer', [
  ('Confirm the type of dehumidifying equipment', 'A compact cabinet device and a room dehumidifier are different purchases. Ask for the moisture-removal rate and its test conditions if the feed gives only a room-size slogan. Check the tank size separately. An unusually small or low-priced item deserves a type check before it is compared with a full-size appliance.'),
  ('Price the drainage arrangement you will use', 'If the machine will run in a basement, confirm gravity-drain requirements, hose inclusion and whether there is a pump. Check pump lift limits and operating-temperature range in the manual. ENERGY STAR explains why capacity figures from different test procedures can differ. <a href="https://www.energystar.gov/products/dehumidifier_testing_and_capacity">Read the capacity comparison guidance</a>.'),
 ]),
 'power-banks': ('Compare a power bank by output and recharge needs', [
  ('Check the port that powers your device', 'Battery capacity alone does not establish laptop charging support. Confirm the USB-C Power Delivery output, the supported voltage profiles and the cable requirements for your device. Check the shared-power limits when two ports are used. A high total wattage can describe several outputs combined rather than the power available from the one port you need.'),
  ('Account for recharging and travel', 'Compare the input power accepted by the bank and whether a suitable wall charger is supplied. A large bank with slow input can take an inconvenient time to refill. For air travel, check the printed watt-hour rating and the airline\'s current rules before buying. Do not infer airline approval from a marketplace headline or convert capacity without the correct nominal voltage.'),
 ]),
 'security-cameras': ('Compare these retailer cameras by installation type', [
  ('A bulb camera, floodlight and standalone camera mount differently', 'Check the permitted socket or power connection, weather rating and field of view for the actual installation. A discreet indoor camera should not be treated as equivalent to an outdoor floodlight camera. For solar models, confirm the panel position, charging requirements and mounting hardware. The white and black versions of one system are color variants rather than independent performance choices.'),
  ('Find the recording terms before comparing price', 'Check whether saved footage requires a card, hub or subscription, and what happens when any included trial ends. Ask for the app name and supported devices if the feed is vague. Compare the merchant\'s support and return terms for the complete kit. A low camera price is only one part of a usable, maintainable recording setup.'),
 ]),
}

LEGACY = {
 'best-refurbished-ipads-ebay-us-2026': ('Before buying an older iPad: check the complete setup', [
  ('Match the generation to the accessory', 'Write down the exact iPad generation, storage and connectivity, then check the keyboard and Pencil compatibility for that model. A similar screen size does not guarantee that an accessory fits. Price the tablet with the accessories and suitable charger you actually need. Do not assign an assumed number of future software-update years to an older iPad; verify current app requirements and Apple support information.'),
  ('Ask what refurbished means for this unit', 'Confirm battery testing, account removal, cosmetic condition and return terms in writing. Check touch response, charging, cameras, speakers and wireless connections during the return period, using the manufacturer\'s setup instructions. A seller\'s refurbished label is not automatically the same program as Apple Certified Refurbished. The search links are routes to compare offers, not a guarantee of stock, price or condition for every unit.'),
 ]),
 'best-refurbished-iphones-under-400-us-2026': ('Check the complete refurbished iPhone before spending $400', [
  ('A budget is a search limit, not a verified offer', 'Compare the exact model, storage and battery condition at the delivered price including sales tax. Add any required charger and case. A phone listed below $400 can still exceed the budget at checkout. Do not treat a model shortlist as proof that every recommended generation is available in acceptable condition within that price today.'),
  ('Check ownership, network and repairs separately', 'Apple advises checking Activation Lock, battery health, parts and service history, and carrier restrictions when buying preowned. Do not buy a device showing iPhone Locked to Owner. Confirm that the exact regional model and SIM arrangement suit your carrier, then test calls, cameras, charging and biometrics during the return period. <a href="https://support.apple.com/en-mide/104999">Apple\'s preowned iPhone checklist</a>. Seller grading does not establish remaining battery life or future software support.'),
 ]),
 'best-toasters-worth-buying-us-2026': ('Choose the toaster for your actual bread and counter', [
  ('Check slot shape as well as slice count', 'Measure a slice of the bread or bagel you normally buy and compare the maker\'s slot dimensions. Four slots can help a family breakfast, but two independently controlled pairs are a separate feature to confirm. A long-slot design can suit wider bread while using a different strip of counter space. Neither a bagel button nor a large setting count proves even browning.'),
  ('Make the everyday handling comparison', 'Check the crumb-tray access, cord storage, cancel control and ability to lift smaller items using the intended mechanism. Read the instructions for frozen bread and specialty items. Compare owner comments for the exact model, particularly browning consistency and ease of cleaning, without treating another model\'s reviews as transferable. The retailer search links below require a live price and variant check before purchase.'),
 ]),
}

SAVVY = {
 ('price-comparison', 'before-you-shop'): ('Build a fair comparison before opening the sales pages', [
  ('Write one specification for the purchase', 'Start with the job, the exact size or capacity you need and a maximum complete budget. For a printer, record the required scanning and duplex features; for a cordless drill, specify whether you need the battery and charger. This prevents a cheaper, incomplete product from becoming the benchmark against which every usable kit looks expensive.'),
  ('Make one row per comparable offer', 'Record model and regional suffix, condition, included equipment, item price, delivery, estimated sales tax and any required subscription. Keep optional extras in a separate column. If the basket is not yet priced for your ZIP code, mark the total as incomplete rather than assuming free delivery or zero tax.'),
  ('Use an example to expose the missing cost', 'Illustrative figures: a $70 tool body plus a $45 battery-and-charger kit totals $115 before tax. A $105 complete kit is cheaper for a first-time buyer, but the body could be better for someone who already owns compatible power equipment. These are example numbers, not live offers. The same method works for a camera that needs a recorder or a printer that needs ink.'),
  ('Decide what would change the result', 'Check whether a bundle extra replaces something you would otherwise buy. Ignore an inflated claimed value for an accessory you do not need. Save the offer date and contents so that a changed variant or expired coupon does not silently alter your comparison. When you return to the product guide, compare the complete setup against this written requirement.'),
 ]),
 ('price-comparison', 'final-checklist'): ('Audit the checkout total before paying', [
  ('Match the basket to the offer you researched', 'Recheck the model suffix, storage or capacity, condition and seller at checkout. A marketplace page can change the selected offer when a variant sells out. Confirm that the image and headline are describing the same bundle as the contents list. Do not let a substituted color or size conceal a different specification.'),
  ('Recalculate the delivered price', 'Include delivery to your ZIP code, estimated sales tax, mandatory membership, installation and essential accessories. Illustrative example: a $90 item with $12 delivery costs $102 before tax, while a $100 item with free delivery costs $100. That is arithmetic, not a current deal. If a coupon has a cap or applies only to part of the order, calculate the actual deduction.'),
  ('Check what happens if the purchase is unsuitable', 'Find the current return window, return destination and who pays shipping. Keep voluntary returns and warranty repair as separate questions rather than assuming one policy answers both. For bulky goods, inspect pickup and repackaging requirements. Save the written policy and the final basket before payment.'),
  ('Make the final choice without the discount badge', 'Ask whether you would still select this exact product at this total if the countdown disappeared. If it remains the least expensive complete option that meets your needs, the comparison is useful. If a cheaper offer depends on an accessory you have not priced or a return process you cannot use, finish those checks first.'),
 ]),
 ('repairability', 'compare-options'): ('Compare the support behind two otherwise similar products', [
  ('Start with the part most likely to wear', 'For a vacuum, look for the battery, brush and filter; for a blender, the jar and seal; for a connected camera, the app and recording service. Search the exact model code in the manufacturer\'s parts catalog. A generic search result mentioning the brand is not proof that the part fits.'),
  ('Record availability, price and who can fit the part', 'Compare a part that is actually orderable with one shown as discontinued or out of stock. Include labor, shipping and required tools where relevant. An accessible battery compartment does not by itself establish that a suitable replacement is available. Use the manufacturer\'s instructions and an appropriate repair route rather than attempting work beyond your competence.'),
  ('Compare the connected life as well as the hardware', 'Find any published update-support period and the features that depend on cloud service. Check what still works if a trial ends or the internet is unavailable. A functioning camera or printer can be less useful if its essential app no longer supports your phone. Do not guess a future support date when the maker has not provided one.'),
  ('Turn those findings into a buying decision', 'Use a simple side-by-side record: exact wear part, current replacement cost, repair route, warranty provider and stated software support. A slightly dearer product can be sensible if there is a credible maintenance path, but do not assume every repair will be economical. Keep your evidence dated because parts and service arrangements can change.'),
 ]),
 ('repairability', 'avoid-traps'): ('Spot a product-support promise that needs more evidence', [
  ('Check the difference between repairable and repair-supported', 'A product may be physically possible to open while lacking an orderable battery, seal or display. Look for the exact part number, service instructions and a realistic repair route before treating repairability as a benefit. A brand\'s parts page for a newer model does not establish support for the older stock you are buying.'),
  ('Do not confuse warranty length with complete coverage', 'Read which organization handles a claim, what the policy covers and which costs remain with the buyer. A seller warranty and a manufacturer warranty are different arrangements. Ask for unclear points in writing. Avoid assuming that a long headline term includes batteries, accidental damage or return shipping.'),
  ('Test the app-dependence claim', 'List the product\'s main job and ask which steps need an account, subscription or cloud connection. Check the documented behavior if that service is unavailable. An offline button may operate only one function. Save any stated security-update date rather than assuming support continues for as long as the device powers on.'),
  ('Use the missing information as a comparison point', 'If one seller cannot identify a replacement consumable or the warranty route, compare a clearer alternative. That uncertainty does not prove the product will fail, but it affects the purchase decision. Avoid buying a very cheap spare from an unrelated model simply because its photograph looks similar; compatibility needs confirmation.'),
 ]),
 ('specifications', 'final-checklist'): ('Translate the specification sheet into a usable purchase', [
  ('Check the unit and the conditions beside the number', 'For a pressure washer, compare rated pressure and flow under a stated basis; for a projector, check the brightness measurement method; for a vacuum, identify the mode behind the runtime claim. Maximum figures taken from different conditions cannot be combined into a measured performance result.'),
  ('Separate physical fit from headline capacity', 'A storage bin\'s quarts do not describe its usable opening. A backpack\'s liters do not establish laptop-compartment dimensions. An air fryer\'s total volume does not tell you whether a whole portion lies flat. Measure the thing you need to fit, then check the relevant internal or external dimensions.'),
  ('Verify the connection and regional model', 'Check voltage, plug, interface, operating system and required hub against what you already own. A tablet keyboard in a photograph may not be included. A high-resolution webcam may offer its fastest frame rate only at a lower resolution. Confirm the combination you need, not each maximum considered separately.'),
  ('Keep three reasons for choosing the model', 'Write the three requirements it meets and the trade-off you accept, such as a heavier vacuum in exchange for a removable battery. If you cannot connect an expensive feature to a job you will do, treat it as optional. Keep the model-specific manual or specification page with your comparison so another variant is not silently substituted.'),
 ]),
 ('safety-authenticity', 'before-you-shop'): ('Check market suitability and product identity before shopping', [
  ('Identify the exact product and intended market', 'Record the model number and regional suffix from the listing and compare them with the manufacturer\'s information. Check the electrical rating, required power supply and instructions. A plug adapter alone does not establish that an appliance is suitable for US power. An imported product may also have different support or warranty arrangements.'),
  ('Look up recalls using the model, not only the brand', 'Search official recall notices and the maker\'s safety information before buying older or secondhand stock. Match the affected identifiers and follow the official instructions if there is a match. A familiar logo or positive seller feedback is not a safety test. <a href="https://www.cpsc.gov/Recalls">Check CPSC recalls</a>.'),
  ('Ask how the seller supports the authenticity claim', 'Compare packaging, serial labels and contents with the official model information, while recognizing that photographs alone cannot authenticate an item. Ask for clearer evidence if a label is altered or details conflict. For a safety-critical product with an unknown history, choose a traceable and appropriate source rather than relying on an unusually low price.'),
  ('Plan the arrival check before the return window starts', 'Keep the listing and written answers. On arrival, confirm the actual model, included power equipment and condition against the order, and follow the manufacturer\'s setup instructions. Stop if you find damage or incompatible equipment and contact the seller through its official route. Do not attempt to make a questionable electrical item usable by improvising repairs.'),
 ]),
}


SAVVY_EXAMPLES = {
 ('price-comparison', 'before-you-shop'): [
  ('Worked comparison: choosing a home printer', 'Suppose you need ten pages a week, occasional color and a scanner. Create three rows for printers that meet those requirements. In each row, write the purchase price, whether the supplied ink is a starter set, the cost of a normal replacement set and whether automatic two-sided printing is included. Put an optional ink subscription in its own column. The point is to compare your likely use, not to declare that one ink arrangement is always cheaper. If you cannot find the cartridge code for one model, that row is not ready for a decision. Check a dated manufacturer page for the specification and the retailer basket for the offer; each answers a different question.'),
  ('What to do with uncertain costs', 'Do not turn an unknown into a zero. Write delivery as unknown until your destination is entered. Write installation as not yet quoted if the appliance needs it. For a subscription, separate the introductory period from the later recurring price and record which features remain after cancellation. If you do not know how much printing you will do, calculate a low-use and a higher-use scenario with your own assumed page counts. Label those figures as estimates. This makes the uncertainty visible and shows which missing detail could change the result, instead of creating a falsely precise ownership total.'),
  ('Keep the comparison small enough to finish', 'Choose a baseline that clearly meets the need, your preferred option and one credible alternative. Eliminate products that fail a requirement before adding more rows. Record a reason for each elimination, such as missing duplex printing or an incompatible battery platform. Revisit that requirement if every affordable option fails it; you may be asking for something unnecessary. When two complete offers are close in price, compare return logistics, condition evidence and support. Keep your comparison dated, because a change in stock or included equipment can reverse the result without changing the product model. The useful outcome is a decision you can explain, not the longest spreadsheet.'),
 ],
 ('price-comparison', 'final-checklist'): [
  ('Worked checkout: the apparent saving that disappears', 'Imagine two offers for the same vacuum and condition. Offer A is $120 with $15 delivery and no crevice tool. Offer B is $140 delivered with the tool included. If the correct tool costs $12 delivered, A becomes $147 before any applicable tax, so B is $7 less on those assumptions. If you already own the compatible tool, A could instead be the cheaper usable option. These example figures show why a bundle is worth only what you would otherwise need to buy. They are not product prices or a claim that one retailer is consistently cheaper. Recalculate with the actual destination, contents and accessories.'),
  ('Check the discount conditions line by line', 'Confirm that the code applies to the selected seller and variant, that any minimum spend is met and that the deduction appears in the final total. Check whether a maximum discount limits the saving and whether delivery is excluded. If a membership is necessary, decide whether you already have it or would pay for it solely for this order. Keep cashback or a future voucher separate from the amount payable now; it may have its own conditions and timing. Do not count the same saving twice when a product page already displays a reduced price. The basket total is the number to compare.'),
  ('Keep a record that will help if something differs', 'Save the exact product page, selected variant, seller name, condition description and included equipment, plus the order confirmation and current return policy. Make sure the saved material identifies the purchase rather than only a generic category page. If the delivery date matters, record what the seller actually promised and whether it was an estimate. Use the retailer or marketplace\'s official communication route for questions. Before paying, review whether any unresolved detail affects your ability to use or return the item. A small saving does not settle a missing-model or missing-accessory question. Finish those checks while you can still choose another offer.'),
 ],
 ('repairability', 'compare-options'): [
  ('Worked comparison: two cordless vacuum systems', 'Imagine Vacuum A costs $130 and Vacuum B costs $160. You find a manufacturer-listed battery and filter for B, while A\'s listing gives no battery code. That does not prove A will fail or B will last longer. It does mean the maintenance route for B is clearer today. Ask A\'s seller for the exact parts and a source before deciding. Next check whether fitting the battery is an approved user task or a service job. Add any quoted labor and delivery rather than comparing bare component prices. Keep battery compatibility tied to the model revision; a similar-looking pack from the same brand may not be the correct one.'),
  ('Use a support matrix rather than a repairability slogan', 'Give each shortlisted product a row. Use columns for the predictable wear item, its exact part number, current availability, replacement price, approved fitting route, warranty provider and any published connected-service support. Put not stated where evidence is missing. Do not award an invented lifetime score or estimate a failure rate from those rows. The matrix shows the maintenance options you can verify now. It also makes the right follow-up question obvious: is the part merely listed in an old manual, or can it actually be ordered? A dated answer from an official supplier is more useful than a vague promise of easy repairs.'),
  ('Decide which support matters for your use', 'A frequently used machine with washable filters and an accessible replacement battery creates different priorities from a lightly used item kept as a backup. Consider how much downtime you can tolerate and whether you have a local repair route. For a connected product, check whether its core function depends on an account or subscription you intend to keep. Separate an optional convenience feature from the main job. A longer warranty can be useful, but read how a claim works and what it covers. The aim is to compare credible ownership paths, not to assume every component is user-serviceable or that any warranty promises unlimited useful life.'),
 ],
 ('repairability', 'avoid-traps'): [
  ('Trap: the spare exists, but for a different revision', 'A replacement jar, battery or seal can appear in search results beside the model you own while fitting only a related generation. Check the manufacturer\'s compatibility list using the full model suffix. Ask about adapters or revised fittings rather than assuming an identical photograph settles the question. If the listing offers several versions in a menu, confirm the selected one at checkout. Save the compatibility claim. Buying an inexpensive but incompatible spare can create a second unusable purchase, and forcing a part to fit can damage the product. Use the approved service instructions instead of treating a close visual match as engineering evidence.'),
  ('Trap: an app is optional until a particular job needs it', 'Walk through the functions you expect to use. A camera may display a live view but require a separate arrangement to save clips; a device may have local controls but require an app for setup or schedules. Check the actual manual and current service terms. Ask what happens after a trial and whether the product can be reset for a new owner. Do not infer continued cloud support from the fact that the hardware still turns on. When the maker does not publish a support period, record that uncertainty rather than inventing an end date or promising indefinite availability.'),
  ('Trap: a warranty sounds easier than its claim process', 'Find the organization that handles the claim and the contact route before ordering. Check whether you must ship the complete machine, provide the original packaging or pay particular transport costs under the policy. Confirm how a refurbished unit is identified and what documents are required. Save any written seller promises that influenced the purchase. These checks do not determine your legal rights, which depend on the facts and applicable rules; they help you understand the advertised process. If the seller cannot explain that process, compare a clearer offer. A generous headline duration should not replace the practical question of what happens when you need help.'),
 ],
 ('specifications', 'final-checklist'): [
  ('Worked example: a webcam specification combination', 'Suppose one webcam advertises its highest resolution and fastest frame rate on separate lines. Before treating both as simultaneous, open the model\'s supported-video-mode table. Check which resolution is available at the frame rate you need, which connection is required and whether the setting works in your meeting app. Next identify the field of view and whether cropping or auto framing requires additional software. A higher number on the box can still be irrelevant if your normal call uses a different mode. This comparison does not predict picture quality; lighting, exposure behavior and the actual meeting service still matter.'),
  ('Worked example: a container that almost fits', 'Imagine a shelf with 14 inches of depth and an object that is 12 inches wide. A bin described only by volume does not answer whether it will work. You need the closed external depth, the internal width at the narrowest useful point and the opening size. Handles or a lid lip may add to the outside measurement, while tapered walls reduce the usable space. Leave the access room your storage arrangement needs rather than matching every dimension exactly. This is why a capacity headline is a starting point, not a substitute for a physical fit check. Apply the same distinction to luggage and laptop compartments.'),
  ('Resolve conflicting specifications before choosing', 'If the retailer page and manufacturer manual disagree, confirm that they refer to the same regional model and revision. Save both references and ask the seller to identify what will be supplied. Check whether an accessory photograph is illustrative and whether a feature is supported only after an optional upgrade. Do not average two conflicting numbers or pick the more attractive one. Mark the requirement as unconfirmed until you have a clear answer. At the final comparison, you should be able to point from each essential job to a model-specific capability and then to the complete offer that supplies it. That is more useful than counting features.'),
 ],
 ('safety-authenticity', 'before-you-shop'): [
  ('Worked example: a low-priced imported appliance', 'Suppose a coffee maker appears cheaper than comparable US offers but the title says 220–240 volts and not for USA. Do not treat it as a normal US alternative or assume a travel plug adapter resolves the issue. Check the exact electrical rating and manufacturer guidance, then choose equipment intended for your market if compatibility cannot be established. Also check the warranty route and availability of instructions and parts. The price difference is not a useful saving if the product cannot be used appropriately in your setup. The same regional-model check belongs in a comparison of chargers, smart-home devices and connected electronics.'),
  ('Make a record of the product identity', 'Save the model number, seller, condition statement and any identifying information shown in the listing. If the seller uses stock photographs, ask which details describe the actual item. Match recall notices using the identifiers specified in the notice, such as model or production range, instead of assuming every product from a brand is affected. Conversely, a different color name alone does not establish that a unit is outside a recall. Follow the official notice if the identifiers match. Keep recall and authenticity as separate checks: absence from a recall list does not authenticate an item, and authentic equipment can still be subject to a recall.'),
  ('Use a cautious arrival process for uncertain equipment', 'Before powering an electrical purchase, compare the supplied unit and power equipment with the order and manufacturer instructions. Look for obvious damage, missing labels or incompatible components. Do not bypass warnings or improvise a charger because the connector fits. If there is a discrepancy, document it and use the retailer\'s official support process while the return window is open. For safety-critical goods whose history cannot be established, seek an appropriate qualified source. These steps are a screening process rather than a safety certification. The useful buying decision is whether the product\'s identity, intended use and support route are clear enough for the job you need it to do.'),
 ],
}

SAVVY_ACTION = {
 ('price-comparison', 'before-you-shop'): 'Try this before browsing: choose one product you already own and write the complete replacement specification without naming a brand. Include the job, dimensions, connections and equipment you would keep. Then identify which extras in a typical bundle you would actually need to buy. This gives you a baseline for judging an offer without relying on its claimed discount. Leave room for an alternative product type if it solves the same job more simply, and keep optional preferences separate from requirements.',
 ('price-comparison', 'final-checklist'): 'Try a final basket audit: read each line aloud and mark it required, optional or unexplained. Remove optional additions you did not intend to buy and investigate unexplained charges. Confirm the selected delivery service and destination, then compare the resulting total with your saved alternative. If an offer has changed, update your comparison instead of relying on yesterday\'s screenshot. Finish by saving the actual order details; a promotional page by itself may not record the seller, condition or bundle you selected.',
 ('repairability', 'compare-options'): 'Try one support question with each shortlisted brand: identify a common wear part and ask for the correct replacement code and approved repair route. Compare how specific and usable the answers are, while allowing for different service hours. This is a practical information check rather than a scientific test of customer service. Keep the replies with your model comparison. If the answers refer to different revisions or regions, resolve that difference before treating the products as equally supported in your location.',
 ('repairability', 'avoid-traps'): 'Try checking a product you already own: find its exact model label, one replaceable wear part and the current support contact. Notice where a generic brand search sends you to a different generation or a third-party accessory. That experience helps you spot the same gap in a new offer. Write down which evidence is missing and ask a precise question before buying. Do not describe a product as unsupported merely because one quick search failed; distinguish missing information from confirmed discontinued support.',
 ('specifications', 'final-checklist'): 'Try a three-column check before checkout: requirement, confirmed capability and evidence. For example, write two-sided scanning as the requirement, the model\'s actual scanner behavior as the capability and its manual page as the evidence. Do not substitute a nearby feature such as two-sided printing. Repeat the exercise for physical fit and device compatibility. If a row still contains a vague marketing phrase, you have found a useful question to resolve. The final list should describe what your complete purchase will do in your own setup.',
 ('safety-authenticity', 'before-you-shop'): 'Try building a product-identity record before comparing price: exact model, regional version, electrical requirements, seller and official support page. Check that the listing answers each field consistently. If a photograph and description conflict, ask which unit will be supplied and keep the answer. Do not infer authenticity from the record alone; it simply makes discrepancies easier to identify. For a purchase whose failure could cause harm, use an appropriate qualified source and the manufacturer\'s instructions rather than filling missing details with assumptions.',
}


def enhance_savvy_article(article: dict, market: str) -> dict:
    if market != 'us':
        return article
    slug = article.get('slug', '')
    key = next((k for k in SAVVY if ('-' + k[0] + '-' + k[1] + '-') in slug), None)
    config = SAVVY.get(key)
    if not config:
        return article
    result = copy.deepcopy(article)
    config = (config[0], config[1] + SAVVY_EXAMPLES[key] + [('Put the checks into practice', SAVVY_ACTION[key])])
    result['content_html'] = ('<!-- wb-savvy-disclosure: footer --><p>Before you buy, use these practical checks '
        'to compare the exact offer. The examples use assumed figures and situations; '
        'confirm the current product details and terms before ordering.</p>' + _block(config) +
        '<p>For model-specific comparisons, browse the <a href="https://www.worthbuyingusa.com/">Worth Buying USA buying guides</a>.</p>')
    result.setdefault('_seo', {})['description'] = config[0] + '. Practical USA shopping checks, worked examples and the evidence to confirm before ordering.'
    result['_seo']['usa_editorial_revision'] = REVISION
    return result


def _block(config):
    heading, sections = config
    return (START + '<h2>' + html.escape(heading) + '</h2>' + ''.join(
        '<h3>' + html.escape(title) + '</h3><p>' + text + '</p>'
        for title, text in sections) + END)


def enhance_usa_article(article: dict, market: str) -> dict:
    if market != 'us':
        return article
    generator = article.get('_generator') or {}
    topic = generator.get('topic', '')
    config = VARIANTS.get(topic) or ADVICE.get(topic)
    if generator.get('channel') == 'rakuten':
        config = RETAILER_ADVICE.get(topic)
    # Existing researched guides have their own maintained advice. Do not
    # duplicate it with a second, generic topic block.
    content = str(article.get('content_html') or '')
    if (generator.get('channel') == 'rakuten' and topic == 'air-purifiers'
            and not re.search(r'<h3[^>]*>[^<]*(?:Wire Kit|Capsule Refills|HEPA Filters? for)', content, re.I)):
        config = ('Check the complete purifier package at the retailer', [
            ('Verify the machine and the first filter', 'Find the exact model number and confirm that the offer includes the complete purifier and its required initial filters. Feed names can be shortened, and accessory results must not be priced as whole machines. Check the merchant\'s full contents list and the manufacturer\'s room-sizing information before comparing the package with another retailer.'),
            ('Check the replacement route before ordering', 'Locate the exact replacement-filter code, its current price and the maintenance instructions. Compare delivery, returns and warranty for the actual merchant offer. A low first price can be outweighed by hard-to-find consumables. For room sizing, use published CADR information and its stated conditions rather than treating every square-foot coverage headline as equivalent.'),
        ])
    legacy = LEGACY.get(article.get('slug', ''))
    if legacy:
        config = legacy
    if article.get('slug') == 'approved-retailer-slow-cookers-us-2026-10-05':
        config = ('Slow cooker or sous-vide circulator? Identify the cooking equipment', [
            ('The Inkbird offer is a different cooking method', 'The ISV-300W listing describes sous-vide equipment, not a conventional countertop slow cooker. It should not be compared with a Crock-Pot as a like-for-like pot-and-lid alternative. Confirm the exact contents, compatible vessel and manufacturer instructions. A vacuum sealer in a bundle is another separate component, not proof that the offer includes a slow-cooker pot.'),
            ('Use this page to check package contents', 'The Crock-Pot listings describe complete cookers, with a carry bag in one offer. Compare the exact model, quart capacity, control behavior and included lid or travel equipment. A manual Warm setting does not imply automatic switching. For the broader capacity and timer comparison, use the main slow-cooker guide; here, focus on avoiding a mismatch between the listing name and the appliance you intend to buy.'),
        ])
    if not config:
        return article
    result = copy.deepcopy(article)
    block = _block(config)
    if START in content and END in content:
        content = re.sub(re.escape(START) + '.*?' + re.escape(END), lambda _: block, content, flags=re.S)
    else:
        target = ('How to compare these retailer offers' if generator.get('channel') == 'rakuten'
                  else 'How to choose the right option')
        pattern = '<h2>' + re.escape(target) + r'</h2>.*?(?=<h2>|$)'
        if re.search(pattern, content, re.S):
            content = re.sub(pattern, lambda _: block, content, count=1, flags=re.S)
        elif legacy:
            # Preserve the original sourced model descriptions and every link.
            match = re.search(r'<h2', content)
            pos = match.start() if match else len(content)
            content = content[:pos] + block + content[pos:]
        else:
            # Bespoke/previously researched advice wins; no padding added.
            return article
    # These sections repeat the same general retail instructions and questions
    # across categories. Keep disclosures, evidence and related links intact.
    content = re.sub(r'<h2>eBay vs Amazon: where should you compare\?</h2>.*?(?=<h2>)',
                     '', content, count=1, flags=re.S)
    if not legacy:
        content = re.sub(r'<h2>Frequently asked questions</h2>(?:\s*<h3>.*?</h3>\s*<p>.*?</p>)*',
                         '', content, count=1, flags=re.S)
        # Selection boilerplate and the same warning repeated under every
        # product add no model evidence. Keep prices, condition and seller stats.
        content = re.sub(r' This listing made the shortlist because it passed our automated '
                         r'price, fixed-price and seller-quality checks for [^.]+\.', '', content)
        content = content.replace(' Availability, condition and price can change quickly, so verify '
            'the exact model, specification, warranty, delivery and returns on the retailer page.', '')
    if article.get('_event'):
        note = ('<!-- wb-usa-event-context --><p><strong>Historical event guide:</strong> '
                'This page was created for October 2026 Prime Big Deal Days. '
                'It does not establish an active event discount today. The links are '
                'searches; confirm the current model, price and terms on Amazon.</p>')
        if '<!-- wb-usa-event-context -->' not in content:
            content = note + content
    elif generator.get('prime_amazon_only'):
        content = re.sub(r'<h2>Why this Prime guide is Amazon-only</h2>.*?(?=<h2>)',
            '<h2>Using these Amazon searches</h2><p>These links open retailer searches. '
            'Check the selected model, live price, delivery and seller terms; a search '
            'result is not a verified discounted offer.</p>', content, count=1, flags=re.S)
    # Put the product-type correction beside each affected offer, not just in
    # the buying advice. Keep historic prices and commercial destinations.
    def label_component(match):
        heading = match.group(0)
        text = re.sub('<[^>]+>', '', heading).casefold()
        component = (topic in {'video-doorbells', 'value-video-doorbells'} and
                     re.search(r'add[- ]on chime|chime 2', text))
        component = component or (generator.get('channel') == 'rakuten' and
                     topic == 'air-purifiers' and re.search(r'filter|refill|wire kit|capsule', text))
        different = 'sous vide' in text and topic == 'slow-cookers'
        if not component and not different:
            return heading
        note = ('Different appliance: sous-vide equipment, not a conventional slow cooker.'
                if different else 'Accessory or consumable: not a complete room air purifier.'
                if topic == 'air-purifiers' else 'Add-on indoor chime: not a complete video doorbell.')
        return heading + '<p class="wb-component-note"><strong>' + note + '</strong></p>'
    content = re.sub(r'<p class="wb-component-note">.*?</p>', '', content, flags=re.S)
    content = re.sub(r'<h3[^>]*>.*?</h3>', label_component, content, flags=re.S)
    result['content_html'] = content
    seo = result.setdefault('_seo', {})
    seo['usa_editorial_revision'] = REVISION
    # Avoid replacing existing model-specific descriptions on sourced guides.
    description = (config[0] + '. ' +
        re.sub('<[^>]+>', '', config[1][0][1]).split('. ')[0].rstrip('.') + '.')
    if len(description) > 160:
        description = config[0] + '. Practical checks before buying in the USA.'
    seo['description'] = description
    return result
