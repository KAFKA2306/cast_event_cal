from pathlib import Path


TONIGHT_JS = Path("public/tonight/tonight.js")


def test_tonight_uses_stable_identity_as_equal_time_tiebreaker():
    source = TONIGHT_JS.read_text(encoding="utf-8")

    assert "function compareEvents(a,b)" in source
    assert "if(ta!==tb)return ta-tb" in source
    assert "return id(a).localeCompare(id(b),'en',{numeric:true,sensitivity:'variant'})" in source
    assert ".sort(compareEvents)" in source


def test_tonight_identity_reuses_existing_canonical_fallback_chain():
    source = TONIGHT_JS.read_text(encoding="utf-8")

    assert "const id=e=>text(e,'id','event_id','slug','source_url')||title(e)" in source
    assert "const PAGE=30" in source
    assert "visible=list.slice(0,state.limit)" in source
