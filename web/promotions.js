(() => {
  'use strict';

  const current = document.currentScript;
  const configUrl = current?.dataset.config || 'promotions.json';
  const eventsUrl = current?.dataset.events || 'events.json';
  const pageKind = document.body.dataset.pageKind || 'home';
  const pageCategory = document.body.dataset.category || '';

  const jstDateKey = value =>
    new Intl.DateTimeFormat('sv-SE', {
      timeZone: 'Asia/Tokyo',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).format(new Date(value));

  const active = (promotion, now) => {
    if (promotion?.status !== 'approved') return false;
    const start = new Date(promotion.starts_at);
    const end = new Date(promotion.ends_at);
    return Number.isFinite(start.getTime()) &&
      Number.isFinite(end.getTime()) &&
      now >= start &&
      now < end;
  };

  const eligibleForPage = (promotion, event, now) => {
    const placements = Array.isArray(promotion.placements) ? promotion.placements : [];
    if (pageKind === 'category-landing') {
      return placements.includes('category') && event.category === pageCategory;
    }
    if (pageKind === 'tonight') {
      if (!placements.includes('tonight')) return false;
      const start = new Date(event.starts_at);
      const end = event.ends_at ? new Date(event.ends_at) : null;
      const stillRelevant = end && Number.isFinite(end.getTime()) ? end >= now : start >= now;
      return stillRelevant && jstDateKey(start) === jstDateKey(now);
    }
    return placements.includes('home');
  };

  const formatJst = value =>
    new Intl.DateTimeFormat('ja-JP', {
      timeZone: 'Asia/Tokyo',
      month: 'numeric',
      day: 'numeric',
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).format(new Date(value));

  const addStyles = () => {
    if (document.getElementById('promotion-overlay-style')) return;
    const style = document.createElement('style');
    style.id = 'promotion-overlay-style';
    style.textContent = `
      .promotion-overlay{margin:0 0 20px;padding:16px;border:1px solid rgba(185,168,230,.72);border-radius:18px;background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(244,241,252,.96));box-shadow:0 14px 36px rgba(76,91,125,.08)}
      .promotion-overlay-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
      .promotion-badge{display:inline-flex;align-items:center;padding:5px 9px;border-radius:999px;background:#243653;color:#fff;font-size:.72rem;font-weight:850;letter-spacing:.04em}
      .promotion-disclosure{font-size:.72rem;color:#66758d;font-weight:800}
      .promotion-list{display:grid;gap:10px}
      .promotion-card{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:13px;border:1px solid #dfe6ef;border-radius:14px;background:#fff}
      .promotion-card h2{margin:0 0 4px;font-size:1rem;line-height:1.45}
      .promotion-meta{color:#66758d;font-size:.78rem;line-height:1.5}
      .promotion-action{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:9px 13px;border-radius:999px;background:#243653;color:#fff;text-decoration:none;font-weight:800;white-space:nowrap}
      @media(max-width:620px){.promotion-card{grid-template-columns:1fr}.promotion-action{width:100%}}
    `;
    document.head.appendChild(style);
  };

  const buildCard = (promotion, event) => {
    const card = document.createElement('article');
    card.className = 'promotion-card';
    card.dataset.promotionId = promotion.promotion_id;

    const copy = document.createElement('div');
    const title = document.createElement('h2');
    title.textContent = event.canonical_name || event.title || 'イベント';
    const meta = document.createElement('div');
    meta.className = 'promotion-meta';
    const bits = [formatJst(event.starts_at), event.organizer, event.category_label || event.category]
      .filter(Boolean);
    meta.textContent = bits.join(' · ');
    copy.append(title, meta);

    const link = document.createElement('a');
    link.className = 'promotion-action';
    link.href = promotion.destination_url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = '公式情報を見る';
    link.dataset.track = 'featured_event_click';
    link.dataset.eventId = String(event.id || '');
    link.dataset.category = String(event.category || '');
    link.dataset.destinationType = 'featured';
    link.dataset.campaignId = String(promotion.campaign_id || '');
    link.dataset.promotionType = String(promotion.type || '');

    card.append(copy, link);
    return card;
  };

  const insert = rows => {
    if (!rows.length || document.getElementById('promotion-overlay')) return;
    addStyles();

    const section = document.createElement('section');
    section.id = 'promotion-overlay';
    section.className = 'promotion-overlay';
    section.setAttribute('aria-label', 'Featured events');

    const head = document.createElement('div');
    head.className = 'promotion-overlay-head';

    const badge = document.createElement('span');
    badge.className = 'promotion-badge';
    badge.textContent = 'Featured';

    const disclosure = document.createElement('span');
    disclosure.className = 'promotion-disclosure';
    disclosure.textContent = 'スポンサー掲載 · イベント情報の採否・分類には影響しません';

    const list = document.createElement('div');
    list.className = 'promotion-list';
    rows.slice(0, 2).forEach(({ promotion, event }) => {
      list.appendChild(buildCard(promotion, event));
    });

    head.append(badge, disclosure);
    section.append(head, list);

    const anchor = pageKind === 'category-landing'
      ? document.querySelector('.facts')
      : document.querySelector('.hero') || document.querySelector('.filters');
    if (anchor) anchor.insertAdjacentElement('afterend', section);
    else document.querySelector('main')?.prepend(section);
  };

  Promise.all([
    fetch(configUrl, { cache: 'no-store' }).then(response => {
      if (!response.ok) throw new Error('promotions');
      return response.json();
    }),
    fetch(eventsUrl, { cache: 'no-store' }).then(response => {
      if (!response.ok) throw new Error('events');
      return response.json();
    }),
  ]).then(([promotionData, eventData]) => {
    const now = new Date();
    const events = Array.isArray(eventData.events) ? eventData.events : [];
    const byId = new Map(events.map(event => [String(event.id || ''), event]));
    const promotions = Array.isArray(promotionData.promotions) ? promotionData.promotions : [];

    const rows = promotions
      .filter(promotion => active(promotion, now))
      .map(promotion => ({ promotion, event: byId.get(String(promotion.event_id || '')) }))
      .filter(row => row.event && eligibleForPage(row.promotion, row.event, now))
      .sort((left, right) =>
        new Date(left.event.starts_at) - new Date(right.event.starts_at)
      );

    insert(rows);
  }).catch(() => {
    // Promotion failure must never block the canonical event experience.
  });
})();
