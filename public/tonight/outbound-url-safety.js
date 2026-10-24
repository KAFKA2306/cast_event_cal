(()=>{'use strict';
function safeOutboundUrl(value){
  if(typeof value!=='string'||/[\u0000-\u001f\u007f]/.test(value))return null;
  const raw=value.trim();
  if(!raw||raw.startsWith('//')||raw.includes('\\'))return null;
  try{
    const url=new URL(raw);
    if(url.protocol!=='https:'||!url.hostname||url.username||url.password)return null;
    return url.href;
  }catch{return null;}
}
function sanitizeAnchor(anchor){
  if(!(anchor instanceof HTMLAnchorElement))return true;
  const raw=anchor.getAttribute('href');
  if(raw===null)return true;
  if(!raw||raw!==raw.trim()||/[\u0000-\u001f\u007f]/.test(raw)||raw.includes('\\')||raw.startsWith('//')){
    anchor.remove();return false;
  }
  // Relative first-party navigation is allowed; all absolute links require HTTPS.
  if(!/^[A-Za-z][A-Za-z0-9+.-]*:/.test(raw))return true;
  const safe=safeOutboundUrl(raw);
  if(!safe){anchor.remove();return false;}
  // Avoid an endless attribute MutationObserver loop.
  if(raw!==safe)anchor.setAttribute('href',safe);
  if(anchor.target==='_blank')anchor.rel='noopener noreferrer';
  return true;
}
function sanitize(root=document){
  if(root instanceof HTMLAnchorElement)sanitizeAnchor(root);
  if(root.querySelectorAll)root.querySelectorAll('a[href]').forEach(sanitizeAnchor);
}
const list=document.querySelector('#list');
if(list){
  sanitize(list);
  new MutationObserver(records=>records.forEach(record=>{
    if(record.type==='attributes')sanitizeAnchor(record.target);
    for(const node of record.addedNodes){
      if(node.nodeType===Node.ELEMENT_NODE)sanitize(node);
    }
  })).observe(list,{childList:true,subtree:true,attributes:true,attributeFilter:['href']});
  // MutationObserver runs asynchronously; a click must be checked synchronously.
  list.addEventListener('click',event=>{
    const target=event.target;
    const anchor=target?.closest?.('a[href]')||target?.parentElement?.closest?.('a[href]');
    if(anchor&&!sanitizeAnchor(anchor))event.preventDefault();
  },true);
}
window.TonightOutboundUrlSafety=Object.freeze({safeOutboundUrl,sanitize});
})();
