from scripts.render_frontend import patch_frontend


def test_frontend_deduplicates_x_announcement_by_status_id() -> None:
    template = """
    <style></style>
    <script>
    function eventLinks(e){const rows=Array.isArray(e.official_links)?e.official_links:[];const seen=new Set();const valid=[];for(const row of rows){const url=String(row?.url||'');if(!url.startsWith('https://')||seen.has(url))continue;seen.add(url);valid.push({url,label:String(row?.label||'公式リンク'),kind:String(row?.kind||'official')})}if(!valid.length&&String(e.url||'').startsWith('https://'))valid.push({url:e.url,label:'告知・参加方法',kind:'announcement'});return valid.slice(0,3)}
    function detailsHtml(e){return ''}
    const card=`<div class="event-main"><div class="event-top">${detailsHtml(e)}${tags?`<div class="tags">${tags}</div>`:''}</div>`;
    </script>
    """
    rendered = patch_frontend(template)
    assert "x-status:" in rendered
    assert "seenKinds.has('announcement')" in rendered


def test_frontend_prefers_official_vrchat_group_for_image_click() -> None:
    template = """
    <style></style>
    <script>
    function eventLinks(e){const rows=Array.isArray(e.official_links)?e.official_links:[];const seen=new Set();const valid=[];for(const row of rows){const url=String(row?.url||'');if(!url.startsWith('https://')||seen.has(url))continue;seen.add(url);valid.push({url,label:String(row?.label||'公式リンク'),kind:String(row?.kind||'official')})}if(!valid.length&&String(e.url||'').startsWith('https://'))valid.push({url:e.url,label:'告知・参加方法',kind:'announcement'});return valid.slice(0,3)}
    function detailsHtml(e){return ''}
    const card=`<div class="event-main"><div class="event-top">${detailsHtml(e)}${tags?`<div class="tags">${tags}</div>`:''}</div>`;
    </script>
    """
    rendered = patch_frontend(template)
    assert "preferredActionUrl" in rendered
    assert "vrchat_group" in rendered
    assert "https://vrchat.com/home/group/" in rendered
    assert "VRChat Group" in rendered
