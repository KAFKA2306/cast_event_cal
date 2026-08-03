from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cast_event_cal.ontology import main as enrich_event_ontology
from scripts.build_observed_ontology import main as build_observed_ontology

TEMPLATE = Path("web/index.template.html")
EVENTS = Path("public/events.json")
OUTPUT = Path("public/index.html")

ASSET_CSS = """
.event-media{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:14px;border:1px solid var(--line);background:#f2f5f9;margin-bottom:12px}.asset-proof{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.asset-proof a{font-size:.7rem;color:#49678f;text-decoration:none;border-bottom:1px solid #b9c7dc}.asset-proof a:hover{border-color:#49678f}
""".strip()

MEDIA_HELPER = """
function mediaHtml(e){const url=String(e.image_url||'');if(!url.startsWith('https://'))return'';const kind=e.image_kind==='post_media'?'公式投稿画像':'公式プロフィール画像';return `<img class="event-media" src="${esc(url)}" alt="${esc((e.canonical_name||e.title||'イベント')+' '+kind)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`}
function assetProofHtml(e){const rows=[];if(String(e.official_x_url||'').startsWith('https://'))rows.push(`<a href="${esc(e.official_x_url)}" target="_blank" rel="noopener noreferrer">公式X</a>`);if(String(e.official_website_url||'').startsWith('https://'))rows.push(`<a href="${esc(e.official_website_url)}" target="_blank" rel="noopener noreferrer">公式Web</a>`);if(String(e.image_url||'').includes('webp'))rows.push(`<a href="${esc(e.image_url)}" target="_blank" rel="noopener noreferrer">WebP画像</a>`);return rows.length?`<div class="asset-proof">${rows.join('')}</div>`:''}
""".strip()


def patch_frontend(html: str) -> str:
    html = html.replace("</style>", f"{ASSET_CSS}\n</style>", 1)
    marker = "function detailsHtml(e){"
    if marker not in html:
        raise ValueError("frontend details marker missing")
    html = html.replace(marker, f"{MEDIA_HELPER}\n{marker}", 1)
    old = '<div class="event-main"><div class="event-top">'
    new = '<div class="event-main">${mediaHtml(e)}<div class="event-top">'
    if old not in html:
        raise ValueError("frontend event card marker missing")
    html = html.replace(old, new, 1)
    old_tail = "${detailsHtml(e)}${tags?`<div class=\"tags\">${tags}</div>`:''}</div>"
    new_tail = "${detailsHtml(e)}${assetProofHtml(e)}${tags?`<div class=\"tags\">${tags}</div>`:''}</div>"
    if old_tail not in html:
        raise ValueError("frontend card tail marker missing")
    return html.replace(old_tail, new_tail, 1)


def main() -> int:
    enrich_event_ontology()
    build_observed_ontology()
    payload = json.loads(EVENTS.read_text(encoding="utf-8"))
    generated_at = str(payload.get("generated_at") or "")
    html = TEMPLATE.read_text(encoding="utf-8").replace("{{GENERATED_AT}}", generated_at)
    html = patch_frontend(html)
    if "VRChat Event Calendar" not in html or 'id="agenda"' not in html:
        raise ValueError("frontend template validation failed")
    if "event-media" not in html or "assetProofHtml" not in html:
        raise ValueError("official asset frontend patch failed")
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"rendered {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
