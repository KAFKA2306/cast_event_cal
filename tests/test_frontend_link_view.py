from pathlib import Path

from scripts.render_frontend import patch_frontend


TEMPLATE = Path("web/index.template.html")


def rendered_frontend() -> str:
    return patch_frontend(TEMPLATE.read_text(encoding="utf-8"))


def test_frontend_deduplicates_x_announcement_by_status_id() -> None:
    rendered = rendered_frontend()
    assert "x-status:" in rendered
    assert "seenKinds.has('announcement')" in rendered


def test_frontend_prefers_official_vrchat_group_for_image_click() -> None:
    rendered = rendered_frontend()
    assert "preferredActionUrl" in rendered
    assert "vrchat_group" in rendered
    assert "https://vrchat.com/home/group/" in rendered
    assert "VRChat Group" in rendered


def test_frontend_uses_only_local_browser_history_for_recommendations() -> None:
    rendered = rendered_frontend()
    assert 'id="recommendations"' in rendered
    assert "kafka2306-vrc-event-click-history-v2" in rendered
    assert "localStorage.getItem" in rendered
    assert "localStorage.setItem" in rendered
    assert "HISTORY_LIMIT=120" in rendered
    assert "HISTORY_MAX_AGE_DAYS=180" in rendered
    assert "RECOMMENDATION_LIMIT=6" in rendered
    assert "HALF_LIFE_DAYS=28" in rendered
    assert "MMR_RELEVANCE=0.82" in rendered
    assert "data-event-history-id" in rendered
    assert "端末内で計算 · 外部送信なし" in rendered


def test_frontend_preserves_ontology_features_and_explanations() -> None:
    rendered = rendered_frontend()
    assert "categoryKey(e.category)" in rendered
    assert "categoryLabel(e)" in rendered
    assert "e.category_detail" in rendered
    assert "e.event_mode" in rendered
    assert "e.organizer" in rendered
    assert "e.event_format" in rendered
    assert "e.audience" in rendered
    assert "weekdayLabel" in rendered
    assert "timeBand" in rendered
    assert "matchedReasons" in rendered
    assert "閲覧傾向" in rendered
    assert "renderAgenda();renderRecommendations()" in rendered
