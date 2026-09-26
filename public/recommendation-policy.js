(()=>{'use strict';
const VERSION='recommendation.v1';
const arr=v=>Array.isArray(v)?v:[];
const text=v=>String(v??'').trim();
const instant=v=>{const d=v?new Date(v):null;return d&&Number.isFinite(d.getTime())?d:null};
const identity=e=>text(e?.occurrence_id||e?.id||e?.event_id);
const categories=e=>new Set([text(e?.category),...arr(e?.tags).map(text)].filter(Boolean));
function recommend(events,{currentEventId='',seenIds=[],preferredCategories=[]}={},now=new Date()){
  const nowDate=instant(now);if(!nowDate)throw new TypeError('now must be a valid instant');
  const seen=new Set(arr(seenIds).map(text)),preferred=new Set(arr(preferredCategories).map(text));
  const unique=new Map();
  for(const e of arr(events)){
    const id=identity(e),start=instant(e?.starts_at),end=instant(e?.ends_at);
    if(!id||id===text(currentEventId)||!start||start<nowDate||(end&&end<nowDate))continue;
    if(!unique.has(id))unique.set(id,e);
  }
  return [...unique.values()].map(e=>{
    const id=identity(e),start=instant(e.starts_at),cats=categories(e);
    const matched=[...cats].filter(c=>preferred.has(c)).sort();
    const reason={category_match:matched,seen:seen.has(id),starts_at:e.starts_at};
    const score=(matched.length?100:0)-(seen.has(id)?20:0)-Math.min(30,Math.floor((start-nowDate)/86400000));
    return {event:e,event_id:id,score,reason,policy_version:VERSION};
  }).sort((a,b)=>b.score-a.score||instant(a.event.starts_at)-instant(b.event.starts_at)||a.event_id.localeCompare(b.event_id,'en'));
}
const api={VERSION,recommend};
if(typeof module!=='undefined'&&module.exports)module.exports=api;else globalThis.CastEventRecommendation=api;
})();
