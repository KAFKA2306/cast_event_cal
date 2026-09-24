from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "public" / "tonight" / "index.html"
JS = ROOT / "public" / "tonight" / "tonight.js"


def test_tonight_dynamic_status_contract() -> None:
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")

    assert 'id="announcement"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-atomic="true"' in html
    assert 'id="error" class="state error" role="alert"' in html
    assert 'id="list" class="event-list" aria-busy="true"' in html

    assert "setTimeout(publish,300)" in js
    assert "条件に一致するイベントは0件です。" in js
    assert "条件一致 ${list.length}件です。" in js
    assert "render({focus:true})" not in js
    assert "$('#events').focus()" not in js
    assert "catch(error){clearTimeout(announceTimer);$('#loading').hidden=true;$('#list').setAttribute('aria-busy','false')" in js
