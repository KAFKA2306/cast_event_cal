(() => {
  'use strict';

  const release = 'kafka-signal-v1.0.0';
  const preloadMargin = 800;

  function explain(card) {
    if (card.dataset.ksExplained) return;
    card.dataset.ksExplained = '1';
    const details = card.querySelector('details .details-body');
    if (!details) return;
    const reason = card.querySelector('[data-field="reason"]')?.textContent?.trim();
    const source = card.querySelector('[data-field="source"]')?.textContent?.trim();
    const paragraph = document.createElement('p');
    paragraph.className = 'why-shown';
    paragraph.innerHTML = `<strong>この一覧に表示された理由</strong><br>${reason || '選択中の期間・カテゴリ・情報源条件に一致したため表示しています。'}${source ? ` 情報源: ${source}` : ''}。これは公式説明ではなく、収集・分類処理の説明です。`;
    details.prepend(paragraph);
  }

  function installInfiniteScroll() {
    const more = document.querySelector('#more');
    if (!more || !('IntersectionObserver' in window)) return;
    let loading = false;
    const loadNext = () => {
      if (loading || more.hidden || more.disabled) return;
      loading = true;
      const activeElement = document.activeElement;
      const scrollX = window.scrollX;
      const scrollY = window.scrollY;
      more.click();
      if (activeElement && activeElement !== document.body && typeof activeElement.focus === 'function') activeElement.focus({ preventScroll: true });
      else more.blur();
      window.scrollTo(scrollX, scrollY);
      requestAnimationFrame(() => {
        loading = false;
        if (!more.hidden && more.getBoundingClientRect().top < window.innerHeight + preloadMargin) loadNext();
      });
    };
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadNext();
    }, { root: null, rootMargin: `${preloadMargin}px 0px`, threshold: 0 });
    observer.observe(more);
    new MutationObserver(() => {
      if (!more.hidden && more.getBoundingClientRect().top < window.innerHeight + preloadMargin) loadNext();
    }).observe(more, { attributes: true, attributeFilter: ['hidden'] });
  }

  async function installProvenance(footer) {
    const paragraph = document.createElement('p');
    paragraph.className = 'ks-version';
    paragraph.textContent = `KAFKA SIGNAL ${release} · provenance loading`;
    footer.append(paragraph);
    try {
      const response = await fetch('./provenance.json', { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const provenance = await response.json();
      const revision = provenance.verified ? provenance.commit.slice(0, 8) : 'LOCAL/UNVERIFIED';
      paragraph.textContent = `KAFKA SIGNAL ${provenance.release || release} · ${revision}`;
      document.documentElement.dataset.publicationCommit = provenance.commit || 'UNVERIFIED';
    } catch (_error) {
      paragraph.textContent = `KAFKA SIGNAL ${release} · LOCAL/UNVERIFIED`;
      document.documentElement.dataset.publicationCommit = 'UNVERIFIED';
    }
  }

  function install() {
    document.documentElement.dataset.kafkaSignal = release;
    const hero = document.querySelector('.hero');
    if (hero && !document.querySelector('.entry-contract')) {
      const box = document.createElement('section');
      box.className = 'entry-contract';
      box.setAttribute('aria-label', '表示モード');
      box.innerHTML = '<p><strong>参加モード</strong><br>時刻・参加方法・公式告知を先に表示します。分類根拠と監査情報は詳細へ分離しています。</p><a href="../">データ監査を開く</a>';
      hero.insertAdjacentElement('afterend', box);
    }
    const list = document.querySelector('#list');
    if (list) {
      new MutationObserver(() => list.querySelectorAll('.event-card').forEach(explain)).observe(list, { childList: true, subtree: true });
      list.querySelectorAll('.event-card').forEach(explain);
    }
    const footer = document.querySelector('footer');
    if (footer && !footer.querySelector('.ks-version')) installProvenance(footer);
    const off = document.querySelector('#history-off');
    if (off) off.addEventListener('click', () => localStorage.setItem('vrc-tonight-history-off', off.getAttribute('aria-pressed') === 'true' ? '1' : '0'));
    installInfiniteScroll();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install);
  else install();
})();
