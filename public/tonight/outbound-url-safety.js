(()=>{'use strict';
function safeOutboundUrl(value){
  if(typeof value!=='string')return null;
  if(/[\u0000-\u001f\u007f]/.test(value))return null;
  const raw=value.trim();
  if(!raw||raw.startsWith('//')||/^[\\/]{2}/.test(raw))return null;
  try{
    const url=new URL(raw);
    if(url.protocol!=='https:'||!url.hostname)return null;
    return url.href;
  }catch{return null;}
}
function sanitizeAnchor(anchor){
  if(!(anchor instanceof HTMLAnchorElement))return;
  const raw=anchor.getAttribute('href');
  if(raw===null)return;
  // A browser may interpret leading whitespace, controls, or backslashes as a scheme/host.
  // Never allow those values to escape the outbound policy's scheme detection.
  if(!raw||raw!==raw.trim()||/[\u0000-\u001f\u007f]/.test(raw)||raw.startsWith('\\')||/^[\\/]{2}/.test(raw)){
    anchor.remove();return;
  }
  // Relative first-party navigation is intentionally outside the outbound policy.
  if(!/^[A-Za-z][A-Za-z0-9+.-]*:/.test(raw))return;
  const safe=safeOutboundUrl(raw);
  if(!safe){anchor.remove();return;}
  anchor.href=safe;
  if(anchor.target==='_blank')anchor.rel='noopener noreferrer';
}
function sanitize(root=document){
  if(root instanceof HTMLAnchorElement)sanitizeAnchor(root);
  if(root.querySelectorAll)root.querySelectorAll('a[href]').forEach(sanitizeAnchor);
}
const list=document.querySelector('#list');
if(list){
  sanitize(list);
  new MutationObserver(records=>records.forEach(record=>record.addedNodes.forEach(node=>{
    if(node.nodeType===Node.ELEMENT_NODE)sanitize(node);
  }))).observe(list,{childList:true,subtree:true});
}
window.TonightOutboundUrlSafety=Object.freeze({safeOutboundUrl,sanitize});
})();
