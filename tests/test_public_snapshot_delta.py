import json
from pathlib import Path

from scripts.build_public_snapshot_delta import append_history, build_delta


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def event(event_id: str, starts_at: str, **extra):
    row = {
        "id": event_id,
        "occurrence_id": event_id,
        "source_record_id": f"src-{event_id}",
        "source_id": f"source-{event_id}",
        "title": event_id,
        "starts_at": starts_at,
        "source": "repository_manual_events",
    }
    row.update(extra)
    return row


def snapshot(path: Path, rows, *, generated_at="2026-09-26T00:00:00Z") -> None:
    write_json(path, {"generated_at": generated_at, "count": len(rows), "events": rows})


def healthy(path: Path, **statuses) -> None:
    defaults = {
        "repository_manual_events": "ok",
        "yahoo_realtime_events": "ok",
        "external_calendar_events": "ok",
    }
    defaults.update(statuses)
    write_json(
        path,
        {"sources": [{"name": name, "status": status} for name, status in defaults.items()]},
    )


def test_added_new_discovery_and_conservation(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    health = tmp_path / "health.json"
    snapshot(before, [event("a", "2026-09-27T00:00:00Z"), event("b", "2026-09-28T00:00:00Z")])
    snapshot(after, [event("b", "2026-09-28T00:00:00Z"), event("a", "2026-09-27T00:00:00Z"), event("c", "2026-09-29T00:00:00Z")])
    healthy(health)

    report = build_delta(before, after, health_path=health, base_sha="abc")

    assert report["counts"] == {"before": 2, "after": 3, "added": 1, "removed": 0, "changed": 0, "unchanged": 2, "net": 1}
    assert report["added"] == [{"occurrence_id": "c", "reason": "new_discovery", "title": "c"}]
    assert report["conservation"]["ok"] is True
    assert report["healthy"] is True
    assert report["base_sha"] == "abc"


def test_recurring_and_datetime_promotion_use_explicit_evidence(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    health = tmp_path / "health.json"
    recurring = tmp_path / "recurring.json"
    previous_history = tmp_path / "history.json"
    snapshot(before, [])
    snapshot(
        after,
        [
            event("r", "2026-09-27T00:00:00Z", source_id="weekly-meet:2026-09-27"),
            event("y", "2026-09-28T00:00:00Z", source="yahoo_realtime_events", source_id="yahoo:x:123"),
        ],
    )
    healthy(health)
    write_json(recurring, [{"series_id": "weekly-meet"}])
    write_json(previous_history, {"candidates": [{"status_id": "123", "last_decision": "rejected", "last_reason": "missing_datetime"}]})

    report = build_delta(
        before,
        after,
        health_path=health,
        recurring_path=recurring,
        previous_yahoo_history_path=previous_history,
    )

    assert report["reason_counts"]["added"] == {
        "promoted_datetime_resolution": 1,
        "recurrence_materialized": 1,
    }


def test_removed_expired_and_dedup_merged_are_distinguished(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    health = tmp_path / "health.json"
    old_dup = event("old-dup", "2026-09-28T00:00:00Z", source_record_id="src-shared")
    expired = event("expired", "2026-09-20T00:00:00Z")
    survivor = event(
        "survivor",
        "2026-09-28T00:00:00Z",
        source_record_id="src-survivor",
        provenance=[{"source_record_id": "src-shared", "source_id": "source-old-dup"}],
    )
    snapshot(before, [old_dup, expired])
    snapshot(after, [survivor], generated_at="2026-09-26T00:00:00Z")
    healthy(health)

    report = build_delta(before, after, health_path=health, past_days=1)
    removed = {row["occurrence_id"]: row for row in report["removed"]}

    assert removed["old-dup"]["reason"] == "dedup_merged"
    assert removed["old-dup"]["canonical_survivor_ids"] == ["survivor"]
    assert removed["expired"]["reason"] == "expired"


def test_presentation_and_material_changes_are_separate(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    health = tmp_path / "health.json"
    snapshot(
        before,
        [
            event("p", "2026-09-27T00:00:00Z", title="old", fetched_at="one"),
            event("m", "2026-09-27T00:00:00Z", title="same"),
            event("v", "2026-09-27T00:00:00Z", fetched_at="one"),
        ],
    )
    snapshot(
        after,
        [
            event("p", "2026-09-27T00:00:00Z", title="new", fetched_at="two"),
            event("m", "2026-09-28T00:00:00Z", title="same"),
            event("v", "2026-09-27T00:00:00Z", fetched_at="two"),
        ],
    )
    healthy(health)

    report = build_delta(before, after, health_path=health)
    changed = {row["occurrence_id"]: row for row in report["changed"]}

    assert changed["p"]["change_kind"] == "presentation"
    assert changed["p"]["presentation_fields"] == ["title"]
    assert changed["m"]["change_kind"] == "material"
    assert changed["m"]["material_fields"] == ["starts_at"]
    assert "v" in report["unchanged_ids"]


def test_degraded_source_removal_never_appends_healthy_history(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    health = tmp_path / "health.json"
    history = tmp_path / "history.jsonl"
    snapshot(before, [event("a", "2026-09-27T00:00:00Z", source="external_calendar_events")])
    snapshot(after, [])
    healthy(health, external_calendar_events="degraded")

    report = build_delta(before, after, health_path=health)

    assert report["status"] == "degraded_source_context"
    assert report["healthy"] is False
    assert report["removed"][0]["reason"] == "unknown"
    assert append_history(report, history) is False
    assert not history.exists()


def test_history_is_deduplicated_and_input_order_does_not_change_semantic_hash(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    after_reordered = tmp_path / "after-reordered.json"
    health = tmp_path / "health.json"
    history = tmp_path / "history.jsonl"
    rows = [event("a", "2026-09-27T00:00:00Z"), event("b", "2026-09-28T00:00:00Z")]
    snapshot(before, rows)
    snapshot(after, rows)
    snapshot(after_reordered, list(reversed(rows)))
    healthy(health)

    first = build_delta(before, after, health_path=health, base_sha="abc")
    second = build_delta(before, after_reordered, health_path=health, base_sha="abc")

    assert first["after_snapshot"]["semantic_sha256"] == second["after_snapshot"]["semantic_sha256"]
    assert first["counts"] == second["counts"]
    assert append_history(first, history) is True
    assert append_history(first, history) is False
    assert len(history.read_text(encoding="utf-8").splitlines()) == 1


def test_degraded_source_without_disappearance_is_still_a_safe_delta(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    health = tmp_path / "health.json"
    history = tmp_path / "history.jsonl"
    rows = [event("a", "2026-09-27T00:00:00Z", source="external_calendar_events")]
    snapshot(before, rows)
    snapshot(after, rows)
    healthy(health, external_calendar_events="skipped")

    report = build_delta(before, after, health_path=health)

    assert report["status"] == "ok_with_degraded_sources"
    assert report["healthy"] is True
    assert append_history(report, history) is True


def test_production_workflow_captures_and_persists_delta_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/update-calendar-v2.yml").read_text(
        encoding="utf-8"
    )

    capture = workflow.index("Capture previous canonical snapshot")
    materialize = workflow.index("Materialize curated recurring events")
    validate = workflow.index("Validate generated data and collection health")
    delta = workflow.index("Explain canonical public snapshot delta")
    commit = workflow.index("Commit generated data safely")

    assert capture < materialize < validate < delta < commit
    assert "cp public/events.json /tmp/public-events-before.json" in workflow
    assert (
        "cp public/yahoo-candidate-history.json "
        "/tmp/yahoo-candidate-history-before.json"
    ) in workflow
    assert "--before /tmp/public-events-before.json" in workflow
    assert (
        "--previous-yahoo-history "
        "/tmp/yahoo-candidate-history-before.json"
    ) in workflow
    assert "uses: actions/upload-artifact@v7" in workflow
    assert "path: audit/public-snapshot-delta.json" in workflow
    assert "audit/public-snapshot-delta-history.jsonl" in workflow
