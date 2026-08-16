from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree.ElementTree import Element, SubElement, tostring
from zoneinfo import ZoneInfo

BASE_URL = "https://kafka2306.github.io/vrc_cast_event_calender"
JST = ZoneInfo("Asia/Tokyo")
SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
ROOT_PREVIEW_LIMIT = 24


def parse_time(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
    except ValueError:
        return None


def https_url(value: object) -> str:
    raw = str(value or "").strip()
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    return raw if parsed.scheme == "https" and parsed.netloc else ""


def action_links(event: dict[str, object]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    primary = https_url(event.get("primary_action_url"))
    if primary:
        rows.append(
            {
                "url": primary,
                "label": "公式・参加情報",
                "kind": str(event.get("primary_action_kind") or "official"),
            }
        )
        seen.add(primary)
    for item in event.get("official_links") or []:
        if not isinstance(item, dict):
            continue
        url = https_url(item.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        rows.append(
            {
                "url": url,
                "label": str(item.get("label") or "公式リンク"),
                "kind": str(item.get("kind") or "official"),
            }
        )
    if not rows:
        fallback = https_url(event.get("url"))
        if fallback:
            rows.append({"url": fallback, "label": "告知・参加方法", "kind": "announcement"})
    return rows[:5]


def indexable(event: dict[str, object], generated_at: datetime) -> bool:
    event_id = str(event.get("id") or "")
    title = str(event.get("canonical_name") or event.get("title") or "").strip()
    start = parse_time(event.get("starts_at"))
    end = parse_time(event.get("ends_at"))
    if not SAFE_ID.fullmatch(event_id) or not title or start is None or not action_links(event):
        return False
    if event.get("review_required") is True:
        return False
    return end >= generated_at if end else start >= generated_at


def event_title(event: dict[str, object]) -> str:
    return str(event.get("canonical_name") or event.get("title") or "イベント").strip()


def truncate(value: str, limit: int) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def format_jst(value: object) -> str:
    parsed = parse_time(value)
    if parsed is None:
        return ""
    return parsed.astimezone(JST).strftime("%Y年%m月%d日 %H:%M JST")


def escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def track_type(kind: str) -> str:
    key = kind.lower()
    return (
        "participation_link_click"
        if any(token in key for token in ("particip", "join", "entry", "registration"))
        else "official_link_click"
    )


def render_event_page(event: dict[str, object], base_url: str) -> str:
    event_id = str(event["id"])
    title = event_title(event)
    category = str(event.get("category_label") or event.get("category") or "")
    organizer = str(event.get("organizer") or "").strip()
    description = str(event.get("description") or "").strip()
    start = format_jst(event.get("starts_at"))
    end = format_jst(event.get("ends_at"))
    observed = format_jst(event.get("fetched_at"))
    source = str(event.get("source") or "").strip()
    canonical = f"{base_url}/events/{event_id}/"
    page_title = f"{truncate(title, 56)}｜{start} | VRChatイベントカレンダー"
    summary_bits = [start, category, truncate(description, 110)]
    meta_description = truncate(" · ".join(bit for bit in summary_bits if bit), 158)
    image = https_url(
        event.get("preferred_image_url")
        or event.get("vrchat_group_image_url")
        or event.get("image_url")
    )
    links = action_links(event)
    actions = "".join(
        f'<a class="action {"primary" if i == 0 else ""}" href="{escape(link["url"])}" '
        f'target="_blank" rel="noopener noreferrer" data-track="{track_type(link["kind"])}" '
        f'data-event-id="{escape(event_id)}" data-category="{escape(event.get("category"))}">'
        f'{escape(link["label"])}</a>'
        for i, link in enumerate(links)
    )
    provenance: list[str] = []
    for row in event.get("provenance") or []:
        if not isinstance(row, dict):
            continue
        url = https_url(row.get("url"))
        if url:
            provenance.append(url)
    provenance = list(dict.fromkeys(provenance))[:3]
    provenance_html = "".join(
        f'<li><a href="{escape(url)}" target="_blank" rel="noopener noreferrer">観測元を開く</a></li>'
        for url in provenance
    )
    image_meta = (
        f'<meta property="og:image" content="{escape(image)}">\n'
        '<meta name="twitter:card" content="summary_large_image">'
        if image
        else '<meta name="twitter:card" content="summary">'
    )
    image_html = (
        f'<img class="hero-image" src="{escape(image)}" alt="{escape(title)}の公式画像" '
        'referrerpolicy="no-referrer">'
        if image
        else ""
    )
    description_html = f'<p class="description">{escape(description)}</p>' if description else ""
    organizer_html = f'<div><dt>主催</dt><dd>{escape(organizer)}</dd></div>' if organizer else ""
    end_html = f'<div><dt>終了</dt><dd>{escape(end)}</dd></div>' if end else ""
    observed_html = f'<div><dt>観測時刻</dt><dd>{escape(observed)}</dd></div>' if observed else ""
    source_html = f'<div><dt>情報源</dt><dd>{escape(source)}</dd></div>' if source else ""
    provenance_section = (
        f'<details><summary>データ根拠</summary><ul>{provenance_html}</ul></details>'
        if provenance_html
        else ""
    )
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(page_title)}</title>
<meta name="description" content="{escape(meta_description)}">
<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1">
<link rel="canonical" href="{escape(canonical)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="ja_JP">
<meta property="og:site_name" content="VRChatイベントカレンダー">
<meta property="og:title" content="{escape(title)}">
<meta property="og:description" content="{escape(meta_description)}">
<meta property="og:url" content="{escape(canonical)}">
{image_meta}
<style>
:root{{--bg:#fbfaf7;--surface:#fff;--ink:#243653;--muted:#66758d;--line:#dfe6ef}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Noto Sans JP",sans-serif}}main{{width:min(820px,100%);margin:auto;padding:28px 18px 64px}}a{{color:inherit}}nav{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:28px}}nav a{{font-weight:700}}.eyebrow{{font-size:.78rem;font-weight:800;letter-spacing:.1em;color:#58729a}}h1{{font-size:clamp(1.8rem,6vw,3.5rem);line-height:1.08;letter-spacing:-.035em;margin:.5rem 0 1rem}}.hero-image{{width:100%;max-height:440px;object-fit:cover;border-radius:18px;border:1px solid var(--line);background:#f2f5f9}}.description{{line-height:1.8;font-size:1rem;white-space:pre-wrap}}dl{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}dl div{{padding:14px;border:1px solid var(--line);border-radius:14px;background:var(--surface)}}dt{{font-size:.75rem;color:var(--muted);font-weight:800}}dd{{margin:5px 0 0;overflow-wrap:anywhere}}.actions{{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}}.action{{display:inline-flex;min-height:46px;align-items:center;padding:10px 15px;border:1px solid var(--line);border-radius:999px;text-decoration:none;font-weight:800;background:var(--surface)}}.action.primary{{background:var(--ink);color:white;border-color:var(--ink)}}.notice{{padding:15px;border-left:4px solid #8fb5ec;background:#fff;line-height:1.7}}details{{margin-top:26px;padding:14px;border-top:1px solid var(--line)}}li{{margin:.6rem 0}}@media(max-width:560px){{dl{{grid-template-columns:1fr}}}}
</style>
<script src="../../analytics.js" data-config="../../analytics-config.json" defer></script>
</head>
<body data-page-kind="event-detail" data-event-id="{escape(event_id)}" data-category="{escape(event.get('category'))}">
<main>
<nav><a href="../../">イベント一覧へ戻る</a><a href="../../calendar.ics" data-track="calendar_download">カレンダーを購読</a></nav>
<div class="eyebrow">{escape(category or 'VRChat EVENT')} · {escape(start)}</div>
<h1>{escape(title)}</h1>
{image_html}
{description_html}
<dl>
<div><dt>開始</dt><dd>{escape(start)}</dd></div>
{end_html}
{organizer_html}
{source_html}
{observed_html}
</dl>
<div class="actions">{actions}</div>
<p class="notice">開催時刻・参加条件は変更される場合があります。参加前に主催者の最新公式情報を確認してください。</p>
{provenance_section}
</main>
</body>
</html>
'''


def sitemap_xml(urls: list[str], lastmod: str) -> str:
    root = Element("urlset", {"xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
    for url in urls:
        node = SubElement(root, "url")
        SubElement(node, "loc").text = url
        SubElement(node, "lastmod").text = lastmod
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode") + "\n"


def root_preview(events: list[dict[str, object]]) -> str:
    items = []
    for event in events[:ROOT_PREVIEW_LIMIT]:
        event_id = str(event["id"])
        items.append(
            '<li><a href="events/{id}/" data-track="event_detail_open" data-event-id="{id}" '
            'data-category="{category}">{title}</a><span>{date} · {category_label}</span></li>'.format(
                id=escape(event_id),
                title=escape(truncate(event_title(event), 100)),
                date=escape(format_jst(event.get("starts_at"))),
                category=escape(event.get("category")),
                category_label=escape(event.get("category_label") or event.get("category") or ""),
            )
        )
    return (
        '<section class="search-entry" aria-labelledby="search-entry-title">'
        '<div class="eyebrow">SEARCHABLE EVENT PAGES</div>'
        '<h2 id="search-entry-title">直接開けるイベント詳細</h2>'
        '<p>直近のイベントを、共有できる固定URLで確認できます。参加前は主催者の最新公式情報を確認してください。</p>'
        '<ul>'
        + "".join(items)
        + "</ul></section>"
    )


def patch_root(root: Path, events: list[dict[str, object]]) -> None:
    path = root / "index.html"
    text = path.read_text(encoding="utf-8")
    start_marker = "<!-- searchable-events:start -->"
    end_marker = "<!-- searchable-events:end -->"
    text = re.sub(re.escape(start_marker) + r".*?" + re.escape(end_marker), "", text, flags=re.S)
    marker = "<footer>"
    if marker not in text:
        raise ValueError("root footer marker missing")
    css = (
        ".search-entry{margin-top:34px;padding:20px;border:1px solid var(--line);border-radius:var(--radius);background:rgba(255,255,255,.82)}"
        ".search-entry h2{margin:.4rem 0}.search-entry p{color:var(--muted);line-height:1.7}"
        ".search-entry ul{list-style:none;padding:0;margin:16px 0 0;display:grid;gap:8px}"
        ".search-entry li{display:flex;justify-content:space-between;gap:16px;padding:10px 0;border-top:1px solid var(--line)}"
        ".search-entry li a{font-weight:800}.search-entry li span{color:var(--muted);font-size:.8rem;text-align:right}"
        "@media(max-width:680px){.search-entry li{display:grid;gap:4px}.search-entry li span{text-align:left}}"
    )
    if ".search-entry{" not in text:
        text = text.replace("</style>", css + "\n</style>", 1)
    section = f"{start_marker}\n{root_preview(events)}\n{end_marker}"
    text = text.replace(marker, section + "\n" + marker, 1)
    text = text.replace(
        '<a class="button" href="calendar.ics">カレンダーを購読</a>',
        '<a class="button" href="calendar.ics" data-track="calendar_download">カレンダーを購読</a>',
        1,
    )
    if 'src="analytics.js"' not in text:
        text = text.replace(
            "</head>",
            '<script src="analytics.js" data-config="analytics-config.json" defer></script>\n</head>',
            1,
        )
    path.write_text(text, encoding="utf-8")


def write_analytics(root: Path) -> None:
    measurement_id = os.environ.get("GA4_MEASUREMENT_ID", "").strip()
    config = {
        "ga4_measurement_id": measurement_id
        if re.fullmatch(r"G-[A-Z0-9]+", measurement_id)
        else None
    }
    (root / "analytics-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    script = r'''(() => {
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
'''
    (root / "analytics.js").write_text(script, encoding="utf-8")


def render(events_path: Path, public_root: Path, base_url: str = BASE_URL) -> dict[str, int]:
    payload = json.loads(events_path.read_text(encoding="utf-8"))
    generated_at = parse_time(payload.get("generated_at"))
    if generated_at is None:
        raise ValueError("events.json generated_at is missing or invalid")
    rows = payload.get("events")
    if not isinstance(rows, list):
        raise ValueError("events.json events must be a list")
    selected = [
        row for row in rows if isinstance(row, dict) and indexable(row, generated_at)
    ]
    selected.sort(
        key=lambda row: (
            parse_time(row.get("starts_at")) or generated_at,
            str(row.get("id")),
        )
    )
    ids = [str(row["id"]) for row in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("indexable event IDs must be unique")

    events_root = public_root / "events"
    shutil.rmtree(events_root, ignore_errors=True)
    events_root.mkdir(parents=True, exist_ok=True)
    for event in selected:
        target = events_root / str(event["id"])
        target.mkdir()
        (target / "index.html").write_text(
            render_event_page(event, base_url), encoding="utf-8"
        )

    lastmod = generated_at.isoformat().replace("+00:00", "Z")
    urls = [base_url + "/"] + [f"{base_url}/events/{event_id}/" for event_id in ids]
    (public_root / "sitemap.xml").write_text(
        sitemap_xml(urls, lastmod), encoding="utf-8"
    )
    write_analytics(public_root)
    patch_root(public_root, selected)
    return {
        "event_count": len(rows),
        "indexable_count": len(selected),
        "sitemap_url_count": len(urls),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=Path, default=Path("public/events.json"))
    parser.add_argument("--public-root", type=Path, default=Path("public"))
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()
    result = render(args.events, args.public_root, args.base_url.rstrip("/"))
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
