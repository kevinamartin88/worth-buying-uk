const CONFIG = {
  "bedfordthemeparkstays.com": {
    upstream: "https://bedford-theme-park-stays.pages.dev",
    title: "Bedford Theme Park Stays | Hotels & Family Accommodation in Bedford",
    description: "Plan ahead for Bedford's future theme park with an independent guide to hotels, holiday lets, serviced apartments and family accommodation across Bedford.",
    h1: "Places to stay near Bedford's future theme park.",
    ogTitle: "Bedford Theme Park Stays | Independent Bedford Accommodation Guide",
    sectionTitle: "Plan your stay around Bedford's future theme park",
    sectionText: "Bedford Theme Park Stays is an independent accommodation guide being developed for future visitors to Bedfordshire. Explore hotels, holiday lets, serviced apartments and family stays across Bedford and the surrounding area while planning ahead for the major new theme park and other local attractions.",
    bullets: [
      "Hotels in Bedford for couples, families and groups",
      "Holiday lets and larger stays for family trips",
      "Serviced apartments for flexible visits",
      "Independent guidance for future Bedfordshire theme park trips"
    ]
  },
  "bedfordstayfinder.com": {
    upstream: "https://bedford-stay-finder.pages.dev",
    title: "Bedford Stay Finder | Hotels, Holiday Lets & Apartments in Bedford",
    description: "Independent Bedford accommodation finder for hotels, holiday lets, B&Bs and serviced apartments for weekends, work trips, family visits and future attractions.",
    h1: "Find hotels and places to stay in Bedford.",
    ogTitle: "Bedford Stay Finder | Find Accommodation in Bedford",
    sectionTitle: "Find the right Bedford stay for your trip",
    sectionText: "Bedford Stay Finder is being built as an independent place to discover accommodation across Bedford and nearby Bedfordshire. Whether you are planning a weekend, a family visit, a work trip or a future visit to new attractions in the area, compare the types of stays that may suit your plans.",
    bullets: [
      "Bedford hotels and independent accommodation",
      "Holiday lets for families and groups",
      "Bed and breakfasts and guest houses",
      "Serviced apartments and flexible longer stays"
    ]
  },
  "stayinbedfordshire.com": {
    upstream: "https://stay-in-bedfordshire.pages.dev",
    title: "Stay in Bedfordshire | Hotels, Cottages, B&Bs & Places to Stay",
    description: "Independent guide to places to stay across Bedfordshire, from hotels and B&Bs to holiday cottages and serviced apartments for countryside breaks and local visits.",
    h1: "Find your perfect place to stay in Bedfordshire.",
    ogTitle: "Stay in Bedfordshire | Independent Accommodation Guide",
    sectionTitle: "Discover places to stay across Bedfordshire",
    sectionText: "From Bedford and market towns to countryside escapes, Stay in Bedfordshire is being developed as an independent guide to accommodation across the county. Plan family visits, relaxing weekends, work trips and longer stays while discovering hotels, cottages, B&Bs and apartments.",
    bullets: [
      "Hotels and guest accommodation across Bedfordshire",
      "Holiday cottages for countryside breaks",
      "B&Bs and independent guest houses",
      "Apartments and flexible stays for work or longer visits"
    ]
  }
};

function esc(value) {
  return String(value).replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[char]));
}

function robots(host) {
  return new Response(
    "User-agent: *\nAllow: /\nSitemap: https://" + host + "/sitemap.xml\n",
    { headers: { "content-type": "text/plain; charset=UTF-8" } }
  );
}

function sitemap(host) {
  const urls = host === "staycloseto.com"
    ? ["https://staycloseto.com/"]
    : ["https://" + host + "/", "https://" + host + "/contact"];
  const body = '<?xml version="1.0" encoding="UTF-8"?>' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
    urls.map(url => '<url><loc>' + url + '</loc></url>').join("") +
    '</urlset>';
  return new Response(body, {
    headers: { "content-type": "application/xml; charset=UTF-8" }
  });
}

