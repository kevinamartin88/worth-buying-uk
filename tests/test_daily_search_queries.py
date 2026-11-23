import pytest
from generate_daily_articles import amazon_model_query

@pytest.mark.parametrize('title', [
    '162pc Electric Rotary Mini Drill & Bit Set Jewellery Making Craft Hobby Tool Kit',
    '40PCS Non Slip Strong Metal Clip Hangers Chrome Clothes Trouser Coat Skirt Rack',
    '5/10Pc Strong Metal Stainless Steel Hangers Heavy Duty Coat Hanger Non Slip 42cm',
    'Sunbeam Royal Luxe Mushroom Heated Blanket 10-Heat Settings Auto Shut Off Twin',
    'MOVA P10 Pro Ultra Gen2 Robot Vacuum with 26,000Pa Suction & Self-Cleaning Dock',
    'HEADSET-PRO X 2 LIGHTSPEED Wireless Gaming Headset-WHITE-2.4GHZ- 981-001268',
])
def test_pack_and_feature_tokens_are_not_exact_models(title):
    query, exact = amazon_model_query(title, 'buying guide')
    assert not exact
    assert len(query.split()) >= 5
    assert query != 'MOVA 000Pa'

def test_real_model_code_still_produces_focused_search():
    assert amazon_model_query('Sony WH-1000XM5 Wireless Headphones', 'headphones') == ('Sony WH1000XM5', True)
