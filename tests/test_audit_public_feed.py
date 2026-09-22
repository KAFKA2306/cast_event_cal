from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_public_feed import audit


def _write(tmp_path: Path, payload: object) -> Path:
    path = tmp_path / "events.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_feed_has_no_errors(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "id": "event-1",
                "title": "Event One",
                "start": "2026-08-06T20:00:00+09:00",
                "url": "https://example.com/event-1",
                "primary_action_url": "https://example.com/join",
                "official_links": [{"url": "https://example.com/official"}],
                "proof_links": ["https://example.com/proof"],
            }
        ],
    )
    report = audit(path)
    assert report["event_count"] == 1
    assert report["unique_identity_count"] == 1
    assert report["error_count"] == 0
    assert len(report["sha256"]) == 64


def test_duplicate_identity_is_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {"id": "same", "title": "A"},
            {"id": "same", "title": "B"},
        ],
    )
    report = audit(path)
    assert any(error["code"] == "duplicate_identity" for error in report["errors"])


def test_missing_identity_and_bad_fields_are_reported(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [{"title": "", "start": "not-a-date", "url": "relative/path"}],
    )
    codes = {error["code"] for error in audit(path)["errors"]}
    assert {"missing_identity", "missing_title", "invalid_datetime", "invalid_url"} <= codes


def test_all_public_navigation_links_fail_closed_on_unsafe_schemes(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [
            {
                "id": "unsafe-links",
                "title": "Unsafe links",
                "primary_action_url": "javascript:alert(1)",
                "join_url": "http://example.com/join",
                "official_links": [{"url": "data:text/html,bad"}],
                "proof_links": ["//example.com/proof"],
                "evidence_links": [{"url": "/relative"}],
            }
        ],
    )
    fields = {error.get("field") for error in audit(path)["errors"] if error["code"] == "invalid_url"}
    assert fields == {
        "primary_action_url",
        "join_url",
        "official_links[0]",
        "proof_links[0]",
        "evidence_links[0]",
    }
