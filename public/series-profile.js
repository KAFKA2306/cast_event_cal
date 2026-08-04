(()=>{
  'use strict';

  const $=(selector,root=document)=>root.querySelector(selector);
  const $$=(selector,root=document)=>[...root.querySelectorAll(selector)];
  const normalize=value=>String(value??'').normalize('NFKC').toLocaleLowerCase('ja').replace(/\s+/g,' ').trim();
  const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,char=>({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;',
  }[char]));

  function events(){
    try{
      return typeof state!=='undefined'&&Array.isArray(state.events)?state.events:[];
    }catch{
      return [];
    }
  }

  function eventNames(event){
    return [event?.canonical_name,event?.title]
      .map(normalize)
      .filter(Boolean);
  }

  function profileIndex(){
    const index=new Map();
    for(const event of events()){
      if(!event?.series_profile) continue;
      for(const name of eventNames(event)){
        if(!index.has(name)) index.set(name,event);
      }
    }
    return index;
  }

  function installStyles(){
    if($('#series-profile-style')) return;
    const style=document.createElement('style');
    style.id='series-profile-style';
    style.textContent=`
      .series-profile{margin:10px 0 0;padding:12px;border:1px solid rgba(54,86,212,.18);border-radius:14px;background:linear-gradient(135deg,rgba(238,242,255,.72),rgba(255,255,255,.9))}
      .series-profile-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
      .series-profile-kicker{font-size:.66rem;font-weight:900;letter-spacing:.08em;color:var(--q-accent)}
      .series-profile-cadence{display:inline-flex;align-items:center;min-height:25px;padding:3px 8px;border-radius:999px;background:rgba(22,130,99,.11);color:var(--q-accent-2);font-size:.68rem;font-weight:850}
      .series-profile-frequency{color:var(--q-muted);font-size:.72rem;font-weight:750}
      .series-profile-intro{margin:8px 0 0;color:#33445e;font-size:.82rem;line-height:1.62}
      .series-profile-highlights{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:9px 0 0;padding:0;list-style:none}
      .series-profile-highlights li{padding:7px 8px;border-radius:10px;background:rgba(255,255,255,.78);color:#43536a;font-size:.71rem;line-height:1.45}
      .series-profile-guide{margin:9px 0 0;padding:8px 9px;border-left:3px solid var(--q-accent);border-radius:0 9px 9px 0;background:rgba(255,255,255,.7);color:#43536a;font-size:.74rem;line-height:1.55}
      .series-profile-note{margin:7px 0 0;color:var(--q-muted);font-size:.67rem;line-height:1.45}
      .series-profile-proof{display:inline-flex;margin-top:8px;color:var(--q-muted);font-size:.63rem;font-weight:750}
      .recommendation-series-badge{display:inline-flex;margin-top:7px;padding:4px 7px;border-radius:999px;background:rgba(22,130,99,.11);color:var(--q-accent-2);font-size:.65rem;font-weight:850}
      @media(max-width:720px){.series-profile-highlights{grid-template-columns:1fr}.series-profile{padding:10px}.series-profile-intro{font-size:.78rem}}
      @media(prefers-color-scheme:dark){.series-profile{background:linear-gradient(135deg,rgba(49,63,105,.42),rgba(26,35,50,.92));border-color:rgba(130,149,255,.28)}.series-profile-intro,.series-profile-guide,.series-profile-highlights li{color:#d4dceb}.series-profile-highlights li,.series-profile-guide{background:rgba(32,43,61,.82)}}
    `;
    document.head.append(style);
  }

  function profileHtml(profile){
    const schedule=profile?.schedule||{};
    const highlights=Array.isArray(profile?.highlights)?profile.highlights.slice(0,3):[];
    const reviewed=profile?.curation?.reviewed_at;
    const cadence=[schedule.label,schedule.cadence].filter(Boolean).join(' · ');
    return `
      <section class="series-profile" aria-label="イベントシリーズ紹介">
        <div class="series-profile-head">
          <span class="series-profile-kicker">CURATED SERIES PROFILE</span>
          ${schedule.label?`<span class="series-profile-cadence">${escapeHtml(schedule.label)}</span>`:''}
          ${schedule.cadence?`<span class="series-profile-frequency">${escapeHtml(schedule.cadence)}</span>`:''}
        </div>
        ${profile.introduction?`<p class="series-profile-intro">${escapeHtml(profile.introduction)}</p>`:''}
        ${highlights.length?`<ul class="series-profile-highlights">${highlights.map(item=>`<li>${escapeHtml(item)}</li>`).join('')}</ul>`:''}
        ${profile.first_time_guide?`<p class="series-profile-guide"><strong>初参加ガイド</strong><br>${escapeHtml(profile.first_time_guide)}</p>`:''}
        ${schedule.note?`<p class="series-profile-note">${escapeHtml(schedule.note)}</p>`:''}
        <span class="series-profile-proof">人手で確認したオントロジー${reviewed?` · ${escapeHtml(reviewed)}更新`:''}${cadence?'':''}</span>
      </section>`;
  }

  function enhanceEventCards(){
    const index=profileIndex();
    if(!index.size) return;
    for(const card of $$('.event')){
      if($('.series-profile',card)) continue;
      const title=normalize($('h2',card)?.textContent);
      const event=index.get(title);
      const profile=event?.series_profile;
      if(!profile) continue;
      const main=$('.event-main',card);
      const meta=$('.meta',main||card);
      if(!main) continue;
      const wrapper=document.createElement('div');
      wrapper.innerHTML=profileHtml(profile).trim();
      const section=wrapper.firstElementChild;
      if(meta?.nextSibling) main.insertBefore(section,meta.nextSibling);
      else main.append(section);
      card.dataset.ontologyId=String(profile.ontology_id||event.ontology_id||'');
      card.dataset.seriesType=String(profile.schedule?.type||'');
    }
  }

  function enhanceRecommendations(){
    const index=profileIndex();
    if(!index.size) return;
    for(const card of $$('.recommendation-card')){
      if($('.recommendation-series-badge',card)) continue;
      const title=normalize($('h3',card)?.textContent);
      const profile=index.get(title)?.series_profile;
      const label=profile?.schedule?.label;
      if(!label) continue;
      const badge=document.createElement('span');
      badge.className='recommendation-series-badge';
      badge.textContent=label;
      const meta=$('.meta',card);
      if(meta?.nextSibling) card.insertBefore(badge,meta.nextSibling);
      else card.append(badge);
    }
  }

  function enhance(){
    enhanceEventCards();
    enhanceRecommendations();
  }

  function start(){
    installStyles();
    const agenda=$('#agenda');
    if(agenda){
      new MutationObserver(()=>queueMicrotask(enhance)).observe(agenda,{childList:true,subtree:true});
    }
    const recommendations=$('#recommendation-grid');
    if(recommendations){
      new MutationObserver(()=>queueMicrotask(enhanceRecommendations)).observe(recommendations,{childList:true,subtree:true});
    }
    enhance();
  }

  document.readyState==='loading'
    ?document.addEventListener('DOMContentLoaded',start,{once:true})
    :start();
})();
