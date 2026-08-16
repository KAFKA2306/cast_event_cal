from __future__ import annotations

import json
from datetime import UTC, date, datetime

from scripts.search_console_growth import build_report, sensitive_query, write_report


def row(query: str, page: str, clicks: float, impressions: float, ctr: float, position: float) -> dict[str, object]:
    return {
        "keys": [query, page],
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "position": position,
    }


def test_report_compares_equal_windows_and_prioritizes_ctr_gap(tmp_path) -> None:
    config = {
        "site_url": "https://example.test/",
        "brand_terms": ["owned-brand"],
        "window_days": 28,
        "min_impressions": 20,
        "max_candidates": 10,
    }
    changes = {
        "changes": [
            {
                "date": "2026-08-01",
                "page": "https://example.test/events/a/",
                "field": "title",
                "before": "old",
                "after": "new",
                "reference": "PR #1",
            }
        ]
    }
    current = [
        row("vrchat event", "https://example.test/events/a/", 2, 100, 0.02, 5.0),
        row("healthy query", "https://example.test/events/b/", 10, 100, 0.10, 6.0),
        row("owned-brand schedule", "https://example.test/events/c/", 4, 40, 0.10, 2.0),
        row("person@example.com", "https://example.test/events/private/", 0, 50, 0.0, 8.0),
    ]
    previous = [
        row("vrchat event", "https://example.test/events/a/", 1, 80, 0.0125, 5.5),
        row("healthy query", "https://example.test/events/b/", 7, 90, 7 / 90, 6.2),
    ]

    report = build_report(
        config=config,
        changes_doc=changes,
        latest_finalized=date(2026, 8, 14),
        current_total={"clicks": 16, "impressions": 240, "ctr": 16 / 240, "position": 5.0},
        previous_total={"clicks": 8, "impressions": 170, "ctr": 8 / 170, "position": 5.6},
        current_raw=current,
        previous_raw=previous,
        generated_at=datetime(2026, 8, 16, 10, 0, tzinfo=UTC),
    )

    assert report["windows"]["current"] == {"start": "2026-07-18", "end": "2026-08-14", "days": 28}
    assert report["windows"]["previous"] == {"start": "2026-06-20", "end": "2026-07-17", "days": 28}
    assert report["totals"]["delta"]["clicks"] == 8
    assert report["privacy"]["obvious_pii_query_rows_dropped"] == 1
    assert report["generative_ai"]["impressions"] is None
    assert report["changes_in_comparison_window"][0]["reference"] == "PR #1"

    candidate = report["candidates"][0]
    assert candidate["query"] == "vrchat event"
    assert candidate["brand"] is False
    assert candidate["position_band"] == "4-10"
    assert candidate["estimated_missed_clicks_vs_band"] > 0
    assert candidate["delta"]["position"] == -0.5

    brand_row = next(item for item in report["query_page_rows"] if item["query"] == "owned-brand schedule")
    assert brand_row["brand"] is True

    dated, latest = write_report(report, tmp_path)
    assert dated.name == "2026-08-14.json"
    assert json.loads(latest.read_text(encoding="utf-8"))["latest_finalized_date"] == "2026-08-14"


def test_sensitive_query_drops_obvious_contact_identifiers() -> None:
    assert sensitive_query("mail me user@example.com")
    assert sensitive_query("090-1234-5678 event")
    assert not sensitive_query("VRChat 音楽イベント")
