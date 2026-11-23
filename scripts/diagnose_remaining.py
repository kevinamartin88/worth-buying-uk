"""Bounded, read-only provider diagnostics; never publishes or changes settings."""
import json
import os
from pathlib import Path

import requests
import cloud_editorial as editorial
import generate_daily_articles as daily
from src.ebay import EbayClient
from src.ai_visuals import _extract_image_bytes

out = Path('reports/remaining-diagnostics')
out.mkdir(parents=True, exist_ok=True)
account = os.environ['CLOUDFLARE_ACCOUNT_ID']
token = os.environ['CLOUDFLARE_API_TOKEN']
response = requests.post(
    f'https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/black-forest-labs/flux-1-schnell',
    headers={'Authorization': f'Bearer {token}'},
    json={'prompt': 'Editorial photograph of a simple table setting with stainless steel cutlery, no text or logos.', 'steps': 4},
    timeout=120,
)
print('Cloudflare HTTP', response.status_code)
if response.ok:
    (out / 'cloudflare-probe.jpg').write_bytes(_extract_image_bytes(response))
    print('Cloudflare image decoded successfully')
else:
    try:
        errors = response.json().get('errors', [])
    except ValueError:
        errors = [{'message': 'Non-JSON response'}]
    print(json.dumps(errors).replace(token, '[redacted]').replace(account, '[account]')[:1600])

brief = next(b for b in editorial.load(Path('automation/bespoke_briefs.json')) if b['key'] == 'easy-grip-cutlery')
for market in ('uk', 'us'):
    client = EbayClient.for_market(market)
    for group in brief['groups']:
        query = group.get('query_' + market, group['query'])
        queries = [query, 'easy grip cutlery' if 'handle' in group['label'] else 'bendable spoon']
        for q in dict.fromkeys(queries):
            items = client.search(query=q, max_price=group['ceiling'][market], require_free_shipping=False, limit=30)
            print(json.dumps({'market': market, 'query': q, 'results': len(items)}))
            for item in items[:12]:
                detail = client.get_item(item['itemId'])
                item = {**item, **detail}
                print(json.dumps({'title': item.get('title'), 'price': item.get('price'),
                    'condition': item.get('conditionId'), 'specifics': item.get('localizedAspects'),
                    'editorial_eligible': editorial.eligible(item, group, market),
                    'daily_score': daily.listing_score(item, group['ceiling'][market], 'GBP' if market == 'uk' else 'USD', query=q)}, ensure_ascii=False))
