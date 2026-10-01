(() => {
  const current = document.currentScript;
  const configUrl = current?.dataset.config || 'analytics-config.json';
  const consentKey = 'cast-event-cal.analytics-consent.v1';
  const safe = (value, limit = 80) => String(value || '').slice(0, limit);
  const privacyOptOut = () => navigator.globalPrivacyControl === true || navigator.doNotTrack === '1' || window.doNotTrack === '1';
  const readConsent = () => {
    if (privacyOptOut()) return 'denied';
    try {
      const value = localStorage.getItem(consentKey);
      return value === 'granted' || value === 'denied' ? value : 'unknown';
    } catch (_) {
      return 'unknown';
    }
  };
  const writeConsent = value => {
    try { localStorage.setItem(consentKey, value); } catch (_) {}
  };
  let consent = readConsent();
  let initialized = false;

  const send = (name, params = {}) => {
    if (consent !== 'granted' || privacyOptOut()) return;
    if (typeof window.gtag === 'function') window.gtag('event', name, params);
  };

  const initAnalytics = ({ includePageOpen = false } = {}) => {
    if (initialized || consent !== 'granted' || privacyOptOut()) return;
    initialized = true;
    fetch(configUrl, { cache: 'no-store' }).then(r => r.ok ? r.json() : {}).then(config => {
      const id = safe(config.ga4_measurement_id);
      if (!/^G-[A-Z0-9]+$/.test(id) || consent !== 'granted' || privacyOptOut()) return;
      window.dataLayer = window.dataLayer || [];
      window.gtag = function(){ dataLayer.push(arguments); };
      gtag('js', new Date());
      gtag('config', id, {
        allow_google_signals: false,
        allow_ad_personalization_signals: false,
        ads_data_redaction: true,
        send_page_view: false,
      });
      const tag = document.createElement('script');
      tag.async = true;
      tag.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
      document.head.appendChild(tag);
      if (includePageOpen && document.body.dataset.pageKind === 'event-detail') {
        send('event_detail_open', {
          event_id: safe(document.body.dataset.eventId),
          category: safe(document.body.dataset.category),
        });
      }
    }).catch(() => {});
  };

  const showConsent = () => {
    if (consent !== 'unknown' || privacyOptOut()) return;
    const banner = document.createElement('div');
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-label', 'アクセス解析の設定');
    banner.dataset.analyticsConsent = '';
    banner.innerHTML = '<span>サイト改善のため匿名の利用状況を計測してもよいですか？</span> <button type="button" data-consent="granted">許可する</button> <button type="button" data-consent="denied">許可しない</button>';
    banner.addEventListener('click', event => {
      const choice = event.target.closest('[data-consent]')?.dataset.consent;
      if (choice !== 'granted' && choice !== 'denied') return;
      consent = choice;
      writeConsent(choice);
      banner.remove();
      if (choice === 'granted') initAnalytics({ includePageOpen: false });
    });
    document.body.appendChild(banner);
  };

  if (consent === 'granted') initAnalytics({ includePageOpen: true });
  else if (consent === 'unknown') showConsent();

  document.addEventListener('click', event => {
    const target = event.target.closest('[data-track]');
    if (!target) return;
    send(safe(target.dataset.track), {
      event_id: safe(target.dataset.eventId),
      category: safe(target.dataset.category),
      destination_type: safe(target.dataset.destinationType),
      campaign_id: safe(target.dataset.campaignId),
      promotion_type: safe(target.dataset.promotionType),
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
