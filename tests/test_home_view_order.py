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
    assert 'data-view-order="decision-first-v1"' in html


def test_home_reorder_is_idempotent() -> None:
    html = rendered_home()
    assert reorder_home_view(html) == html
