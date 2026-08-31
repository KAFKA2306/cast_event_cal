from pathlib import Path

from scripts.render_frontend import patch_frontend
from scripts.reorder_home_view import reorder_home_view


TEMPLATE = Path("web/index.template.html")


def rendered_home() -> str:
    return reorder_home_view(patch_frontend(TEMPLATE.read_text(encoding="utf-8")))


def test_home_prioritizes_decision_ui_before_operational_summary() -> None:
    html = rendered_home()
    markers = [
        '<section class="hero">',
        '<section id="event-filters" class="controls"',
        '<section id="recommendations"',
        '<div class="statusbar">',
        '<div id="agenda"',
        '<section class="summary" aria-label="全体集計">',
        "<footer>",
    ]
    positions = [html.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_home_primary_action_is_tonight_and_subscription_remains_available() -> None:
    html = rendered_home()
    assert '<a class="button primary" href="tonight/">今夜のイベントを見る</a>' in html
    assert '<a class="button" href="calendar.ics">カレンダーを購読</a>' in html
    assert 'data-view-order="decision-first-v2"' in html
    assert 'data-card-order="decision-first-v2"' in html


def test_event_card_keeps_decision_information_above_optional_evidence() -> None:
    html = rendered_home()
    start = html.index("function eventHtml(event){")
    end = html.index("function renderAgenda(){", start)
    card = html[start:end]

    markers = [
        '<div class="time">',
        "<h2>",
        '<div class="event-top">',
        "${participationHtml(event)}${primaryActionHtml(event)}",
        'class="meta decision-meta"',
        "${mediaHtml(event)}",
        'class="description"',
        "${detailsHtml(event)}",
        '<div class="tags">',
        "${evidenceHtml(event)}",
    ]
    positions = [card.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_operational_classification_metadata_is_not_always_visible() -> None:
    html = rendered_home()
    event_start = html.index("function eventHtml(event){")
    event_end = html.index("function renderAgenda(){", event_start)
    event_card = html[event_start:event_end]

    assert "辞書照合済み" not in event_card
    assert "分類信頼度" not in event_card
    assert "分類根拠" not in event_card
    assert "event.ontology_id" not in event_card
    assert "event.category_confidence" not in event_card


def test_participation_and_classification_evidence_are_not_duplicated_in_details() -> None:
    html = rendered_home()
    details_start = html.index("function detailsHtml(event){")
    classification_start = html.index("function classificationEvidenceHtml(event){")
    details = html[details_start:classification_start]

    assert "event.participation_method" not in details
    assert "['参加方法'" not in details
    assert "event.category_evidence" not in details
    assert "分類根拠" not in details
    assert "開催形式" in details
    assert "対象" in details


def test_evidence_disclosure_preserves_provenance_and_classification_audit() -> None:
    html = rendered_home()
    classification_start = html.index("function classificationEvidenceHtml(event){")
    event_start = html.index("function eventHtml(event){")
    evidence = html[classification_start:event_start]

    assert "event.category_evidence" in evidence
    assert "event.category_confidence" in evidence
    assert "event.ontology_id" in evidence
    assert "分類信頼度" in evidence
    assert "分類根拠" in evidence
    assert "出典・確認情報" in evidence
    assert "event.source" in evidence
    assert "secondaryActionsHtml(event)" in evidence
    assert "assetProofHtml(event)" in evidence
    assert '<details class="event-evidence">' in evidence


def test_visible_event_tags_are_capped_at_three() -> None:
    html = rendered_home()
    event_start = html.index("function eventHtml(event){")
    event_end = html.index("function renderAgenda(){", event_start)
    event_card = html[event_start:event_end]
    assert "(event.tags||[]).slice(0,3)" in event_card


def test_recommendation_card_shows_action_before_tags() -> None:
    html = rendered_home()
    start = html.index("function recommendationHtml(row){")
    end = html.index("function renderHistorySummary(){", start)
    card = html[start:end]

    assert card.index("<h3>") < card.index('<div class="event-top">')
    assert card.index("recommendation-reason") < card.index("event-link primary")
    assert card.index("event-link primary") < card.index('<div class="tags">')


def test_home_reorder_is_idempotent() -> None:
    html = rendered_home()
    assert reorder_home_view(html) == html
