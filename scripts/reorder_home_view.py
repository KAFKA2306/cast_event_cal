from __future__ import annotations

from pathlib import Path

OUTPUT = Path("public/index.html")
VIEW_ORDER_MARKER = 'data-view-order="decision-first-v2"'
LEGACY_VIEW_ORDER_MARKER = 'data-view-order="decision-first-v1"'
CARD_ORDER_MARKER = 'data-card-order="decision-first-v2"'
FILTER_URL_MARKER = 'data-filter-url="shareable-v1"'

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
.event-evidence{margin-top:12px;padding-top:9px;border-top:1px solid var(--line)}
.event-evidence summary{width:max-content;max-width:100%;cursor:pointer;color:var(--muted);font-size:.74rem;font-weight:750;line-height:1.5}
.event-evidence-body{margin-top:8px;padding:10px 11px;border-radius:12px;background:#f7f8fb;color:var(--muted);font-size:.72rem;line-height:1.55}
.evidence-line{overflow-wrap:anywhere}
.event-secondary-links{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}
.event-secondary-links .event-link{background:#fff}
.event-evidence .asset-proof{margin-top:8px}
.recommendation-card .event-link{margin-top:10px;align-self:flex-start}
@media(max-width:920px){.event{grid-template-columns:76px minmax(0,1fr)}}
@media(max-width:680px){.decision-row{grid-template-columns:1fr}.event-primary-action{width:100%;min-width:0}}
@media(max-width:480px){.event{grid-template-columns:1fr}}
""".strip()

CARD_JS = r"""
function participationHtml(event){const method=String(event.participation_method||'').trim();return method?`<div class="participation"><b>参加方法</b><span>${esc(method)}</span></div>`:''}
function primaryActionHtml(event){const link=eventLinks(event)[0];return link?`<a class="event-link primary event-primary-action" href="${esc(link.url)}" target="_blank" rel="noopener noreferrer"${historyAttr(event)}>${esc(link.label)}</a>`:''}
function secondaryActionsHtml(event){const rows=eventLinks(event).slice(1);return rows.length?`<div class="event-secondary-links">${rows.map(link=>`<a class="event-link" href="${esc(link.url)}" target="_blank" rel="noopener noreferrer"${historyAttr(event)}>${esc(link.label)}</a>`).join('')}</div>`:''}
function detailsHtml(event){const rows=[['開催形式',event.event_format],['対象',event.audience]].filter(([,value])=>value);return rows.length?`<div class="details">${rows.map(([key,value])=>`<div class="detail"><b>${esc(key)}</b>${esc(value)}</div>`).join('')}</div>`:''}
function classificationEvidenceHtml(event){const rows=[],confidence=Number(event.category_confidence),evidence=(event.category_evidence||[]).slice(0,2).map(value=>String(value).replace(/^keyword:[^:]+:/,'')).join(' / ');if(event.ontology_id)rows.push('<div class="evidence-line">カテゴリ辞書照合済み</div>');if(Number.isFinite(confidence)&&confidence>0)rows.push(`<div class="evidence-line">分類信頼度 ${Math.round(confidence*100)}%</div>`);if(evidence)rows.push(`<div class="evidence-line">分類根拠 ${esc(evidence)}</div>`);return rows.join('')}
function evidenceHtml(event){const source=event.source?`<div class="evidence-line">出典 ${esc(event.source)}</div>`:'',classification=classificationEvidenceHtml(event),secondary=secondaryActionsHtml(event),assets=assetProofHtml(event);return source||classification||secondary||assets?`<details class="event-evidence"><summary>出典・確認情報</summary><div class="event-evidence-body">${source}${classification}${secondary}${assets}</div></details>`:''}
function eventHtml(event){const category=categoryKey(event.category),end=event.ends_at?`–${timeLabel(event.ends_at)}`:'',tags=(event.tags||[]).slice(0,3).map(tag=>`<span class="tag">${esc(tag)}</span>`).join(''),detail=event.category_detail?detailLabels[event.category_detail]||event.category_detail:null,mode=modeLabels[event.event_mode]||event.event_mode,metaParts=[event.organizer?`主催 ${esc(event.organizer)}`:'',event.location?esc(event.location):''].filter(Boolean).join(' · ');const classes=['event',event.event_mode==='offline'?'offline':''].filter(Boolean).join(' ');return `<article class="${classes}"><div class="time">${timeLabel(event.starts_at)}<small>${esc(end)}</small></div><div class="event-main"><h2>${esc(event.canonical_name||event.title)}</h2><div class="event-top"><span class="badge ${esc(category)}">${esc(categoryLabel(event))}</span>${detail?`<span class="badge">${esc(detail)}</span>`:''}${mode?`<span class="badge mode ${event.event_mode==='offline'?'offline':''}">${esc(mode)}</span>`:''}</div><div class="decision-row">${participationHtml(event)}${primaryActionHtml(event)}</div>${metaParts?`<div class="meta decision-meta">${metaParts}</div>`:''}${mediaHtml(event)}${event.description?`<p class="description">${esc(event.description)}</p>`:''}${detailsHtml(event)}${tags?`<div class="tags">${tags}</div>`:''}${evidenceHtml(event)}</div></article>`}
""".strip()

RECOMMENDATION_JS = r"""function recommendationHtml(row){const e=row.event,link=eventLinks(e)[0],tags=(e.tags||[]).filter(tag=>!STOP_TAGS.has(normalize(tag))).slice(0,3).map(tag=>`<span class="tag">${esc(tag)}</span>`).join('');return `<article class="recommendation-card"><h3>${esc(eventTitle(e))}</h3><div class="event-top"><span class="badge ${esc(categoryKey(e.category))}">${esc(categoryLabel(e))}</span><span class="badge">${esc(dayLabel(e.starts_at))} ${esc(timeLabel(e.starts_at))}</span></div><div class="meta">${e.organizer?`主催 ${esc(e.organizer)} · `:''}${esc(e.location||'VRChat')}</div><p class="recommendation-reason">${esc(row.reason)}</p><a class="event-link primary" href="${esc(link.url)}" target="_blank" rel="noopener noreferrer"${historyAttr(e)}>${esc(link.label)}</a>${tags?`<div class="tags">${tags}</div>`:''}</article>`}"""

FILTER_URL_JS = r"""
const FILTER_QUERY_KEYS=['q','category','source','range','deadlines'];
function syncFilterUrl(){const params=new URLSearchParams(location.search),q=$('#q').value.trim(),category=$('#category').value,source=$('#source').value,range=document.querySelector('.chip[data-range][aria-pressed="true"]')?.dataset.range||state.range||'week';q?params.set('q',q):params.delete('q');category&&category!=='all'?params.set('category',category):params.delete('category');source&&source!=='all'?params.set('source',source):params.delete('source');range&&range!=='week'?params.set('range',range):params.delete('range');$('#include-deadlines').checked?params.set('deadlines','1'):params.delete('deadlines');for(const key of [...params.keys()])if(FILTER_QUERY_KEYS.includes(key)&&!params.get(key))params.delete(key);const query=params.toString();history.replaceState(null,'',`${location.pathname}${query?`?${query}`:''}${location.hash}`)}
function restoreSelectFilter(id,value){if(!value||value==='all')return;const select=$(`#${id}`),apply=()=>{if(![...select.options].some(option=>option.value===value))return false;select.value=value;select.dispatchEvent(new Event('change',{bubbles:true}));return true};if(apply())return;const observer=new MutationObserver(()=>{if(apply())observer.disconnect()});observer.observe(select,{childList:true});window.setTimeout(()=>observer.disconnect(),10000)}
function restoreFilterUrl(){const params=new URLSearchParams(location.search),q=params.get('q'),range=params.get('range'),deadlines=params.get('deadlines');if(q!==null){$('#q').value=q;$('#q').dispatchEvent(new Event('input',{bubbles:true}))}if(range&&['today','week','month','all'].includes(range)){const chip=document.querySelector(`.chip[data-range="${CSS.escape(range)}"]`);if(chip)chip.click()}if(deadlines==='1'){const input=$('#include-deadlines');input.checked=true;input.dispatchEvent(new Event('change',{bubbles:true}))}restoreSelectFilter('category',params.get('category'));restoreSelectFilter('source',params.get('source'))}
function isFilterControl(target){return target instanceof Element&&(target.matches('#q,#category,#source,#include-deadlines')||target.matches('.chip[data-range]'))}
function syncTrustedFilterEvent(event){if(event.isTrusted&&isFilterControl(event.target))queueMicrotask(syncFilterUrl)}
document.addEventListener('input',syncTrustedFilterEvent);document.addEventListener('change',syncTrustedFilterEvent);document.addEventListener('click',syncTrustedFilterEvent);
$('#copy-filter-url').addEventListener('click',async()=>{syncFilterUrl();const button=$('#copy-filter-url'),label=button.textContent;try{if(!navigator.clipboard?.writeText)throw new Error('Clipboard API unavailable');await navigator.clipboard.writeText(location.href);button.textContent='URLをコピーしました'}catch{window.prompt('このURLをコピーしてください',location.href);button.textContent='URLを表示しました'}window.setTimeout(()=>{button.textContent=label},1800)});
restoreFilterUrl();
""".strip()


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


def _apply_filter_url(html: str) -> str:
    if FILTER_URL_MARKER in html:
        return html

    html = _replace_once(
        html,
        CARD_ORDER_MARKER,
        f"{CARD_ORDER_MARKER} {FILTER_URL_MARKER}",
        "card-order marker missing before filter URL integration",
    )
    html = _replace_once(
        html,
        '<label class="toggle"><input id="include-deadlines" type="checkbox"> 募集・締切も通常一覧に含める</label>',
        '<label class="toggle"><input id="include-deadlines" type="checkbox"> 募集・締切も通常一覧に含める</label><button id="copy-filter-url" class="button" type="button">絞り込みURLをコピー</button>',
        "filter controls marker missing",
    )
    html = _replace_once(
        html,
        "</script>",
        f"{FILTER_URL_JS}\n</script>",
        "frontend script closing marker missing",
    )
    return html


def reorder_home_view(html: str) -> str:
    """Apply decision-first information order, progressive evidence, and shareable filter state."""
    if VIEW_ORDER_MARKER in html and CARD_ORDER_MARKER in html and FILTER_URL_MARKER in html:
        return html

    html = _apply_home_order(html)
    html = _apply_card_order(html)
    html = _apply_filter_url(html)

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
