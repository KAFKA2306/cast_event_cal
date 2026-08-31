from __future__ import annotations

from pathlib import Path

OUTPUT = Path("public/index.html")
VIEW_ORDER_MARKER = 'data-view-order="decision-first-v2"'
LEGACY_VIEW_ORDER_MARKER = 'data-view-order="decision-first-v1"'
CARD_ORDER_MARKER = 'data-card-order="decision-first-v1"'

CARD_CSS = """
.event{grid-template-columns:92px minmax(0,1fr)}
.event h2{margin:0 0 8px;font-size:1.12rem}
.event-top{margin:0 0 10px}
.decision-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;align-items:stretch;margin:10px 0}
.participation{min-width:0;padding:10px 12px;border-radius:14px;background:rgba(183,219,200,.22);color:#39566a;font-size:.82rem;line-height:1.55}
.participation b{display:block;margin-bottom:2px;color:#52627a;font-size:.68rem}
.event-primary-action{min-width:150px;align-self:stretch;padding-inline:16px}
.decision-meta{margin-bottom:10px}
.event-media-link{margin-top:10px;margin-bottom:10px}
.provenance{margin-top:10px;color:var(--muted);font-size:.72rem;line-height:1.5}
.event-secondary-links{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
.event-secondary-links .event-link{background:#fff}
.recommendation-card .event-link{margin-top:10px;align-self:flex-start}
@media(max-width:920px){.event{grid-template-columns:76px minmax(0,1fr)}}
@media(max-width:680px){.decision-row{grid-template-columns:1fr}.event-primary-action{width:100%;min-width:0}}
@media(max-width:480px){.event{grid-template-columns:1fr}}
""".strip()

CARD_JS = r"""
function participationHtml(event){const method=String(event.participation_method||'').trim();return method?`<div class="participation"><b>参加方法</b><span>${esc(method)}</span></div>`:''}
function primaryActionHtml(event){const link=eventLinks(event)[0];return link?`<a class="event-link primary event-primary-action" href="${esc(link.url)}" target="_blank" rel="noopener noreferrer"${historyAttr(event)}>${esc(link.label)}</a>`:''}
function secondaryActionsHtml(event){const rows=eventLinks(event).slice(1);return rows.length?`<div class="event-secondary-links">${rows.map(link=>`<a class="event-link" href="${esc(link.url)}" target="_blank" rel="noopener noreferrer"${historyAttr(event)}>${esc(link.label)}</a>`).join('')}</div>`:''}
function detailsHtml(event){const evidence=(event.category_evidence||[]).slice(0,2).map(value=>String(value).replace(/^keyword:[^:]+:/,'')).join(' / ');const rows=[['開催形式',event.event_format],['対象',event.audience],['分類根拠',evidence]].filter(([,value])=>value);return rows.length?`<div class="details">${rows.map(([key,value])=>`<div class="detail"><b>${esc(key)}</b>${esc(value)}</div>`).join('')}</div>`:''}
function eventHtml(event){const category=categoryKey(event.category),end=event.ends_at?`–${timeLabel(event.ends_at)}`:'',tags=(event.tags||[]).slice(0,7).map(tag=>`<span class="tag">${esc(tag)}</span>`).join(''),detail=event.category_detail?detailLabels[event.category_detail]||event.category_detail:null,mode=modeLabels[event.event_mode]||event.event_mode,confidence=Number(event.category_confidence),metaParts=[event.organizer?`主催 ${esc(event.organizer)}`:'',event.location?esc(event.location):''].filter(Boolean).join(' · ');const classes=['event',confidence&&confidence<.6?'low-confidence':'',event.event_mode==='offline'?'offline':''].filter(Boolean).join(' ');return `<article class="${classes}"><div class="time">${timeLabel(event.starts_at)}<small>${esc(end)}</small></div><div class="event-main"><h2>${esc(event.canonical_name||event.title)}</h2><div class="event-top"><span class="badge ${esc(category)}">${esc(categoryLabel(event))}</span>${detail?`<span class="badge">${esc(detail)}</span>`:''}${mode?`<span class="badge mode ${event.event_mode==='offline'?'offline':''}">${esc(mode)}</span>`:''}${event.ontology_id?'<span class="badge">辞書照合済み</span>':''}${confidence?`<span class="badge mode">分類 ${Math.round(confidence*100)}%</span>`:''}</div><div class="decision-row">${participationHtml(event)}${primaryActionHtml(event)}</div>${metaParts?`<div class="meta decision-meta">${metaParts}</div>`:''}${mediaHtml(event)}${event.description?`<p class="description">${esc(event.description)}</p>`:''}${detailsHtml(event)}${event.source?`<div class="provenance">出典 ${esc(event.source)}</div>`:''}${secondaryActionsHtml(event)}${assetProofHtml(event)}${tags?`<div class="tags">${tags}</div>`:''}</div></article>`}
""".strip()

