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
.event-media-link{display:block;border-radius:14px;overflow:hidden;margin-bottom:12px}.event-media{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;border:1px solid var(--line);background:#f2f5f9;transition:transform .18s ease}.event-media-link:hover .event-media{transform:scale(1.015)}.asset-proof{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}.asset-proof a{font-size:.7rem;color:#49678f;text-decoration:none;border-bottom:1px solid #b9c7dc}.asset-proof a:hover{border-color:#49678f}
""".strip()

MEDIA_HELPER = """
function canonicalLinkKey(raw){try{const u=new URL(String(raw||''));const h=u.hostname.toLowerCase().replace(/^www\\./,'');if((h==='x.com'||h==='twitter.com')&&/\\/status\\/(\\d+)/.test(u.pathname))return`x-status:${u.pathname.match(/\\/status\\/(\\d+)/)[1]}`;if(h==='vrchat.com'&&/\\/home\\/group\\/(grp_[a-z0-9-]+)/i.test(u.pathname))return`vrchat-group:${u.pathname.match(/\\/home\\/group\\/(grp_[a-z0-9-]+)/i)[1].toLowerCase()}`;u.hash='';['utm_source','utm_medium','utm_campaign','utm_term','utm_content'].forEach(k=>u.searchParams.delete(k));return u.toString().replace(/\\/$/,'')}catch{return String(raw||'')}}
function preferredActionUrl(e){const rows=Array.isArray(e.official_links)?e.official_links:[];const group=rows.find(r=>String(r?.kind||'')==='vrchat_group'&&String(r?.url||'').startsWith('https://vrchat.com/home/group/'));return String(group?.url||e.primary_action_url||e.url||'')}
function mediaHtml(e){const url=String(e.image_url||'');if(!url.startsWith('https://'))return'';const target=preferredActionUrl(e);const kind=e.image_kind==='post_media'?'公式投稿画像':e.image_kind==='vrchat_group'?'VRChat公式グループ画像':'公式プロフィール画像';const image=`<img class="event-media" src="${esc(url)}" alt="${esc((e.canonical_name||e.title||'イベント')+' '+kind)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;return target.startsWith('https://')?`<a class="event-media-link" href="${esc(target)}" target="_blank" rel="noopener noreferrer" aria-label="${esc((e.canonical_name||e.title||'イベント')+'の参加・募集ページを開く')}">${image}</a>`:image}
function assetProofHtml(e){const rows=[];const links=Array.isArray(e.official_links)?e.official_links:[];const group=links.find(r=>String(r?.kind||'')==='vrchat_group'&&String(r?.url||'').startsWith('https://'));if(group)rows.push(`<a href="${esc(group.url)}" target="_blank" rel="noopener noreferrer">VRChat Group</a>`);if(String(e.official_x_url||'').startsWith('https://'))rows.push(`<a href="${esc(e.official_x_url)}" target="_blank" rel="noopener noreferrer">公式X</a>`);if(String(e.official_website_url||'').startsWith('https://'))rows.push(`<a href="${esc(e.official_website_url)}" target="_blank" rel="noopener noreferrer">公式Web</a>`);if(String(e.image_url||'').includes('webp'))rows.push(`<a href="${esc(e.image_url)}" target="_blank" rel="noopener noreferrer">WebP画像</a>`);return rows.length?`<div class="asset-proof">${rows.join('')}</div>`:''}
""".strip()

OLD_EVENT_LINKS = """function eventLinks(e){const rows=Array.isArray(e.official_links)?e.official_links:[];const seen=new Set();const valid=[];for(const row of rows){const url=String(row?.url||'');if(!url.startsWith('https://')||seen.has(url))continue;seen.add(url);valid.push({url,label:String(row?.label||'公式リンク'),kind:String(row?.kind||'official')})}if(!valid.length&&String(e.url||'').startsWith('https://'))valid.push({url:e.url,label:'告知・参加方法',kind:'announcement'});return valid.slice(0,3)}"""

NEW_EVENT_LINKS = """function eventLinks(e){const rows=Array.isArray(e.official_links)?e.official_links:[];const seen=new Set();const seenKinds=new Set();const valid=[];for(const row of rows){const url=String(row?.url||'');const kind=String(row?.kind||'official');if(!url.startsWith('https://'))continue;const key=canonicalLinkKey(url);if(seen.has(key)||(kind==='announcement'&&seenKinds.has('announcement')))continue;seen.add(key);seenKinds.add(kind);valid.push({url,label:String(row?.label||'公式リンク'),kind})}if(!valid.length&&String(e.url||'').startsWith('https://'))valid.push({url:e.url,label:'告知・参加方法',kind:'announcement'});return valid.slice(0,3)}"""


def patch_frontend(html: str) -> str:
    html = html.replace("</style>", f"{ASSET_CSS}\n</style>", 1)
    marker = "function detailsHtml(e){"
    if marker not in html:
        raise ValueError("frontend details marker missing")
    html = html.replace(marker, f"{MEDIA_HELPER}\n{marker}", 1)
    if OLD_EVENT_LINKS not in html:
        raise ValueError("frontend eventLinks marker missing")
    html = html.replace(OLD_EVENT_LINKS, NEW_EVENT_LINKS, 1)
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
    if "event-media-link" not in html or "preferredActionUrl" not in html or "canonicalLinkKey" not in html:
        raise ValueError("linked official asset frontend patch failed")
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"rendered {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
