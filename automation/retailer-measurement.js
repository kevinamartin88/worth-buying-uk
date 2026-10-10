/* Install once in each Blogger theme. Reuse the regional GA4 tag. */
(function () {
  if (window.wbRetailerMeasurement) return;
  window.wbRetailerMeasurement = true;
  var properties = {
    'www.worthbuyinguk.co.uk': 'G-KL9MHT5ZJ1',
    'worthbuyinguk.blogspot.com': 'G-KL9MHT5ZJ1',
    'www.worthbuyingusa.com': 'G-EEYCNV01MN',
    'worthbuyingusa.blogspot.com': 'G-EEYCNV01MN'
  };
  var property = properties[location.hostname];
  if (!property) return;
  document.addEventListener('click', function (event) {
    var target = event.target;
    var link = target && target.closest && target.closest('a[href]');
    if (!link || typeof window.gtag !== 'function') return;
    var url;
    try { url = new URL(link.href); } catch (_) { return; }
    if (url.protocol !== 'https:' && url.protocol !== 'http:') return;
    var host = url.hostname.toLowerCase().replace(/^www\./, '');
    var retailer = link.getAttribute('data-wb-retailer');
    if (!retailer) {
      if (host === 'amazon.co.uk' || host === 'amazon.com' || host === 'amzn.to') retailer = 'amazon';
      if (host === 'ebay.co.uk' || host === 'ebay.com' || host === 'ebay.us' || host === 'rover.ebay.com') retailer = 'ebay';
      if (host === 'click.linksynergy.com' || host === 'linksynergy.com' || host === 'go.linksynergy.com') retailer = 'rakuten';
    }
    if (!retailer || url.hostname === location.hostname) return;
    var root = link.closest('[data-wb-article]');
    var post = link.closest('.post-body');
    var metadata = post && post.querySelector('script.wb-published-seo[data-wb-article]');
    var params = {
      article_slug: root ? root.getAttribute('data-wb-article') :
        (metadata ? metadata.getAttribute('data-wb-article') : location.pathname),
      retailer: retailer,
      placement: link.getAttribute('data-wb-placement') || 'article',
      link_url: link.href,
      transport_type: 'beacon',
      send_to: property
    };
    var experiment = root && root.getAttribute('data-wb-experiment');
    if (experiment) params.experiment_id = experiment;
    window.gtag('event', 'wb_retailer_click', params);
  });
}());
