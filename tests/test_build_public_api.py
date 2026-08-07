from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from scripts.build_public_api import build


def test_build_public_api_outputs_consistent_files(tmp_path: Path) -> None:
    source = tmp_path / "events.json"
    source.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "generated_at": "2026-08-07T12:00:00Z",
                "timezone": "Asia/Tokyo",
                "count": 2,
                "events": [
                    {"id": "b", "title": "B", "starts_at": "2026-08-09T00:00:00Z", "category": "music", "status": "scheduled", "source": "official"},
                    {"id": "a", "title": "A", "starts_at": "2026-08-08T00:00:00Z", "category": "community", "status": "scheduled", "source": "official"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "api" / "v1"
    manifest = build(source, output)
    assert manifest["event_count"] == 2
    assert manifest["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    events = json.loads((output / "events.json").read_text(encoding="utf-8"))
    assert events["count"] == 2
    facets = json.loads((output / "facets.json").read_text(encoding="utf-8"))
    assert facets["facets"]["category"] == {"community": 1, "music": 1}
    with (output / "events.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [row["id"] for row in rows] == ["a", "b"]
    for name, meta in manifest["files"].items():
        path = output / name
        assert meta["bytes"] == path.stat().st_size
        assert meta["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_duplicate_ids_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "events.json"
    source.write_text(json.dumps({"count": 2, "events": [{"id": "x"}, {"id": "x"}]}), encoding="utf-8")
    try:
        build(source, tmp_path / "out")
    except ValueError as exc:
        assert "unique" in str(exc)
    else:
        raise AssertionError("duplicate ids must be rejected")
