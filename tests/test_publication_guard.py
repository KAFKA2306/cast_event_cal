from __future__ import annotations

import json

import pytest

from scripts.publication_guard import REASON_BASE_CHANGED, assert_same_base, load_validated_base
from scripts.write_snapshot_identity import build_snapshot_identity


def test_publication_guard_accepts_exact_validated_base(tmp_path):
    record = tmp_path / "validated-base.json"
    record.write_text(json.dumps({"validated_base_sha": "abc123"}), encoding="utf-8")

    validated = load_validated_base(record)
    assert_same_base(validated, "abc123")


def test_publication_guard_rejects_concurrent_main_advancement(tmp_path):
    record = tmp_path / "validated-base.json"
    record.write_text(json.dumps({"validated_base_sha": "abc123"}), encoding="utf-8")

    with pytest.raises(RuntimeError, match=REASON_BASE_CHANGED):
        assert_same_base(load_validated_base(record), "def456")


def test_snapshot_identity_audits_source_revision(tmp_path):
    events = tmp_path / "events.json"
    events.write_text(
        json.dumps({"count": 1, "events": [{"id": "event-1", "starts_at": "2026-09-27T12:00:00+09:00"}]}),
        encoding="utf-8",
    )

    identity = build_snapshot_identity(events, "abc123")

    assert identity["source_revision"] == "abc123"
