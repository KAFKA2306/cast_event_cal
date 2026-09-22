'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('public/analytics.js', 'utf8');

function fixture({ consent = null, gpc = false, dnt = '0', pageKind = 'event-detail' } = {}) {
  const storage = new Map();
  if (consent) storage.set('cast-event-cal.analytics-consent.v1', consent);
  const googleTags = [];
  const bodyChildren = [];
  const listeners = {};
  const makeElement = tag => ({
    tagName: tag,
    dataset: {},
    setAttribute() {},
    addEventListener(type, fn) { this.listeners = this.listeners || {}; this.listeners[type] = fn; },
    remove() { this.removed = true; },
    closest() { return null; },
  });
  const document = {
    currentScript: { dataset: { config: '/analytics-config.json' } },
    body: {
      dataset: { pageKind, eventId: 'evt-1', category: 'social' },
      appendChild(node) { bodyChildren.push(node); },
    },
    head: {
      appendChild(node) { if (String(node.src || '').includes('googletagmanager.com')) googleTags.push(node.src); },
    },
    createElement: makeElement,
    addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
  };
  const context = {
    document,
    navigator: { globalPrivacyControl: gpc, doNotTrack: dnt },
    localStorage: {
      getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
    },
    fetch: async () => ({ ok: true, json: async () => ({ ga4_measurement_id: 'G-TEST123' }) }),
    console,
    Date,
    encodeURIComponent,
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(source, context, { filename: 'public/analytics.js' });
  return { context, storage, googleTags, bodyChildren, listeners };
}

const flush = () => new Promise(resolve => setImmediate(resolve));

(async () => {
  {
    const f = fixture();
    await flush();
    assert.equal(f.googleTags.length, 0, 'unknown consent must not load Google tag');
    assert.equal(f.bodyChildren.length, 1, 'unknown consent should offer a local choice');
    assert.equal(f.context.gtag, undefined, 'unknown consent must not initialize gtag');
  }

  {
    const f = fixture({ consent: 'denied' });
    await flush();
    assert.equal(f.googleTags.length, 0, 'denied consent must not load Google tag');
    assert.equal(f.bodyChildren.length, 0, 'denied consent must not nag again');
  }

  {
    const f = fixture({ consent: 'granted', gpc: true });
    await flush();
    assert.equal(f.googleTags.length, 0, 'GPC must override stored grant');
    assert.equal(f.bodyChildren.length, 0, 'GPC must not show a tracking prompt');
  }

  {
    const f = fixture({ consent: 'granted', dnt: '1' });
    await flush();
    assert.equal(f.googleTags.length, 0, 'DNT must override stored grant');
  }

  {
    const f = fixture({ consent: 'granted' });
    await flush();
    assert.equal(f.googleTags.length, 1, 'stored grant may load Google tag');
    const config = f.context.dataLayer.find(item => item[0] === 'config');
    assert.ok(config, 'GA4 config must be queued');
    assert.equal(config[2].send_page_view, false, 'automatic page_view must stay disabled');
    assert.equal(config[2].allow_ad_personalization_signals, false);
    assert.equal(config[2].ads_data_redaction, true);
  }

  {
    const f = fixture();
    const banner = f.bodyChildren[0];
    const preConsentClick = f.listeners.click[0];
    preConsentClick({ target: { closest: () => ({ dataset: { track: 'official_link_click' } }) } });
    banner.listeners.click({ target: { closest: () => ({ dataset: { consent: 'granted' } }) } });
    await flush();
    assert.equal(f.storage.get('cast-event-cal.analytics-consent.v1'), 'granted');
    assert.equal(f.googleTags.length, 1, 'explicit grant may load Google tag');
    const events = f.context.dataLayer.filter(item => item[0] === 'event');
    assert.equal(events.length, 0, 'events that happened before consent must not be replayed');
  }

  console.log('analytics privacy fixture: ok');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
