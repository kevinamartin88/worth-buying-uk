"""Honest, non-blocking records of discovery submission and index inspection."""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


def inspection_record(status: dict) -> dict:
    verdict = str(status.get('verdict') or '')
    coverage = str(status.get('coverageState') or '')
    if verdict == 'PASS':
        state = 'indexed'
    elif verdict in {'FAIL', 'NEUTRAL'} or coverage:
        state = 'not_indexed'
    else:
        state = 'unconfirmed'
    return {'state': state, 'verdict': verdict, 'coverage': coverage,
            'last_crawl': status.get('lastCrawlTime'),
            'google_canonical': status.get('googleCanonical'),
            'user_canonical': status.get('userCanonical'),
            'robots_state': status.get('robotsTxtState'),
            'indexing_state': status.get('indexingState'),
            'fetch_state': status.get('pageFetchState')}


def next_action(url: str, row: dict) -> str:
    state = row.get('state')
    if state == 'indexed':
        canonical = row.get('google_canonical')
        if canonical and canonical != url:
            return 'Review Google’s selected canonical before requesting this URL.'
        return 'Already indexed; allow time for Google to refresh changed content.'
    if state == 'not_indexed':
        if row.get('robots_state') == 'DISALLOWED' or row.get('indexing_state') in {
            'BLOCKED_BY_META_TAG', 'BLOCKED_BY_HTTP_HEADER'}:
            return 'Review the reported crawl/indexing block before requesting indexing.'
        return 'Live-test in Search Console; request indexing once for an important new or substantially improved guide if not already requested.'
    return 'Index status unconfirmed; check Search Console and the next follow-up report.'


def new_report(market: str, urls: list[str], mode: str) -> dict:
    return {'market': market, 'mode': mode, 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'workflow_run_id': os.getenv('GITHUB_RUN_ID'), 'complete': False,
            'individual_indexing_requests_submitted': False,
            'google': {'property': None, 'sitemaps': [], 'inspections': {
                url: {'state': 'unconfirmed'} for url in urls}},
            'public_checks': {},
            'note': 'Sitemap submission does not confirm crawling, indexing or ranking. URL Inspection API reports Google’s stored index status, not a live test.'}


def save_report(path: Path, report: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        temporary.replace(path)
    except OSError as exc:
        print(f'[seo-warning] Discovery report could not be saved: {type(exc).__name__}')


def write_summary(report: dict) -> None:
    target = os.getenv('GITHUB_STEP_SUMMARY')
    if not target:
        return
    google = report['google']
    property_name = google.get('property')
    property_link = ('https://search.google.com/search-console?resource_id=' + quote(property_name, safe='')
                     if property_name else None)
    rows = []
    for url, record in google['inspections'].items():
        public = report['public_checks'].get(url, {})
        sitemap = public.get('sitemap_contains_url')
        inclusion = 'Yes' if sitemap is True else 'No — review discovery' if sitemap is False else 'Not confirmed'
        page_status = str(public.get('http_status') or public.get('page_check_error') or 'Not rechecked')
        rows.append('<tr><td><a href="' + html.escape(url, quote=True) + '">' + html.escape(url) + '</a></td>'
                    '<td>' + inclusion + '</td><td>' + html.escape(page_status) + '</td>'
                    '<td>' + html.escape(record.get('coverage') or record['state']) + '</td>'
                    '<td>' + html.escape(next_action(url, record)) + '</td></tr>')
    feeds = '\n'.join('- ' + str(x['url']) + ': **' + str(x['state']) + '**'
                      for x in google.get('sitemaps', [])) or '- No sitemap submission confirmed.'
    summary = (f'\n## {report["market"].upper()} Google discovery: {report["mode"]}\n\n'
               f'Report complete: **{report["complete"]}**. Individual indexing requests submitted by this workflow: **No**.\n\n'
               + (f'[Open the matching Search Console property]({property_link})\n\n' if property_link else
                  'Search Console property not confirmed.\n\n')
               + feeds + '\n\n<table><tr><th>Guide</th><th>In sitemap</th><th>Public HTTP check</th><th>Google index status</th><th>Next action</th></tr>'
               + ''.join(rows) + '</table>\n\n' + report['note'] + '\n')
    try:
        with Path(target).open('a', encoding='utf-8') as handle:
            handle.write(summary)
    except OSError as exc:
        print(f'[seo-warning] Discovery summary could not be written: {type(exc).__name__}')