function stayCloseToPage() {
  return new Response(`<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stay Close To | Accommodation Near Attractions, Events & Destinations</title>
<meta name="description" content="Independent accommodation discovery for people who want to stay close to attractions, events and destinations. The Stay Close To platform is in development.">
<meta name="robots" content="index,follow">
<link rel="canonical" href="https://staycloseto.com/">
<meta property="og:title" content="Stay Close To | Accommodation Near Attractions & Events">
<meta property="og:description" content="An independent accommodation discovery brand for stays near attractions, events and destinations.">
<meta property="og:url" content="https://staycloseto.com/">
<meta property="og:type" content="website">
<meta property="og:locale" content="en_GB">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"WebSite","name":"Stay Close To","url":"https://staycloseto.com/","description":"Independent accommodation discovery for stays near attractions, events and destinations.","inLanguage":"en-GB"}</script>
<style>
:root{--navy:#081a2f;--blue:#1976d2;--sky:#eaf5ff;--text:#172033;--muted:#64748b}
*{box-sizing:border-box}
body{margin:0;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;color:var(--text);background:#f7f9fc;line-height:1.65}
header{background:var(--navy);color:#fff;padding:24px 0}
.wrap{width:min(1100px,calc(100% - 40px));margin:auto}
.brand{font-size:22px;font-weight:800}
.hero{background:linear-gradient(135deg,#081a2f,#123f67);color:#fff;padding:110px 0}
.eyebrow{font-weight:700;color:#9dd2ff}
.hero h1{font-size:clamp(42px,6vw,72px);line-height:1.05;max-width:850px;margin:15px 0 22px}
.hero p{max-width:720px;font-size:20px;color:rgba(255,255,255,.82)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;padding:70px 0}
.card{background:#fff;border:1px solid #dfe7ef;border-radius:20px;padding:28px;box-shadow:0 16px 40px rgba(5,27,52,.07)}
.card h2{color:var(--navy);font-size:22px}
.coming{background:var(--sky);padding:60px 0}
.coming h2{font-size:34px;color:var(--navy)}
footer{background:#061321;color:rgba(255,255,255,.7);padding:35px 0}
@media(max-width:750px){.grid{grid-template-columns:1fr}.hero{padding:80px 0}}
</style>
</head>
<body>
<header><div class="wrap brand">Stay Close To</div></header>
<main>
<section class="hero"><div class="wrap"><div class="eyebrow">Independent accommodation discovery</div><h1>Stay close to the places that bring you here.</h1><p>We're building a simple way to discover places to stay near attractions, events, venues and destinations. Stay Close To is an independent accommodation brand in development.</p></div></section>
<section><div class="wrap grid">
<div class="card"><h2>Stay close to attractions</h2><p>Discover accommodation options for future visits to theme parks, visitor attractions and family destinations.</p></div>
<div class="card"><h2>Stay close to events</h2><p>Plan accommodation around concerts, sporting events, exhibitions and major local occasions.</p></div>
<div class="card"><h2>Stay close to destinations</h2><p>Find hotels, holiday lets and apartments that can make a short break or longer trip more convenient.</p></div>
</div></section>
<section class="coming"><div class="wrap"><h2>Accommodation discovery is coming soon.</h2><p>We're developing the platform now. Listings and bookings are not yet available.</p></div></section>
</main>
<footer><div class="wrap">© 2026 Stay Close To · Independent accommodation information website.</div></footer>
</body>
</html>`, {
    headers: { "content-type": "text/html; charset=UTF-8" }
  });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const host = url.hostname.replace(/^www\./, "");

    if (url.pathname === "/robots.txt") return robots(host);
    if (url.pathname === "/sitemap.xml") return sitemap(host);
    if (host === "staycloseto.com") return stayCloseToPage();

    const cfg = CONFIG[host];
    if (!cfg) return new Response("Not found", { status: 404 });

    const upstreamUrl = new URL(url.pathname + url.search, cfg.upstream);
    const upstreamResponse = await fetch(new Request(upstreamUrl, request));
    const contentType = upstreamResponse.headers.get("content-type") || "";

    if (!contentType.includes("text/html") || url.pathname !== "/") {
      return upstreamResponse;
    }

    const schema = JSON.stringify({
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "WebSite",
          "url": "https://" + host + "/",
          "name": cfg.ogTitle.split("|")[0].trim(),
          "description": cfg.description,
          "inLanguage": "en-GB"
        },
        {
          "@type": "Organization",
          "url": "https://" + host + "/",
          "name": cfg.ogTitle.split("|")[0].trim()
        }
      ]
    });

    const section =
      '<section style="padding:80px 0;background:#fff">' +
      '<div style="width:min(1100px,calc(100% - 40px));margin:0 auto">' +
      '<div style="max-width:820px;margin:0 auto;text-align:center">' +
      '<div style="font-size:13px;font-weight:800;text-transform:uppercase;letter-spacing:1.2px;color:#1976d2">Plan your visit</div>' +
      '<h2 style="font-size:clamp(30px,4vw,44px);line-height:1.15;color:#081a2f;margin:12px 0 16px">' + esc(cfg.sectionTitle) + '</h2>' +
      '<p style="font-size:17px;color:#64748b">' + esc(cfg.sectionText) + '</p>' +
      '<ul style="text-align:left;max-width:680px;margin:28px auto 0;color:#334155;line-height:1.8">' +
      cfg.bullets.map(item => '<li>' + esc(item) + '</li>').join("") +
      '</ul></div></div></section>';

    return new HTMLRewriter()
      .on("title", { element(e) { e.setInnerContent(cfg.title); } })
      .on('meta[name="description"]', { element(e) { e.setAttribute("content", cfg.description); } })
      .on('meta[name="keywords"]', { element(e) { e.remove(); } })
      .on('meta[property="og:title"]', { element(e) { e.setAttribute("content", cfg.ogTitle); } })
      .on('meta[property="og:description"]', { element(e) { e.setAttribute("content", cfg.description); } })
      .on("h1", { element(e) { e.setInnerContent(cfg.h1); } })
      .on("head", { element(e) {
        e.append(
          '<meta property="og:locale" content="en_GB">' +
          '<meta name="twitter:card" content="summary_large_image">' +
          '<meta name="twitter:title" content="' + esc(cfg.ogTitle) + '">' +
          '<meta name="twitter:description" content="' + esc(cfg.description) + '">' +
          '<script type="application/ld+json">' + schema + '<\/script>',
          { html: true }
        );
      }})
      .on("main", { element(e) { e.append(section, { html: true }); } })
      .transform(upstreamResponse);
  }
};
