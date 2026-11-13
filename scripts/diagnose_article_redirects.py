"""Bounded, read-only redirect evidence for four Search Console exclusions."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

TARGETS = [
    'https://www.worthbuyinguk.co.uk/2026/11/4-best-luggage-uk-2026-picks-from-2535.html',
    'https://www.worthbuyinguk.co.uk/2026/11/4-best-office-chairs-uk-2026-picks-from.html',
    'https://www.worthbuyingusa.com/2026/10/best-large-capacity-air-fryers-worth.html',
    'https://www.worthbuyingusa.com/2026/11/4-best-luggage-usa-2026-picks-from-5985.html',
]
DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
MOBILE = 'Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36'
SMARTPHONE = MOBILE + ' (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class Head(HTMLParser):
    def __init__(self):
        super().__init__(); self.canonical=[]; self.robots=[]; self.refresh=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='link' and a.get('rel')=='canonical': self.canonical.append(a.get('href'))
        if tag=='meta' and a.get('name','').lower() in ('robots','googlebot'): self.robots.append(a.get('content'))
        if tag=='meta' and a.get('http-equiv','').lower()=='refresh': self.refresh.append(a.get('content'))

def trace(url, ua):
    opener=build_opener(NoRedirect())
    hops=[]; seen=set(); current=url
    for _ in range(7):
        if current in seen: return {'hops':hops,'error':'redirect loop'}
        seen.add(current)
        if urlsplit(current).hostname not in {'www.worthbuyinguk.co.uk','worthbuyinguk.co.uk','www.worthbuyingusa.com','worthbuyingusa.com','worthbuyinguk.blogspot.com','worthbuyingusa.blogspot.com'}:
            return {'hops':hops,'error':'unexpected redirect host','destination':current}
        try:
            response=opener.open(Request(current,headers={'User-Agent':ua}),timeout=20)
        except HTTPError as exc:
            response=exc
        except (URLError, OSError) as exc:
            return {'hops':hops,'error':str(exc)}
        with response:
            code=response.code; headers=response.headers
            hop={'url':current,'status':code,'location':headers.get('Location'),
                 'server':headers.get('Server'),'vary':headers.get('Vary'),
                 'x_robots_tag':headers.get('X-Robots-Tag')}
            hops.append(hop)
            if code in (301,302,303,307,308):
                if not hop['location']: return {'hops':hops,'error':'missing Location'}
                current=urljoin(current,hop['location']); time.sleep(.7); continue
            raw=response.read(1000000).decode('utf-8','replace')
            head=Head();head.feed(raw)
            return {'hops':hops,'final_url':current,'final_status':code,
                    'canonical':head.canonical,'robots':head.robots,'meta_refresh':head.refresh,
                    'article_present':'post-body-' in raw,
                    'javascript_location_write':any(s in raw for s in ('location.replace(', 'location.assign(', 'location.href =', 'location.href='))}
    return {'hops':hops,'error':'redirect chain exceeded seven hops'}

def main():
    report={'created_at':datetime.now(timezone.utc).isoformat(),
            'note':'User-agent simulation is not a verified Googlebot request. No publication or site configuration is changed.',
            'dns':{},'results':[]}
    blocked=set()
    for host in ('worthbuyinguk.co.uk','www.worthbuyinguk.co.uk','worthbuyingusa.com','www.worthbuyingusa.com'):
        try: report['dns'][host]=socket.gethostbyname_ex(host)
        except OSError as exc: report['dns'][host]={'error':str(exc)}
    for url in TARGETS:
        for label,ua,target in [('desktop',DESKTOP,url),('mobile',MOBILE,url),('googlebot-smartphone',SMARTPHONE,url),('googlebot-explicit-mobile',SMARTPHONE,url+'?m=1')]:
            host=urlsplit(target).hostname
            if host in blocked:
                report['results'].append({'url':target,'agent':label,'skipped':'Host returned 429; stopped without retries'});continue
            result={'url':target,'agent':label,**trace(target,ua)}
            report['results'].append(result)
            print(json.dumps(result),flush=True)
            if any(h['status']==429 for h in result.get('hops',[])):blocked.add(host)
            time.sleep(1)
    path=Path('reports/article-redirect-diagnostic.json');path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__': main()
