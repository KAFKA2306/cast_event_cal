from __future__ import annotations

import json

import pytest

from scripts import publication_guard
from scripts.write_snapshot_identity import build_snapshot_identity

SOURCE = "a" * 40
ADVANCED = "b" * 40


def write_inputs(tmp_path, *, source=SOURCE, snapshot_source=SOURCE):
    record = tmp_path / "validated-source.json"
    snapshot = tmp_path / "snapshot.json"
    record.write_text(
        json.dumps({"schema_version": 1, "validated_base_sha": source}), encoding="utf-8"
    )
    snapshot.write_text(json.dumps({"source_revision": snapshot_source}), encoding="utf-8")
    return record, snapshot


def test_publication_accepts_exact_source_and_remote(tmp_path, monkeypatch):
    record, snapshot = write_inputs(tmp_path)
    monkeypatch.setattr(
        publication_guard,
        "git",
        lambda *args: SOURCE if args == ("rev-parse", "HEAD")
        else f"{SOURCE}\trefs/heads/main",
    )
    assert publication_guard.check_base(record, snapshot) == SOURCE


def test_publication_rejects_remote_advance(tmp_path, monkeypatch):
    record, snapshot = write_inputs(tmp_path)
    monkeypatch.setattr(
        publication_guard,
        "git",
        lambda *args: SOURCE if args == ("rev-parse", "HEAD")
        else f"{ADVANCED}\trefs/heads/main",
    )
    with pytest.raises(RuntimeError, match="base_changed_after_validation"):
        publication_guard.check_base(record, snapshot)


def test_publication_rejects_different_checkout(tmp_path, monkeypatch):
    record, snapshot = write_inputs(tmp_path)
    monkeypatch.setattr(publication_guard, "git", lambda *args: ADVANCED)
    with pytest.raises(RuntimeError, match="base_changed_after_validation"):
        publication_guard.check_base(record, snapshot)


def test_publication_rejects_missing_or_invalid_evidence(tmp_path, monkeypatch):
    record, snapshot = write_inputs(tmp_path, snapshot_source=ADVANCED)
    monkeypatch.setattr(publication_guard, "git", lambda *args: SOURCE)
    with pytest.raises(RuntimeError, match="source_revision_mismatch"):
        publication_guard.check_base(record, snapshot)
    record.unlink()
    with pytest.raises(FileNotFoundError):
        publication_guard.check_base(record, snapshot)


def test_snapshot_identity_carries_exact_source_revision(tmp_path):
    events = tmp_path / "events.json"
    events.write_text(
        json.dumps({
            "generated_at": "2026-10-24T00:00:00Z",
            "count": 1,
            "events": [{"id": "e1", "starts_at": "2026-10-24T01:00:00Z"}],
        }),
        encoding="utf-8",
    )
    assert build_snapshot_identity(events, SOURCE)["source_revision"] == SOURCE
