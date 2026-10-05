import argparse
import json
from pathlib import Path
from src.price_charts import render_chart


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--market', choices=('uk', 'us'), required=True)
    market = parser.parse_args().market
    root = Path(__file__).resolve().parent
    target = root / 'assets/price-history' / market
    target.mkdir(parents=True, exist_ok=True)
    (target / '.gitkeep').touch()
    history = json.loads((root / 'state/daily_price_history.json').read_text(encoding='utf-8'))
    generated = 0
    for key, entry in history.items():
        if key.startswith(f'daily|{market}|') and render_chart(key, entry, market):
            generated += 1
    print(f'[price-charts] {market.upper()}: {generated} charts with real dated observations')


if __name__ == '__main__':
    main()
