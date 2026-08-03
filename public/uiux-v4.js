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
