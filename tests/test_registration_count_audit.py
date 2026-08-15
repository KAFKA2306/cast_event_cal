from __future__ import annotations

import json

from scripts import build_registration_count_audit as audit


def write_events(path, *, generated_at: str, count: int) -> None:
    path.write_text(
        json.dumps(
            {
                "generated_at": generated_at,
                "count": count,
                "events": [{"id": f"event-{index}"} for index in range(count)],
            }
        ),
        encoding="utf-8",
    )


def test_build_appends_snapshot_and_computes_deltas(tmp_path, monkeypatch):
    calendar = tmp_path / "health.json"
    events = tmp_path / "events.json"
    yahoo = tmp_path / "yahoo.json"
    output = tmp_path / "audit.json"
    calendar.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-05T00:00:00Z",
                "status": "ok",
                "event_count": 610,
                "sources": [
                    {"name": "repository_manual_events", "count": 499},
                    {"name": "yahoo_realtime_events", "count": 470},
                ],
            }
        ),
        encoding="utf-8",
    )
    write_events(events, generated_at="2026-08-05T00:00:00Z", count=610)
    yahoo.write_text(
        json.dumps(
            {
                "status": "ok",
                "history_candidate_count": 3000,
                "history_accepted_count": 470,
                "history_rejected_count": 2530,
                "unique_candidates_this_run": 70,
                "queries_succeeded": 22,
                "queries_failed": 0,
            }
        ),
        encoding="utf-8",
    )
    output.write_text(
        json.dumps(
            {
                "snapshots": [
                    {
                        "generated_at": "2026-08-04T00:00:00Z",
                        "calendar_event_count": 600,
                        "source_counts": {
                            "repository_manual_events": 499,
                            "yahoo_realtime_events": 466,
                        },
                        "yahoo_candidate_count": 2930,
                        "yahoo_accepted_count": 466,
                        "yahoo_rejected_count": 2464,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(audit, "CALENDAR_HEALTH", calendar)
    monkeypatch.setattr(audit, "EVENTS", events)
    monkeypatch.setattr(audit, "YAHOO_HEALTH", yahoo)
    monkeypatch.setattr(audit, "OUTPUT", output)

    payload = audit.build()
    latest = payload["latest"]
    assert latest["calendar_event_count"] == 610
    assert latest["normalized_event_count"] == 610
    assert latest["delta_from_previous"]["calendar_event_count"] == 10
    assert latest["delta_from_previous"]["yahoo_candidate_count"] == 70
    assert latest["delta_from_previous"]["yahoo_accepted_count"] == 4
    assert latest["delta_from_previous"]["yahoo_rejected_count"] == 66
    assert latest["delta_from_previous"]["source_counts"]["yahoo_realtime_events"] == 4


def test_build_uses_post_dedup_public_count(tmp_path, monkeypatch):
    calendar = tmp_path / "health.json"
    events = tmp_path / "events.json"
    yahoo = tmp_path / "yahoo.json"
    output = tmp_path / "audit.json"
    calendar.write_text(
        json.dumps(
            {
                "generated_at": "2026-08-15T11:10:49Z",
                "status": "ok",
                "event_count": 628,
                "sources": [{"name": "yahoo_realtime_events", "count": 706}],
            }
        ),
        encoding="utf-8",
    )
    write_events(events, generated_at="2026-08-15T11:10:49Z", count=623)
    yahoo.write_text(
        json.dumps(
            {
                "status": "ok",
                "history_candidate_count": 4482,
                "history_accepted_count": 706,
                "history_rejected_count": 3776,
                "queries_succeeded": 22,
                "queries_failed": 0,
            }
        ),
        encoding="utf-8",
    )
    output.write_text(json.dumps({"snapshots": []}), encoding="utf-8")
    monkeypatch.setattr(audit, "CALENDAR_HEALTH", calendar)
    monkeypatch.setattr(audit, "EVENTS", events)
    monkeypatch.setattr(audit, "YAHOO_HEALTH", yahoo)
    monkeypatch.setattr(audit, "OUTPUT", output)

    latest = audit.build()["latest"]

    assert latest["calendar_event_count"] == 623
    assert latest["normalized_event_count"] == 628


def test_synchronize_public_health_preserves_pre_dedup_count():
    events = {
        "count": 623,
        "events": [{"id": str(index)} for index in range(623)],
        "occurrence_dedup": {"policy_version": "canonical-occurrence.v1"},
    }
    health = {"status": "ok", "event_count": 628}

    first = audit.synchronize_public_health(health, events)
    second = audit.synchronize_public_health(first, events)

    assert first["event_count"] == 623
    assert first["normalized_event_count"] == 628
    assert first["occurrence_dedup_policy"] == "canonical-occurrence.v1"
    assert second["event_count"] == 623
    assert second["normalized_event_count"] == 628


def test_append_kpi_log_keeps_only_cumulative_accepted_event_kpi(tmp_path):
    path = tmp_path / "accepted-event-kpi.jsonl"

    first = audit.append_kpi_log(
        {"generated_at": "2026-08-15T00:00:00Z", "yahoo_accepted_count": 701},
        path,
    )
    second = audit.append_kpi_log(
        {"generated_at": "2026-08-16T00:00:00Z", "yahoo_accepted_count": 708},
        path,
    )

    assert first == {
        "generated_at": "2026-08-15T00:00:00Z",
        "accepted_event_cumulative": 701,
        "delta": None,
    }
    assert second == {
        "generated_at": "2026-08-16T00:00:00Z",
        "accepted_event_cumulative": 708,
        "delta": 7,
    }
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows == [first, second]
    assert set(rows[-1]) == {"generated_at", "accepted_event_cumulative", "delta"}


def test_append_kpi_log_is_idempotent_for_same_snapshot(tmp_path):
    path = tmp_path / "accepted-event-kpi.jsonl"
    latest = {"generated_at": "2026-08-15T00:00:00Z", "yahoo_accepted_count": 701}

    audit.append_kpi_log(latest, path)
    audit.append_kpi_log(latest, path)

    assert len(path.read_text(encoding="utf-8").splitlines()) == 1


def test_append_kpi_log_rejects_cumulative_decrease(tmp_path):
    path = tmp_path / "accepted-event-kpi.jsonl"
    audit.append_kpi_log(
        {"generated_at": "2026-08-15T00:00:00Z", "yahoo_accepted_count": 701},
        path,
    )

    try:
        audit.append_kpi_log(
            {"generated_at": "2026-08-16T00:00:00Z", "yahoo_accepted_count": 700},
            path,
        )
    except ValueError as exc:
        assert "must not decrease" in str(exc)
    else:
        raise AssertionError("cumulative KPI decrease must fail closed")


def test_build_rejects_unhealthy_inputs(tmp_path, monkeypatch):
    calendar = tmp_path / "health.json"
    events = tmp_path / "events.json"
    yahoo = tmp_path / "yahoo.json"
    calendar.write_text(json.dumps({"status": "degraded"}), encoding="utf-8")
    write_events(events, generated_at="2026-08-15T00:00:00Z", count=1)
    yahoo.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    monkeypatch.setattr(audit, "CALENDAR_HEALTH", calendar)
    monkeypatch.setattr(audit, "EVENTS", events)
    monkeypatch.setattr(audit, "YAHOO_HEALTH", yahoo)
    try:
        audit.build()
    except ValueError as exc:
        assert "calendar health" in str(exc)
    else:
        raise AssertionError("unhealthy input must fail closed")
