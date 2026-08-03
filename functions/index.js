class HeadAssets {
  element(element) {
    element.append(
      '<link rel="stylesheet" href="/uiux-v4.css"><script defer src="/uiux-v4.js"></script>',
      { html: true },
    );
  }
}

export async function onRequest(context) {
  const response = await context.next();
  const contentType = response.headers.get('content-type') || '';

  if (!contentType.toLowerCase().includes('text/html')) {
    return response;
  }

  const transformed = new HTMLRewriter().on('head', new HeadAssets()).transform(response);
  const headers = new Headers(transformed.headers);
  headers.set('x-quality-view', '2026-08-03-quality-view-v4');
  return new Response(transformed.body, {
    status: transformed.status,
    statusText: transformed.statusText,
    headers,
  });
}
