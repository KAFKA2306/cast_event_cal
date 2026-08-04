from __future__ import annotations

import json

from scripts import build_registration_count_audit as audit


def test_build_appends_snapshot_and_computes_deltas(tmp_path, monkeypatch):
    calendar = tmp_path / "health.json"
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
    monkeypatch.setattr(audit, "YAHOO_HEALTH", yahoo)
    monkeypatch.setattr(audit, "OUTPUT", output)

    payload = audit.build()
    latest = payload["latest"]
    assert latest["delta_from_previous"]["calendar_event_count"] == 10
    assert latest["delta_from_previous"]["yahoo_candidate_count"] == 70
    assert latest["delta_from_previous"]["yahoo_accepted_count"] == 4
    assert latest["delta_from_previous"]["yahoo_rejected_count"] == 66
    assert latest["delta_from_previous"]["source_counts"]["yahoo_realtime_events"] == 4


def test_build_rejects_unhealthy_inputs(tmp_path, monkeypatch):
    calendar = tmp_path / "health.json"
    yahoo = tmp_path / "yahoo.json"
    calendar.write_text(json.dumps({"status": "degraded"}), encoding="utf-8")
    yahoo.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    monkeypatch.setattr(audit, "CALENDAR_HEALTH", calendar)
    monkeypatch.setattr(audit, "YAHOO_HEALTH", yahoo)
    try:
        audit.build()
    except ValueError as exc:
        assert "calendar health" in str(exc)
    else:
        raise AssertionError("unhealthy input must fail closed")
