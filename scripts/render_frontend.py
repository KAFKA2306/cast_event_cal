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
.recommendations{margin:18px 0 6px;padding:20px;border:1px solid rgba(185,168,230,.58);border-radius:var(--radius);background:linear-gradient(135deg,rgba(255,255,255,.94),rgba(244,241,252,.88));box-shadow:var(--shadow)}.recommendations[hidden]{display:none}.recommendations-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap}.recommendations h2{margin:3px 0 6px;font-size:clamp(1.35rem,3vw,2rem);letter-spacing:-.03em}.recommendations-description{margin:0;color:var(--muted);font-size:.86rem;line-height:1.65;max-width:760px}.privacy-note{display:inline-flex;align-items:center;gap:6px;margin-top:8px;color:#49678f;font-size:.75rem;font-weight:750}.secondary-button{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:9px 13px;border-radius:999px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font-weight:750;cursor:pointer}.secondary-button:disabled{opacity:.45;cursor:not-allowed}.history-summary{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:15px 0 13px;color:var(--muted);font-size:.78rem}.history-chip{max-width:min(260px,100%);padding:5px 8px;border-radius:999px;background:rgba(185,168,230,.18);color:#43536a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.recommendation-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.recommendation-card{display:flex;flex-direction:column;min-width:0;border:1px solid var(--line);border-radius:17px;padding:14px;background:rgba(255,255,255,.92)}.recommendation-card:hover{border-color:var(--lav)}.recommendation-card h3{margin:8px 0 5px;font-size:.98rem;line-height:1.45;overflow-wrap:anywhere}.recommendation-card .meta{margin-bottom:8px}.recommendation-reason{margin:0 0 10px;padding:8px 9px;border-radius:11px;background:rgba(183,219,200,.24);color:#39566a;font-size:.75rem;line-height:1.5}.recommendation-card .event-link{margin-top:auto;align-self:flex-start}.recommendation-empty{grid-column:1/-1;padding:20px;border:1px dashed #b9c7dc;border-radius:15px;color:var(--muted);line-height:1.7;text-align:center;background:rgba(255,255,255,.62)}
@media(max-width:920px){.recommendation-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:560px){.recommendations{padding:15px}.recommendation-grid{grid-template-columns:1fr}}@media(prefers-reduced-motion:reduce){.event-media{transition:none}}
""".strip()

RECOMMENDATION_SECTION = """
<section id="recommendations" class="recommendations" aria-labelledby="recommendation-title" hidden>
  <div class="recommendations-head">
    <div><div class="eyebrow">LOCAL-FIRST RECOMMEND</div><h2 id="recommendation-title">あなたへのおすすめ</h2><p id="recommendation-status" class="recommendations-description">この端末の閲覧履歴からおすすめを準備しています。</p><span class="privacy-note">端末内で計算 · 外部送信なし</span></div>
    <button id="reset-history" class="secondary-button" type="button">閲覧履歴をリセット</button>
  </div>
  <div id="history-summary" class="history-summary" aria-live="polite"></div>
  <div id="recommendation-grid" class="recommendation-grid"></div>
</section>
""".strip()

STATE_BLOCK = """
const STORAGE_KEY='kafka2306-vrc-event-click-history-v2';
const HISTORY_LIMIT=120;
const HISTORY_MAX_AGE_DAYS=180;
const RECOMMENDATION_LIMIT=6;
const HALF_LIFE_DAYS=28;
const MMR_RELEVANCE=0.82;
const state={events:[],health:null,range:'week',categories:fallbackCategories,history:loadHistory(),storageAvailable:true};
""".strip()

RECOMMENDATION_HELPERS = """
const normalize=v=>String(v??'').normalize('NFKC').trim().toLocaleLowerCase('ja');
const unique=values=>[...new Set(values.filter(Boolean))];
const weekdayLabel=i=>new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',weekday:'short'}).format(new Date(i));
const hourJst=i=>Number(new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Tokyo',hour:'2-digit',hour12:false}).format(new Date(i)))%24;
const STOP_TAGS=new Set(['vrchat','vrc','イベント','公式','告知','yahoo!リアルタイム検索','yahooリアルタイム検索']);
function eventId(e){return String(e?.id||e?.source_id||e?.primary_action_url||e?.url||'')}
function eventTitle(e){return String(e?.canonical_name||e?.title||'イベント')}
function timeBand(startsAt){const hour=hourJst(startsAt);if(hour>=5&&hour<11)return'朝';if(hour>=11&&hour<17)return'昼';if(hour>=17&&hour<21)return'夜';return'深夜'}
function addFeature(rows,key,label,weight){const normalized=normalize(key);if(!normalized)return;const existing=rows.find(row=>row.key===normalized);if(existing){existing.weight=Math.max(existing.weight,weight);return}rows.push({key:normalized,label:String(label),weight})}
function eventFeatures(e){const rows=[];const grouped=categoryKey(e.category);addFeature(rows,`group:${grouped}`,categoryLabel(e),2.6);if(e.category_detail)addFeature(rows,`detail:${e.category_detail}`,detailLabels[e.category_detail]||e.category_detail,1.45);if(e.event_mode)addFeature(rows,`mode:${e.event_mode}`,modeLabels[e.event_mode]||e.event_mode,.7);if(e.organizer)addFeature(rows,`organizer:${e.organizer}`,String(e.organizer),2.15);for(const tag of unique(Array.isArray(e.tags)?e.tags.map(String):[]).slice(0,14)){if(STOP_TAGS.has(normalize(tag)))continue;addFeature(rows,`tag:${tag}`,tag,1.35)}if(e.event_format)addFeature(rows,`format:${e.event_format}`,String(e.event_format),1.05);if(e.audience)addFeature(rows,`audience:${e.audience}`,String(e.audience),.9);if(e.location&&normalize(e.location)!=='vrchat')addFeature(rows,`location:${e.location}`,String(e.location),.65);if(e.starts_at){const band=timeBand(e.starts_at);addFeature(rows,`time:${band}`,`${band}開催`,.8);const weekday=weekdayLabel(e.starts_at);addFeature(rows,`weekday:${weekday}`,`${weekday}曜日`,.55)}if(e.source)addFeature(rows,`source:${e.source}`,String(e.source),.25);return rows.slice(0,28)}
function loadHistory(){try{const parsed=JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]');if(!Array.isArray(parsed))return[];const cutoff=Date.now()-HISTORY_MAX_AGE_DAYS*86400000;return parsed.filter(row=>row&&row.id&&row.title&&Number.isFinite(Number(row.count))&&Date.parse(row.viewed_at)>=cutoff).map(row=>({id:String(row.id),title:String(row.title),count:Math.max(1,Number(row.count)),viewed_at:String(row.viewed_at),features:Array.isArray(row.features)?row.features.filter(f=>f&&f.key&&f.label&&Number.isFinite(Number(f.weight))).slice(0,28).map(f=>({key:String(f.key),label:String(f.label),weight:Number(f.weight)})):[]})).sort((a,b)=>Date.parse(b.viewed_at)-Date.parse(a.viewed_at)).slice(0,HISTORY_LIMIT)}catch{return[]}}
function saveHistory(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(state.history.slice(0,HISTORY_LIMIT)));state.storageAvailable=true}catch{state.storageAvailable=false}}
function recordVisit(id){const e=state.events.find(row=>eventId(row)===String(id));if(!e)return;const existing=state.history.find(row=>row.id===String(id));const record={id:String(id),title:eventTitle(e),count:(existing?.count||0)+1,viewed_at:new Date().toISOString(),features:eventFeatures(e)};state.history=[record,...state.history.filter(row=>row.id!==String(id))].slice(0,HISTORY_LIMIT);saveHistory();renderRecommendations()}
function buildProfile(){const weights=new Map();const now=Date.now();for(const entry of state.history){const ageDays=Math.max(0,(now-Date.parse(entry.viewed_at))/86400000);const decay=2**(-ageDays/HALF_LIFE_DAYS);const interaction=(1+Math.log2(entry.count+1))*decay;for(const feature of entry.features)weights.set(feature.key,(weights.get(feature.key)||0)+feature.weight*interaction)}return{weights}}
function cosineProfile(profile,features){let dot=0,itemNorm=0,profileNorm=0;for(const value of profile.weights.values())profileNorm+=value*value;for(const feature of features){const p=profile.weights.get(feature.key)||0;dot+=p*feature.weight;itemNorm+=feature.weight*feature.weight}return dot&&itemNorm&&profileNorm?dot/(Math.sqrt(itemNorm)*Math.sqrt(profileNorm)):0}
function featureSimilarity(a,b){const left=new Map(a.map(f=>[f.key,f.weight]));const right=new Map(b.map(f=>[f.key,f.weight]));const keys=new Set([...left.keys(),...right.keys()]);let intersection=0,union=0;for(const key of keys){const x=left.get(key)||0,y=right.get(key)||0;intersection+=Math.min(x,y);union+=Math.max(x,y)}return union?intersection/union:0}
function startUtility(e){const days=(new Date(e.starts_at)-new Date())/86400000;if(days<0||days>120)return 0;return 1/(1+days/12)}
function deterministicNovelty(id){let hash=2166136261;for(const char of String(id)){hash^=char.charCodeAt(0);hash=Math.imul(hash,16777619)}return((hash>>>0)%1000)/1000}
function matchedReasons(profile,features){const seen=new Set();return features.map(feature=>({label:feature.label,score:(profile.weights.get(feature.key)||0)*feature.weight,key:feature.key})).filter(row=>row.score>0&&!row.key.startsWith('source:')).sort((a,b)=>b.score-a.score).filter(row=>{const key=normalize(row.label);if(seen.has(key))return false;seen.add(key);return true}).slice(0,2).map(row=>row.label)}
function historyAttr(e){return eventId(e)?` data-event-history-id="${esc(eventId(e))}"`:''}
function recommendationCandidates(){const now=new Date(),end=rangeEnd('all'),includeDeadlines=$('#include-deadlines').checked,profile=buildProfile(),historyIds=new Set(state.history.map(row=>row.id)),hasHistory=state.history.length>0;const scored=state.events.filter(e=>{const start=new Date(e.starts_at);return eventId(e)&&start>=now&&start<=end&&(includeDeadlines||categoryKey(e.category)!=='recruitment_deadline')&&eventLinks(e).length}).map(e=>{const features=eventFeatures(e),affinity=hasHistory?cosineProfile(profile,features):0,soon=startUtility(e),seen=historyIds.has(eventId(e))?1:0,exploration=deterministicNovelty(eventId(e));const score=hasHistory?.83*affinity+.13*soon+.04*exploration-.18*seen:.82*soon+.18*exploration;const matched=matchedReasons(profile,features);const reason=matched.length?`閲覧傾向「${matched.join('・')}」と一致`:seen?'以前に開いたイベント':'開催が近い未閲覧イベント';return{event:e,features,score,reason,seen}}).sort((a,b)=>b.score-a.score||new Date(a.event.starts_at)-new Date(b.event.starts_at));const unseen=scored.filter(row=>!row.seen),pool=unseen.length>=RECOMMENDATION_LIMIT?unseen:scored;const selected=[];while(selected.length<RECOMMENDATION_LIMIT&&pool.length>selected.length){let best=null;for(const candidate of pool){if(selected.includes(candidate))continue;const redundancy=selected.length?Math.max(...selected.map(chosen=>featureSimilarity(candidate.features,chosen.features))):0;const mmr=MMR_RELEVANCE*candidate.score-(1-MMR_RELEVANCE)*redundancy;if(!best||mmr>best.mmr)best={candidate,mmr}}if(!best)break;selected.push(best.candidate)}return selected}
function recommendationHtml(row){const e=row.event,link=eventLinks(e)[0],tags=(e.tags||[]).filter(tag=>!STOP_TAGS.has(normalize(tag))).slice(0,3).map(tag=>`<span class="tag">${esc(tag)}</span>`).join('');return `<article class="recommendation-card"><div class="event-top"><span class="badge ${esc(categoryKey(e.category))}">${esc(categoryLabel(e))}</span><span class="badge">${esc(dayLabel(e.starts_at))} ${esc(timeLabel(e.starts_at))}</span></div><h3>${esc(eventTitle(e))}</h3><div class="meta">${e.organizer?`主催 ${esc(e.organizer)} · `:''}${esc(e.location||'VRChat')}</div><p class="recommendation-reason">${esc(row.reason)}</p>${tags?`<div class="tags">${tags}</div>`:''}<a class="event-link primary" href="${esc(link.url)}" target="_blank" rel="noopener noreferrer"${historyAttr(e)}>${esc(link.label)}</a></article>`}
function renderHistorySummary(){const total=state.history.reduce((sum,row)=>sum+row.count,0),container=$('#history-summary');$('#reset-history').disabled=!total;container.innerHTML='';if(!total){container.textContent='イベントの公式リンクを開くと、このブラウザ内に閲覧傾向が保存されます。';return}container.insertAdjacentHTML('beforeend',`<span>最近見た（計${total}クリック）</span>`);for(const row of state.history.slice(0,5))container.insertAdjacentHTML('beforeend',`<span class="history-chip">${esc(row.title)}${row.count>1?` ×${row.count}`:''}</span>`)}
function renderRecommendations(){const section=$('#recommendations');if(!state.events.length){section.hidden=true;return}const rows=recommendationCandidates(),total=state.history.reduce((sum,row)=>sum+row.count,0);renderHistorySummary();$('#recommendation-status').textContent=total?`この端末の${state.history.length}件の閲覧履歴を時間減衰で学習し、関連度と多様性を両立するよう再ランキングしています。`:'履歴がまだないため、開催の近さとカテゴリの多様性から候補を表示しています。公式リンクを開くほど個人化されます。';if(!state.storageAvailable)$('#recommendation-status').textContent+=' ストレージが制限されているため、履歴はこのページを開いている間だけ保持されます。';$('#recommendation-grid').innerHTML=rows.length?rows.map(recommendationHtml).join(''):'<div class="recommendation-empty">今後120日以内に、公式リンクを持つ推薦候補がありません。</div>';section.hidden=false}
function historyClick(event){const link=event.target.closest('[data-event-history-id]');if(link)recordVisit(link.dataset.eventHistoryId)}
""".strip()

MEDIA_HELPER = """
function canonicalLinkKey(raw){try{const u=new URL(String(raw||''));const h=u.hostname.toLowerCase().replace(/^www\\./,'');if((h==='x.com'||h==='twitter.com')&&/\\/status\\/(\\d+)/.test(u.pathname))return`x-status:${u.pathname.match(/\\/status\\/(\\d+)/)[1]}`;if(h==='vrchat.com'&&/\\/home\\/group\\/(grp_[a-z0-9-]+)/i.test(u.pathname))return`vrchat-group:${u.pathname.match(/\\/home\\/group\\/(grp_[a-z0-9-]+)/i)[1].toLowerCase()}`;u.hash='';['utm_source','utm_medium','utm_campaign','utm_term','utm_content'].forEach(k=>u.searchParams.delete(k));return u.toString().replace(/\\/$/,'')}catch{return String(raw||'')}}
function preferredActionUrl(e){const rows=Array.isArray(e.official_links)?e.official_links:[];const group=rows.find(r=>String(r?.kind||'')==='vrchat_group'&&String(r?.url||'').startsWith('https://vrchat.com/home/group/'));return String(group?.url||e.vrchat_group_url||e.primary_action_url||e.url||'')}
function mediaHtml(e){const url=String(e.preferred_image_url||e.vrchat_group_image_url||e.image_url||'');if(!url.startsWith('https://'))return'';const target=preferredActionUrl(e);const imageKind=String(e.preferred_image_kind||e.image_kind||'');const kind=imageKind==='post_media'?'公式投稿画像':imageKind==='vrchat_group'?'VRChat公式グループ画像':'公式プロフィール画像';const image=`<img class="event-media" src="${esc(url)}" alt="${esc((e.canonical_name||e.title||'イベント')+' '+kind)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;return target.startsWith('https://')?`<a class="event-media-link" href="${esc(target)}" target="_blank" rel="noopener noreferrer"${historyAttr(e)} aria-label="${esc((e.canonical_name||e.title||'イベント')+'の参加・募集ページを開く')}">${image}</a>`:image}
function assetProofHtml(e){const rows=[];const links=Array.isArray(e.official_links)?e.official_links:[];const group=links.find(r=>String(r?.kind||'')==='vrchat_group'&&String(r?.url||'').startsWith('https://'));const groupUrl=String(group?.url||e.vrchat_group_url||'');if(groupUrl.startsWith('https://'))rows.push(`<a href="${esc(groupUrl)}" target="_blank" rel="noopener noreferrer"${historyAttr(e)}>VRChat Group</a>`);if(String(e.official_x_url||'').startsWith('https://'))rows.push(`<a href="${esc(e.official_x_url)}" target="_blank" rel="noopener noreferrer"${historyAttr(e)}>公式X</a>`);if(String(e.official_website_url||'').startsWith('https://'))rows.push(`<a href="${esc(e.official_website_url)}" target="_blank" rel="noopener noreferrer"${historyAttr(e)}>公式Web</a>`);const imageUrl=String(e.preferred_image_url||e.vrchat_group_image_url||e.image_url||'');if(imageUrl.includes('webp'))rows.push(`<a href="${esc(imageUrl)}" target="_blank" rel="noopener noreferrer"${historyAttr(e)}>WebP画像</a>`);return rows.length?`<div class="asset-proof">${rows.join('')}</div>`:''}
""".strip()

OLD_EVENT_LINKS = """function eventLinks(event){const rows=Array.isArray(event.official_links)?event.official_links:[];const seen=new Set();const valid=[];for(const row of rows){const url=String(row?.url||'');if(!url.startsWith('https://')||seen.has(url))continue;seen.add(url);valid.push({url,label:String(row?.label||'公式リンク'),kind:String(row?.kind||'official')})}if(!valid.length&&String(event.url||'').startsWith('https://'))valid.push({url:event.url,label:'告知・参加方法',kind:'announcement'});return valid.slice(0,3)}"""

NEW_EVENT_LINKS = """function eventLinks(event){const rows=Array.isArray(event.official_links)?event.official_links:[];const seen=new Set();const seenKinds=new Set();const valid=[];for(const row of rows){const url=String(row?.url||'');const kind=String(row?.kind||'official');if(!url.startsWith('https://'))continue;const key=canonicalLinkKey(url);if(seen.has(key)||(kind==='announcement'&&seenKinds.has('announcement')))continue;seen.add(key);seenKinds.add(kind);valid.push({url,label:String(row?.label||'公式リンク'),kind})}if(!valid.length&&String(event.url||'').startsWith('https://'))valid.push({url:event.url,label:'告知・参加方法',kind:'announcement'});return valid.slice(0,3)}"""


def replace_once(html: str, old: str, new: str, error: str) -> str:
    if old not in html:
        raise ValueError(error)
    return html.replace(old, new, 1)


def patch_frontend(html: str) -> str:
    html = replace_once(
        html,
        '<meta name="description" content="VRChatの公開イベントを実表示データ由来のカテゴリオントロジーで分類し、公式リンクと参加方法付きで探せるカレンダー">',
        '<meta name="description" content="VRChatの公開イベントを実表示データ由来のカテゴリオントロジーで分類し、公式リンクと参加方法付きで探せるカレンダー。端末内の閲覧履歴だけを使うレコメンドに対応。">\n<meta name="app-build" content="2026-08-03-local-history-recommend-v2">',
        "frontend description marker missing",
    )
    html = replace_once(html, "</style>", f"{ASSET_CSS}\n</style>", "frontend style marker missing")
    html = replace_once(
        html,
        '<div class="statusbar"><div><strong id="result-count">0件</strong>を表示</div>',
        f'{RECOMMENDATION_SECTION}\n<div class="statusbar"><div><strong id="result-count">0件</strong>を表示</div>',
        "frontend recommendation section marker missing",
    )
    html = replace_once(
        html,
        "const state={events:[],health:null,range:'week',categories:fallbackCategories};",
        STATE_BLOCK,
        "frontend state marker missing",
    )
    marker = "function detailsHtml(event){"
    html = replace_once(html, marker, f"{MEDIA_HELPER}\n{marker}", "frontend details marker missing")
    html = replace_once(html, OLD_EVENT_LINKS, NEW_EVENT_LINKS, "frontend eventLinks marker missing")
    html = replace_once(
        html,
        "function filtered(){",
        f"{RECOMMENDATION_HELPERS}\nfunction filtered(){{",
        "frontend filtered marker missing",
    )
    html = replace_once(
        html,
        '<div class="event-main"><div class="event-top">',
        '<div class="event-main">${mediaHtml(event)}<div class="event-top">',
        "frontend event card marker missing",
    )
    html = replace_once(
        html,
        "${detailsHtml(event)}${tags?`<div class=\"tags\">${tags}</div>`:''}</div>",
        "${detailsHtml(event)}${assetProofHtml(event)}${tags?`<div class=\"tags\">${tags}</div>`:''}</div>",
        "frontend card tail marker missing",
    )
    html = replace_once(
        html,
        'target="_blank" rel="noopener noreferrer">${esc(link.label)}</a>',
        'target="_blank" rel="noopener noreferrer"${historyAttr(event)}>${esc(link.label)}</a>',
        "frontend event link history marker missing",
    )
    html = replace_once(html, "function render(){", "function renderAgenda(){", "frontend render marker missing")
    html = replace_once(
        html,
        "function buildSources(){",
        "function render(){renderAgenda();renderRecommendations()}\nfunction buildSources(){",
        "frontend buildSources marker missing",
    )
    html = replace_once(
        html,
        "</script>",
        "$('#reset-history').addEventListener('click',()=>{state.history=[];saveHistory();renderRecommendations()});$('#agenda').addEventListener('click',historyClick);$('#recommendation-grid').addEventListener('click',historyClick);\n</script>",
        "frontend script marker missing",
    )
    return html


def main() -> int:
    enrich_event_ontology()
    build_observed_ontology()
    payload = json.loads(EVENTS.read_text(encoding="utf-8"))
    generated_at = str(payload.get("generated_at") or "")
    html = TEMPLATE.read_text(encoding="utf-8").replace("{{GENERATED_AT}}", generated_at)
    html = patch_frontend(html)
    required = (
        "VRChat Event Calendar",
        'id="agenda"',
        'id="recommendations"',
        "preferredActionUrl",
        "canonicalLinkKey",
        "recommendationCandidates",
        "MMR_RELEVANCE=0.82",
        "data-event-history-id",
        "localStorage",
    )
    missing = [marker for marker in required if marker not in html]
    if missing:
        raise ValueError(f"frontend template validation failed: {missing}")
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"rendered {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
