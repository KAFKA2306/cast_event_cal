(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.TonightSafeLinks = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function safeExternalUrl(value) {
    if (typeof value !== 'string' || !value.trim()) return null;
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || !url.hostname) return null;
      return url.href;
    } catch {
      return null;
    }
  }

  function normalizeProof(value, index) {
    if (typeof value === 'string') {
      const url = safeExternalUrl(value);
      return url ? { label: `証跡 ${index + 1}`, url } : null;
    }
    if (!value || typeof value !== 'object') return null;
    const rawUrl = value.url || value.href || '';
    const url = safeExternalUrl(rawUrl);
    if (!url) return null;
    const label = String(value.label || value.title || value.type || `証跡 ${index + 1}`);
    return { label, url };
  }

  function buildExternalLink(documentRef, label, rawUrl) {
    const url = safeExternalUrl(rawUrl);
    if (!url) return null;
    const anchor = documentRef.createElement('a');
    anchor.href = url;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    anchor.textContent = `${String(label)} ↗`;
    return anchor;
  }

  return { safeExternalUrl, normalizeProof, buildExternalLink };
});
