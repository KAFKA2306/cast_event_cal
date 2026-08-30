from __future__ import annotations

from pathlib import Path

OUTPUT = Path("public/index.html")
VIEW_ORDER_MARKER = 'data-view-order="decision-first-v1"'


def _replace_once(html: str, old: str, new: str, error: str) -> str:
    if old not in html:
        raise ValueError(error)
    return html.replace(old, new, 1)


def reorder_home_view(html: str) -> str:
    """Move decision-making UI ahead of operational summary information."""
    if VIEW_ORDER_MARKER in html:
        return html

    html = _replace_once(
        html,
        '<main class="shell">',
        f'<main class="shell" {VIEW_ORDER_MARKER}>',
        "home shell marker missing",
    )
    html = _replace_once(
        html,
        '<a class="button primary" href="#agenda">今週のイベントを見る</a>',
        '<a class="button primary" href="tonight/">今夜のイベントを見る</a>',
        "primary home action marker missing",
    )
    html = _replace_once(
        html,
        '<section class="controls" aria-label="イベント絞り込み">',
        '<section id="event-filters" class="controls" aria-label="イベント絞り込み">',
        "home filter marker missing",
    )

    summary_start = html.find('<section class="summary" aria-label="集計">')
    if summary_start < 0:
        raise ValueError("home summary marker missing")
    summary_end = html.find("</section>", summary_start)
    if summary_end < 0:
        raise ValueError("home summary closing marker missing")
    summary_end += len("</section>")
    summary = html[summary_start:summary_end].replace('aria-label="集計"', 'aria-label="全体集計"', 1)
    html = html[:summary_start] + html[summary_end:]

    footer_start = html.find("<footer>")
    if footer_start < 0:
        raise ValueError("home footer marker missing")
    html = html[:footer_start] + summary + "\n" + html[footer_start:]

    ordered_markers = (
        '<section class="hero">',
        '<section id="event-filters" class="controls"',
        '<section id="recommendations"',
        '<div class="statusbar">',
        '<div id="agenda"',
        '<section class="summary" aria-label="全体集計">',
        "<footer>",
    )
    positions = [html.find(marker) for marker in ordered_markers]
    if any(position < 0 for position in positions):
        raise ValueError(f"home view marker missing after reorder: {positions}")
    if positions != sorted(positions):
        raise ValueError(f"home view order invalid: {positions}")
    return html


def main() -> int:
    html = OUTPUT.read_text(encoding="utf-8")
    reordered = reorder_home_view(html)
    OUTPUT.write_text(reordered, encoding="utf-8")
    print("reordered public/index.html by user decision value")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
