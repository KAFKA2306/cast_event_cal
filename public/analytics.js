(() => {
  const current = document.currentScript;
  const configUrl = current?.dataset.config || 'analytics-config.json';
  const safe = (value, limit = 80) => String(value || '').slice(0, limit);
  const send = (name, params = {}) => { if (typeof window.gtag === 'function') window.gtag('event', name, params); };
  fetch(configUrl, { cache: 'no-store' }).then(r => r.ok ? r.json() : {}).then(config => {
    const id = safe(config.ga4_measurement_id);
    if (!/^G-[A-Z0-9]+$/.test(id)) return;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function(){ dataLayer.push(arguments); };
    gtag('js', new Date());
    gtag('config', id, { allow_google_signals: false });
    const tag = document.createElement('script');
    tag.async = true;
    tag.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
    document.head.appendChild(tag);
    if (document.body.dataset.pageKind === 'event-detail') {
      send('event_detail_open', {
        event_id: safe(document.body.dataset.eventId),
        category: safe(document.body.dataset.category),
      });
    }
  }).catch(() => {});
  document.addEventListener('click', event => {
    const target = event.target.closest('[data-track]');
    if (!target) return;
    send(safe(target.dataset.track), {
      event_id: safe(target.dataset.eventId),
      category: safe(target.dataset.category),
      destination_type: safe(target.dataset.destinationType),
    });
  });
  document.addEventListener('change', event => {
    if (event.target.matches('#category,#source')) send('filter_change', { filter: event.target.id });
  });
  document.addEventListener('click', event => {
    const range = event.target.closest('[data-range]');
    if (range) send('filter_change', { filter: 'range', range: safe(range.dataset.range) });
  });
  let searched = false;
  document.addEventListener('input', event => {
    if (!searched && event.target.matches('#q') && String(event.target.value || '').trim()) {
      searched = true;
      send('site_search_used');
    }
  });
})();