RECOMMENDATION_JS = r"""function recommendationHtml(row){const e=row.event,link=eventLinks(e)[0],tags=(e.tags||[]).filter(tag=>!STOP_TAGS.has(normalize(tag))).slice(0,3).map(tag=>`<span class="tag">${esc(tag)}</span>`).join('');return `<article class="recommendation-card"><h3>${esc(eventTitle(e))}</h3><div class="event-top"><span class="badge ${esc(categoryKey(e.category))}">${esc(categoryLabel(e))}</span><span class="badge">${esc(dayLabel(e.starts_at))} ${esc(timeLabel(e.starts_at))}</span></div><div class="meta">${e.organizer?`主催 ${esc(e.organizer)} · `:''}${esc(e.location||'VRChat')}</div><p class="recommendation-reason">${esc(row.reason)}</p><a class="event-link primary" href="${esc(link.url)}" target="_blank" rel="noopener noreferrer"${historyAttr(e)}>${esc(link.label)}</a>${tags?`<div class="tags">${tags}</div>`:''}</article>`}"""


def _replace_once(html: str, old: str, new: str, error: str) -> str:
    if old not in html:
        raise ValueError(error)
    return html.replace(old, new, 1)


def _replace_block(html: str, start_marker: str, end_marker: str, replacement: str, error: str) -> str:
    start = html.find(start_marker)
    if start < 0:
        raise ValueError(f"{error}: start marker missing")
    end = html.find(end_marker, start)
    if end < 0:
        raise ValueError(f"{error}: end marker missing")
    return html[:start] + replacement.rstrip() + "\n" + html[end:]


def _apply_home_order(html: str) -> str:
    if LEGACY_VIEW_ORDER_MARKER in html:
        return html.replace(LEGACY_VIEW_ORDER_MARKER, VIEW_ORDER_MARKER, 1)
    if VIEW_ORDER_MARKER in html:
        return html

    html = _replace_once(
        html,
        '<main class="shell">',
        f'<main class="shell" {VIEW_ORDER_MARKER}>',
        "home shell marker missing",
    )
    html = _replace_once(
        html,
        '<a class="button primary" href="#agenda">今週のイベントを見る</a>',
        '<a class="button primary" href="tonight/">今夜のイベントを見る</a>',
        "primary home action marker missing",
    )
    html = _replace_once(
        html,
        '<section class="controls" aria-label="イベント絞り込み">',
        '<section id="event-filters" class="controls" aria-label="イベント絞り込み">',
        "home filter marker missing",
    )

    summary_start = html.find('<section class="summary" aria-label="集計">')
    if summary_start < 0:
        raise ValueError("home summary marker missing")
    summary_end = html.find("</section>", summary_start)
    if summary_end < 0:
        raise ValueError("home summary closing marker missing")
    summary_end += len("</section>")
    summary = html[summary_start:summary_end].replace('aria-label="集計"', 'aria-label="全体集計"', 1)
    html = html[:summary_start] + html[summary_end:]

    footer_start = html.find("<footer>")
    if footer_start < 0:
        raise ValueError("home footer marker missing")
    return html[:footer_start] + summary + "\n" + html[footer_start:]


def _apply_card_order(html: str) -> str:
    if CARD_ORDER_MARKER in html:
        return html

    html = _replace_once(
        html,
        VIEW_ORDER_MARKER,
        f"{VIEW_ORDER_MARKER} {CARD_ORDER_MARKER}",
        "view-order marker missing before card reorder",
    )
    html = _replace_once(html, "</style>", f"{CARD_CSS}\n</style>", "frontend style marker missing")
    html = _replace_block(
        html,
        "function recommendationHtml(row){",
        "function renderHistorySummary(){",
        RECOMMENDATION_JS,
        "recommendation card function",
    )
    html = _replace_block(
        html,
        "function detailsHtml(event){",
        "function renderAgenda(){",
        CARD_JS,
        "event card function block",
    )
    return html


def reorder_home_view(html: str) -> str:
    """Apply decision-first information order to the home view and event cards."""
    if VIEW_ORDER_MARKER in html and CARD_ORDER_MARKER in html:
        return html

    html = _apply_home_order(html)
    html = _apply_card_order(html)

    ordered_markers = (
        '<section class="hero">',
        '<section id="event-filters" class="controls"',
        '<section id="recommendations"',
        '<div class="statusbar">',
        '<div id="agenda"',
        '<section class="summary" aria-label="全体集計">',
        "<footer>",
    )
    positions = [html.find(marker) for marker in ordered_markers]
    if any(position < 0 for position in positions):
        raise ValueError(f"home view marker missing after reorder: {positions}")
    if positions != sorted(positions):
        raise ValueError(f"home view order invalid: {positions}")
    return html


def main() -> int:
    html = OUTPUT.read_text(encoding="utf-8")
    reordered = reorder_home_view(html)
    OUTPUT.write_text(reordered, encoding="utf-8")
    print("reordered public/index.html by user decision value")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
