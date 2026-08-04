(()=>{
  'use strict';

  const VERSION='2026-08-04-quality-view-v5';
  const DETAIL_KEY='vrc-event-detailed-view-v1';
  const $=(selector,root=document)=>root.querySelector(selector);
  const $$=(selector,root=document)=>[...root.querySelectorAll(selector)];
  const make=(tag,className,text)=>{
    const element=document.createElement(tag);
    if(className) element.className=className;
    if(text) element.textContent=text;
    return element;
  };
  const scrollToEl=element=>element?.scrollIntoView({behavior:'smooth',block:'start'});

  let pageLimit=defaultPageLimit();

  function defaultPageLimit(){
    return matchMedia('(max-width:600px)').matches?12:20;
  }

  function currentRange(){
    return $('.chip[data-range][aria-pressed=true]')?.dataset.range||'today';
  }

  function updateRangeActions(range){
    $$('.ux-action[data-range-target]').forEach(button=>{
      const active=button.dataset.rangeTarget===range;
      button.dataset.active=String(active);
      if(active) button.dataset.primary='true';
      else delete button.dataset.primary;
    });
  }

  function selectRange(range,scroll=true){
    const chip=$(`.chip[data-range="${range}"]`);
    if(!chip) return;
    chip.click();
    updateRangeActions(range);
    if(scroll) scrollToEl($('.statusbar'));
  }

  function hero(){
    const root=$('.hero');
    if(!root) return;
    const eye=$('.eyebrow',root);
    const title=$('h1',root);
    const lede=$('.lede',root);
    const actions=$('.hero-actions',root);
    if(eye) eye.textContent='VRCHAT EVENT GUIDE · JST';
    if(title) title.textContent='今夜のVRChat';
    if(lede) lede.textContent='開催中・今夜のイベントを、時刻と参加方法から選べます。公式情報へ最短で移動できます。';
    if(actions&&!$('.ux-data-menu',root)){
      const details=make('details','ux-data-menu');
      const summary=make('summary','','データ');
      actions.replaceWith(details);
      details.append(summary,actions);
    }
  }

  function command(){
    if($('.ux-command')||!$('.hero')) return;
    const bar=make('section','ux-command');
    bar.setAttribute('aria-label','クイック操作');
    bar.innerHTML=`
      <div class="ux-next" aria-live="polite">
        <span class="ux-live">UPCOMING</span>
        <span class="ux-next-copy">
          <strong id="ux-next-title">イベントを読み込み中</strong>
          <span id="ux-next-meta">開催情報を確認しています</span>
        </span>
      </div>
      <div class="ux-actions">
        <button class="ux-action" data-ux="today" data-range-target="today">今日</button>
        <button class="ux-action" data-ux="week" data-range-target="week">7日</button>
        <button class="ux-action" data-ux="search">検索</button>
        <button class="ux-action" data-ux="recommend">おすすめ</button>
        <button class="ux-density" data-ux="density">詳細表示</button>
      </div>`;
    $('.hero').after(bar);
    bar.addEventListener('click',event=>{
      const action=event.target.closest('[data-ux]')?.dataset.ux;
      if(action==='today'||action==='week') selectRange(action);
      if(action==='recommend') scrollToEl($('#recommendations'));
      if(action==='search'){
        scrollToEl($('.controls'));
        setTimeout(()=>$('#q')?.focus(),180);
      }
      if(action==='density') density();
    });
  }

  function filters(){
    const controls=$('.controls');
    if(!controls||$('.ux-filter-toggle',controls)) return;
    const button=make('button','ux-filter-toggle','カテゴリ・情報源・期間を絞り込む');
    button.type='button';
    button.setAttribute('aria-expanded','false');
    button.onclick=()=>{
      const open=controls.classList.toggle('ux-filters-open');
      button.setAttribute('aria-expanded',String(open));
      button.textContent=open?'絞り込みを閉じる':'カテゴリ・情報源・期間を絞り込む';
    };
    controls.append(button);
  }

  function reset(){
    const row=$('.filter-row');
    if(!row||$('.ux-reset',row)) return;
    const button=make('button','ux-reset','条件をリセット');
    button.type='button';
    button.onclick=()=>{
      for(const [id,value] of [['q',''],['category','all'],['source','all']]){
        const element=$(`#${id}`);
        if(!element) continue;
        element.value=value;
        element.dispatchEvent(new Event(id==='q'?'input':'change',{bubbles:true}));
      }
      const deadlines=$('#include-deadlines');
      if(deadlines){
        deadlines.checked=false;
        deadlines.dispatchEvent(new Event('change',{bubbles:true}));
      }
      selectRange('today',false);
    };
    row.append(button);
  }

  function metrics(){
    for(const [id,range] of [['metric-today','today'],['metric-week','week'],['metric-total','all']]){
      const metric=$(`#${id}`)?.closest('.metric');
      if(!metric||metric.dataset.uxRange) continue;
      metric.dataset.uxRange=range;
      metric.tabIndex=0;
      metric.setAttribute('role','button');
      metric.setAttribute('aria-label',`${metric.textContent.trim()}を表示`);
      const run=()=>selectRange(range);
      metric.onclick=run;
      metric.onkeydown=event=>{
        if(event.key==='Enter'||event.key===' '){
          event.preventDefault();
          run();
        }
      };
    }
  }

  function density(force){
    const detailed=typeof force==='boolean'?force:!document.body.classList.contains('ux-detailed');
    document.body.classList.toggle('ux-detailed',detailed);
    try{localStorage.setItem(DETAIL_KEY,detailed?'1':'0')}catch{}
    $$('.ux-density').forEach(button=>{
      button.textContent=detailed?'標準表示':'詳細表示';
      button.setAttribute('aria-pressed',String(detailed));
    });
  }

  function topButton(){
    if($('.ux-back-top')) return;
    const button=make('button','ux-back-top','↑');
    button.type='button';
    button.setAttribute('aria-label','ページ先頭へ戻る');
    button.dataset.visible='false';
    button.onclick=()=>window.scrollTo({top:0,behavior:'smooth'});
    document.body.append(button);
    addEventListener('scroll',()=>button.dataset.visible=String(scrollY>720),{passive:true});
  }

  function applyPagination(){
    const agenda=$('#agenda');
    if(!agenda) return;
    const events=$$('.event',agenda);
    events.forEach((event,index)=>event.hidden=index>=pageLimit);
    $$('.day',agenda).forEach(day=>{
      day.hidden=!$$('.event',day).some(event=>!event.hidden);
    });

    let button=$('.ux-load-more');
    const remaining=Math.max(0,events.length-pageLimit);
    if(!remaining){
      button?.remove();
      return;
    }
    if(!button){
      button=make('button','ux-load-more');
      button.type='button';
      agenda.after(button);
      button.onclick=()=>{
        pageLimit+=defaultPageLimit();
        applyPagination();
      };
    }
    button.textContent=`さらに表示（残り${remaining}件）`;
  }

  function enhance(){
    const first=$('.event:not([hidden])');
    const title=$('#ux-next-title');
    const meta=$('#ux-next-meta');

    $$('.event').forEach(card=>{
      if(card.dataset.uxEnhanced===VERSION) return;
      card.dataset.uxEnhanced=VERSION;
      const name=$('h2',card)?.textContent.trim();
      if(name) card.setAttribute('aria-label',name);
      $$('.event-link',card).forEach((link,index)=>{
        if(index===0) link.setAttribute('aria-label',`${name||'イベント'}の公式情報を開く`);
      });
    });

    applyPagination();
    const visible=$('.event:not([hidden])');
    if(!title||!meta) return;
    if(!visible){
      title.textContent='条件に合うイベントはありません';
      meta.textContent='期間または絞り込み条件を変更してください';
      return;
    }
    title.textContent=$('h2',visible)?.textContent.trim()||'次のイベント';
    meta.textContent=[
      visible.closest('.day')?.querySelector('.day-label strong')?.textContent.trim(),
      $('.time',visible)?.textContent.replace(/\s+/g,' ').trim(),
    ].filter(Boolean).join(' · ');
  }

  function observe(){
    const agenda=$('#agenda');
    if(!agenda) return;
    const observer=new MutationObserver(()=>{
      pageLimit=defaultPageLimit();
      queueMicrotask(enhance);
    });
    observer.observe(agenda,{childList:true,subtree:true});
    enhance();
  }

  function keyboard(){
    addEventListener('keydown',event=>{
      const editing=event.target instanceof HTMLInputElement||event.target instanceof HTMLSelectElement||event.target instanceof HTMLTextAreaElement;
      if(event.key==='/'&&!editing){
        event.preventDefault();
        scrollToEl($('.controls'));
        $('#q')?.focus();
      }
      if(editing||event.ctrlKey||event.metaKey||event.altKey) return;
      if(event.key.toLowerCase()==='t') selectRange('today');
      if(event.key.toLowerCase()==='w') selectRange('week');
      if(event.key.toLowerCase()==='r') scrollToEl($('#recommendations'));
    });
  }

  function start(){
    document.documentElement.dataset.qualityView=VERSION;
    $('.ux-mobile-nav')?.remove();
    if(!$('.skip-link')){
      const link=make('a','skip-link','イベント一覧へ移動');
      link.href='#agenda';
      document.body.prepend(link);
    }
    hero();
    command();
    filters();
    reset();
    metrics();
    let detailed=false;
    try{detailed=localStorage.getItem(DETAIL_KEY)==='1'}catch{}
    density(detailed);
    topButton();
    observe();
    keyboard();
    $$('.chip[data-range]').forEach(chip=>chip.addEventListener('click',()=>updateRangeActions(chip.dataset.range)));
    setTimeout(()=>selectRange('today',false),0);
  }

  document.readyState==='loading'
    ?document.addEventListener('DOMContentLoaded',start,{once:true})
    :start();
})();

