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
