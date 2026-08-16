(() => {
  const copy = async value => {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(value);
    const area = document.createElement('textarea');
    area.value = value;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    document.execCommand('copy');
    area.remove();
  };
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-share-native]');
    if (!button) return;
    const url = button.dataset.shareUrl || location.href;
    const title = button.dataset.shareTitle || document.title;
    const status = button.parentElement?.querySelector('.share-status');
    try {
      if (navigator.share) {
        await navigator.share({ title, url });
        if (status) status.textContent = '共有しました';
      } else {
        await copy(url);
        if (status) status.textContent = '共有URLをコピーしました';
      }
    } catch (error) {
      if (error?.name !== 'AbortError' && status) status.textContent = '共有できませんでした';
    }
  });
})();
