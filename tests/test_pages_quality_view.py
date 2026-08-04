import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_function_injects_only_first_party_assets() -> None:
    source = (ROOT / "functions" / "index.js").read_text(encoding="utf-8")
    assert "context.next()" in source
    assert "HTMLRewriter" in source
    assert "x-quality-view" in source
    assert "2026-08-04-quality-view-v6" in source
    assert 'href="/uiux-v4.css"' in source
    assert 'src="/uiux-v4.js"' in source
    assert 'src="/series-profile.js"' in source
    assert "https://" not in source


def test_function_invocation_is_limited_to_root() -> None:
    routes = json.loads((ROOT / "public" / "_routes.json").read_text(encoding="utf-8"))
    assert routes == {"version": 1, "include": ["/"], "exclude": []}


def test_quality_view_has_accessibility_mobile_and_density_contracts() -> None:
    css = (ROOT / "public" / "uiux-v4.css").read_text(encoding="utf-8")
    script = (ROOT / "public" / "uiux-v4.js").read_text(encoding="utf-8")
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css
    assert ".ux-mobile-nav{display:none!important}" in css
    assert ".ux-filter-toggle" in css
    assert ".ux-load-more" in css
    assert "MutationObserver" in script
    assert "localStorage" in script
    assert "イベント一覧へ移動" in script
    assert "selectRange('today',false)" in script
    assert "applyPagination" in script
    assert "ux-filters-open" in script
    assert "fetch(" not in script


def test_series_profile_ui_uses_enriched_state_without_network_fetch() -> None:
    script = (ROOT / "public" / "series-profile.js").read_text(encoding="utf-8")
    assert "series_profile" in script
    assert "CURATED SERIES PROFILE" in script
    assert "初参加ガイド" in script
    assert "人手で確認したオントロジー" in script
    assert "MutationObserver" in script
    assert "typeof state!=='undefined'" in script
    assert "fetch(" not in script
