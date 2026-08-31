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
    assert 'data-card-order="decision-first-v1"' in html


def test_event_card_puts_participation_and_primary_action_before_media_and_evidence() -> None:
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
        'class="provenance"',
        "${secondaryActionsHtml(event)}",
        "${assetProofHtml(event)}",
        '<div class="tags">',
    ]
    positions = [card.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_participation_method_is_elevated_not_duplicated_in_detail_grid() -> None:
    html = rendered_home()
    participation_start = html.index("function participationHtml(event){")
    details_start = html.index("function detailsHtml(event){")
    event_start = html.index("function eventHtml(event){")
    participation = html[participation_start:details_start]
    details = html[details_start:event_start]

    assert "event.participation_method" in participation
    assert "参加方法" in participation
    assert "event.participation_method" not in details
    assert "['参加方法'" not in details


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