(()=>{
  'use strict';

  const $=(selector,root=document)=>root.querySelector(selector);
  const $$=(selector,root=document)=>[...root.querySelectorAll(selector)];
  const normalize=value=>String(value??'').normalize('NFKC').toLocaleLowerCase('ja').replace(/\s+/g,' ').trim();
  const SEARCH_ALIASES=new Map([
    ['cast',['cast','キャスト','接客','1対1','一対一','個室','メイド','執事','店員','スタッフ','ゲスト募集','キャスト募集','cast service','cast_service']],
    ['キャスト',['cast','キャスト','接客','1対1','一対一','個室','メイド','執事','店員','スタッフ','ゲスト募集','キャスト募集','cast service','cast_service']],
    ['接客',['cast','キャスト','接客','1対1','一対一','個室','メイド','執事','店員','スタッフ','ゲスト募集','キャスト募集','cast service','cast_service']],
  ]);
  const BATCH_DESKTOP=20;
  const BATCH_MOBILE=12;

  let semanticAliases=null;
  let semanticValue='';
  let semanticLimit=batchSize();
  let semanticGuard=false;
  let semanticTimer=0;
  let sentinel=null;
  let infiniteObserver=null;

  function batchSize(){
    return matchMedia('(max-width:600px)').matches?BATCH_MOBILE:BATCH_DESKTOP;
  }

  function aliasesFor(value){
    return SEARCH_ALIASES.get(normalize(value))||null;
  }

  function installStyles(){
    if($('#ux-infinite-scroll-style')) return;
    const style=document.createElement('style');
    style.id='ux-infinite-scroll-style';
    style.textContent=`
      .ux-load-more{display:none!important}
      .ux-infinite-sentinel{order:6;display:flex;min-height:52px;align-items:center;justify-content:center;margin:8px 0 2px;color:var(--q-muted);font-size:.76rem;font-weight:750;text-align:center}
      .ux-infinite-sentinel::before{content:"";width:8px;height:8px;margin-right:8px;border-radius:50%;background:var(--q-accent);box-shadow:0 0 0 5px rgba(54,86,212,.1)}
      .ux-infinite-sentinel[data-complete="true"]::before{background:var(--q-accent-2)}
    `;
    document.head.append(style);
  }

  function ensureSentinel(){
    const agenda=$('#agenda');
    if(!agenda) return null;
    if(!sentinel){
      sentinel=document.createElement('div');
      sentinel.className='ux-infinite-sentinel';
      sentinel.setAttribute('role','status');
      sentinel.setAttribute('aria-live','polite');
      sentinel.textContent='イベントを読み込んでいます';
    }
    const loadMore=$('.ux-load-more');
    if(loadMore) loadMore.after(sentinel);
    else agenda.after(sentinel);
    return sentinel;
  }

  function hiddenNormalCount(){
    return $$('.event[hidden]',$('#agenda')).length;
  }

  function updateNormalSentinel(){
    if(semanticAliases) return;
    const marker=ensureSentinel();
    if(!marker) return;
    const remaining=hiddenNormalCount();
    marker.dataset.complete=String(remaining===0);
    marker.textContent=remaining?`下へスクロールすると残り${remaining}件を自動で表示します`:'すべてのイベントを表示しました';
  }

  function loadNormalBatch(){
    const button=$('.ux-load-more');
    if(!button){
      updateNormalSentinel();
      return;
    }
    button.click();
    setTimeout(updateNormalSentinel,0);
  }

  function cardMatches(card,aliases){
    const text=normalize(card.textContent);
    return aliases.some(alias=>text.includes(normalize(alias)));
  }

  function updateSemanticSentinel(matches){
    const marker=ensureSentinel();
    if(!marker) return;
    const visible=Math.min(semanticLimit,matches.length);
    const remaining=Math.max(0,matches.length-visible);
    marker.dataset.complete=String(remaining===0);
    marker.textContent=remaining
      ?`${visible}/${matches.length}件を表示中 · 下へスクロールして続きを表示`
      :`${matches.length}件をすべて表示しました`;
  }

  function applySemanticFilter(reset=false){
    if(!semanticAliases) return;
    if(reset) semanticLimit=batchSize();
    const agenda=$('#agenda');
    if(!agenda) return;
    const cards=$$('.event',agenda);
    const matches=cards.filter(card=>cardMatches(card,semanticAliases));
    cards.forEach(card=>{
      card.dataset.semanticMatch=String(matches.includes(card));
      card.hidden=true;
    });
    matches.slice(0,semanticLimit).forEach(card=>{card.hidden=false});
    $$('.day',agenda).forEach(day=>{
      day.hidden=!$$('.event',day).some(card=>!card.hidden);
    });
    const count=$('#result-count');
    if(count) count.textContent=`${matches.length}件`;
    updateSemanticSentinel(matches);
  }

  function loadSemanticBatch(){
    if(!semanticAliases) return;
    semanticLimit+=batchSize();
    applySemanticFilter(false);
  }

  function rerenderSemanticBase(reset=true){
    const input=$('#q');
    if(!input||!semanticAliases||semanticGuard) return;
    semanticGuard=true;
    const preserved=input.value;
    input.value='';
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.value=preserved;
    semanticGuard=false;
    clearTimeout(semanticTimer);
    semanticTimer=setTimeout(()=>applySemanticFilter(reset),0);
  }

  function onQueryInput(event){
    if(semanticGuard) return;
    const input=event.currentTarget;
    const aliases=aliasesFor(input.value);
    if(!aliases){
      semanticAliases=null;
      semanticValue='';
      semanticLimit=batchSize();
      setTimeout(updateNormalSentinel,0);
      return;
    }
    event.stopImmediatePropagation();
    semanticAliases=aliases;
    semanticValue=input.value;
    rerenderSemanticBase(true);
  }

  function installSemanticSearch(){
    const input=$('#q');
    if(!input||input.dataset.semanticSearch==='true') return;
    input.dataset.semanticSearch='true';
    input.addEventListener('input',onQueryInput,true);
    for(const selector of ['#category','#source','#include-deadlines']){
      $(selector)?.addEventListener('change',()=>{
        if(semanticAliases) setTimeout(()=>rerenderSemanticBase(true),0);
      });
    }
    $$('.chip[data-range]').forEach(chip=>chip.addEventListener('click',()=>{
      if(semanticAliases) setTimeout(()=>rerenderSemanticBase(true),0);
    }));
  }

  function installInfiniteScroll(){
    const marker=ensureSentinel();
    if(!marker||infiniteObserver) return;
    infiniteObserver=new IntersectionObserver(entries=>{
      if(!entries.some(entry=>entry.isIntersecting)) return;
      if(semanticAliases) loadSemanticBatch();
      else loadNormalBatch();
    },{root:null,rootMargin:'900px 0px',threshold:0.01});
    infiniteObserver.observe(marker);
    const agenda=$('#agenda');
    if(agenda){
      new MutationObserver(()=>{
        ensureSentinel();
        if(semanticAliases) setTimeout(()=>applySemanticFilter(false),0);
        else setTimeout(updateNormalSentinel,0);
      }).observe(agenda,{childList:true,subtree:true});
    }
    updateNormalSentinel();
  }

  function start(){
    installStyles();
    installSemanticSearch();
    installInfiniteScroll();
  }

  document.readyState==='loading'
    ?document.addEventListener('DOMContentLoaded',start,{once:true})
    :start();
})();
