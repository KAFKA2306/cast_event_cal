from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_quality_view_uses_infinite_scroll_instead_of_manual_paging() -> None:
    script = (ROOT / "public" / "uiux-v4.js").read_text(encoding="utf-8")
    assert "IntersectionObserver" in script
    assert "ux-infinite-sentinel" in script
    assert "rootMargin:'900px 0px'" in script
    assert "button.click()" in script
    assert ".ux-load-more{display:none!important}" in script


def test_cast_search_expands_to_japanese_service_event_terms() -> None:
    script = (ROOT / "public" / "uiux-v4.js").read_text(encoding="utf-8")
    for term in (
        "cast_service",
        "キャスト",
        "接客",
        "1対1",
        "個室",
        "メイド",
        "執事",
        "ゲスト募集",
        "キャスト募集",
    ):
        assert term in script
    assert "event.stopImmediatePropagation()" in script
    assert "applySemanticFilter" in script
