"""Verify and repair publication metadata without blocking the daily publisher.

Browser probes intercept analytics traffic and capture the existing click handler
locally. A passing probe is NOT confirmation that GA4 received a production event.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from post_publish_seo import changed_posts, recent_posts, public_url, same_site
from src.blogger import BloggerClient
from src.publication_quality import CONFIG, affiliate_issues, choose_description, duplicate_descriptions, description_conflicts
from src.publishing_seo import description_for, repair_metadata
from src.site_config import get_site_host, get_site_config

ROOT = Path(__file__).resolve().parent
RECEIPT = 'not tested: no synthetic events are sent to production GA4'

PROBE = r'''() => {
  const body=document.querySelector('.post-body');
  const links=Array.from((body||document).querySelectorAll('a[href]')).map(a=>({href:a.href,rel:a.getAttribute('rel')||''}));
  const scripts=Array.from(document.scripts).map(s=>s.textContent||'').join('\n');
  const properties=Array.from(scripts.matchAll(/gtag\s*\(\s*['"]config['"]\s*,\s*['"](G-[A-Z0-9]+)['"]/g)).map(m=>m[1]);
  const calls=[];
  const link=body&&Array.from(body.querySelectorAll('a[href]')).find(a=>{
    const host=new URL(a.href).hostname.replace(/^www\./,'');
    return ['ebay.co.uk','ebay.com','amazon.co.uk','amazon.com'].includes(host);
  });
  const original=window.gtag;
  if(link){
    const prevent=e=>e.preventDefault();
    window.gtag=(...args)=>calls.push(args);
    document.addEventListener('click',prevent,true);
    try{link.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));}
    finally{document.removeEventListener('click',prevent,true);window.gtag=original;}
  }
  return {
    description:Array.from(document.head.querySelectorAll('meta[name="description"]')).map(m=>m.content),
    ogDescription:Array.from(document.head.querySelectorAll('meta[property="og:description"]')).map(m=>m.content),
    canonical:document.querySelector('link[rel="canonical"]')?.href||null,
    articlePresent:!!body,links,configuredProperties:properties,gtagPresent:typeof original==='function',
    testedRetailerLink:!!link,events:calls.filter(c=>c[0]==='event'&&c[1]==='wb_retailer_click'),
    imageCount:body?body.querySelectorAll('img').length:0
  };
}'''


def assess(observed, article, market, url):
    expected = description_for(article, market)
    issues = []
    conflicts = description_conflicts(article, market)
    if conflicts:
        issues.append('description still shared with another guide; editorial review needed')
    if not observed.get('articlePresent'):
        issues.append('article body missing')
    if observed.get('description') != [expected]:
        issues.append('rendered description missing, duplicated or differs from intended copy')
    if observed.get('ogDescription') != [expected]:
        issues.append('social description missing, duplicated or differs from intended copy')
    if observed.get('canonical') != url:
        issues.append('canonical differs from published URL')
    issues.extend(affiliate_issues(observed.get('links', []), market, article['slug']))
    prop = CONFIG[market]['property']
    properties = observed.get('configuredProperties', [])
    if prop not in properties or any(p != prop for p in properties):
        issues.append('regional GA4 configuration missing or conflicts with another property')
    if not observed.get('gtagPresent'):
        issues.append('GA4 tag function unavailable')
    if observed.get('testedRetailerLink'):
        events = observed.get('events', [])
        if len(events) != 1:
            issues.append('retailer click must produce exactly one event')
        elif (events[0][2].get('send_to') not in {None, prop}
              or events[0][2].get('article_slug') != article['slug']):
            issues.append('retailer click has incorrect regional or article attribution')
    return {'verification': 'passed' if not issues else 'needs_attention', 'issues': issues,
            'description': expected, 'description_source_issues': choose_description(article, market, duplicate_descriptions(market))[1],
            'description_conflicts': conflicts,
            'ga4_receipt': RECEIPT, 'retailer_probe': 'tested locally' if observed.get('testedRetailerLink') else 'no direct retailer link to test',
            'observed': observed}


def render_probe(browser, article, market, url):
    context = browser.new_context(service_workers='block')
    # Do not add test page views, ad impressions or retailer clicks to real accounts.
    def route(request):
        host = (urlsplit(request.request.url).hostname or '').lower()
        if (host.endswith('.google-analytics.com') or host == 'google-analytics.com'
                or host.endswith('.doubleclick.net') or host.endswith('.googlesyndication.com')):
            request.abort()
        else:
            request.continue_()
    context.route('**/*', route)
    page = context.new_page()
    try:
        separator = '&' if '?' in url else '?'
        check_url = url + separator + 'wb_quality=' + str(int(datetime.now(timezone.utc).timestamp() * 1000))
        response = page.goto(check_url, wait_until='domcontentloaded', timeout=20000)
        if not response or response.status >= 400:
            raise RuntimeError('PublicPageUnavailable')
        if not same_site(page.url, get_site_host(market)):
            raise RuntimeError('UnexpectedRedirectHost')
        page.locator('.post-body').first.wait_for(state='attached', timeout=5000)
        # Wait for the publication bridge to execute, without waiting for every ad/image.
        try:
            page.wait_for_function("document.querySelector('script.wb-published-seo') && document.querySelector('meta[name=description]')", timeout=5000)
        except Exception:
            pass  # assess() records missing metadata rather than calling it a pass.
        return assess(page.evaluate(PROBE), article, market, url)
    finally:
        context.close()


def repairable(result):
    return any(('description' in issue or 'affiliate' in issue or 'qualification' in issue or 'retailer click' in issue)
               for issue in result.get('issues', []))


def verify_one(probe, article, market, post, client=None):
    url = public_url(str(post['url']), market)
    if not url:
        return {'verification': 'unconfirmed', 'issues': ['URL outside the active site'], 'ga4_receipt': RECEIPT}
    try:
        first = probe(article, market, url)
        if first['verification'] == 'passed' or not client or not repairable(first):
            return first
        stored = client.get_post(str(post['post_id']))
        # Repair only scripts and affiliate attributes; never replace editorial copy,
        # hero images, post dates, labels, title or URL with generated source content.
        repaired = repair_metadata(client, stored, article, market)
        second = probe(article, market, url)
        second['repair'] = {'attempted': True, 'stored_content_changed': repaired.get('content') != stored.get('content'),
                            'before_issues': first['issues']}
        return second
    except Exception as exc:
        return {'verification': 'unconfirmed', 'issues': [type(exc).__name__], 'ga4_receipt': RECEIPT}


def checkpoint(path, report):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def run(market, recent=None, read_only=False):
    path = ROOT / 'reports' / f'publication-quality-{market}.json'
    report = {'market': market, 'created_at': datetime.now(timezone.utc).isoformat(), 'complete': False,
              'attention_required': True, 'ga4_receipt': RECEIPT, 'posts': {}, 'read_only': read_only}
    checkpoint(path, report)
    posts = recent_posts(market, recent) if recent else changed_posts(market)
    # Code-only updates still verify a small live sample, including on deployment.
    if not posts and recent is None:
        posts = recent_posts(market, 3)
    client = None
    if not read_only:
        try:
            client = BloggerClient.from_env()
            hosts = {get_site_host(market), urlsplit(get_site_config(market)['blogspot_url']).hostname}
            client.resolve_blog(hosts, 'Worth Buying ' + ('UK' if market == 'uk' else 'USA'))
        except Exception as exc:
            report['repair_unavailable'] = type(exc).__name__
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for post in posts:
                    name = str(post.get('source_file') or '')
                    if not name or Path(name).name != name:
                        report['posts'][str(post.get('post_id'))] = {'verification': 'unconfirmed', 'issues': ['invalid source file']}
                        checkpoint(path, report)
                        continue
                    try:
                        folder = 'articles' if market == 'uk' else 'articles-us'
                        article = json.loads((ROOT / folder / name).read_text(encoding='utf-8'))
                        result = verify_one(lambda a, m, u: render_probe(browser, a, m, u), article, market, post, client)
                        result['url'] = public_url(str(post['url']), market)
                        report['posts'][article['slug']] = result
                    except Exception as exc:
                        report['posts'][name] = {'verification': 'unconfirmed', 'issues': [type(exc).__name__]}
                    checkpoint(path, report)
            finally:
                browser.close()
    except Exception as exc:
        report['browser_unavailable'] = type(exc).__name__
    report['complete'] = 'browser_unavailable' not in report
    report['attention_required'] = (not report['complete'] or any(r['verification'] != 'passed' for r in report['posts'].values()))
    checkpoint(path, report)
    rows = '\n'.join(f'| {html.escape(slug)} | {row["verification"]} | {html.escape("; ".join(row.get("issues", [])))} |'
                     for slug, row in report['posts'].items())
    summary = (f'\n## {market.upper()} publication quality\n\n'
               f'Complete: {report["complete"]}; attention required: {report["attention_required"]}.\n\n'
               '| Article | Result | Unresolved checks |\n|---|---|---|\n' + rows +
               '\n\nTracking probes are captured locally. This does not confirm production GA4 receipt. '
               'Indexing requests and Google ranking decisions remain separate.\n')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a', encoding='utf-8') as handle:
            handle.write(summary)
    if report['attention_required']:
        print(f'::warning title=Publication quality::{market.upper()} has unresolved or unconfirmed checks; see publication-quality-{market}.json')
    print(f'[publication-quality] {market.upper()}: {len(report["posts"])} checked; complete={report["complete"]}; attention={report["attention_required"]}')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--market', choices=['uk', 'us'], required=True)
    parser.add_argument('--recent', type=int, choices=range(1, 51))
    parser.add_argument('--read-only', action='store_true')
    args = parser.parse_args()
    run(args.market, args.recent, args.read_only)
