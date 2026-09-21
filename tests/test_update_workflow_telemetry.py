from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(".github/workflows/update-calendar-v2.yml")

EXPECTED_STAGES = {
    "install_dependencies": "setup",
    "regression_tests": "validation",
    "materialize_curated_events": "projection",
    "collect_vrchat_calendar": "network",
    "collect_x_events": "network",
    "collect_yahoo_corpus": "network",
    "refine_yahoo_corpus": "projection",
    "apply_yahoo_archive_policy": "projection",
    "collect_external_calendars": "network",
    "gate_collection_health": "validation",
    "build_normalized_calendar": "projection",
    "enrich_official_assets": "network",
    "discover_event_links": "network",
    "enrich_vrchat_group_assets": "network",
    "deduplicate_occurrences": "projection",
    "render_frontend": "projection",
    "build_promotions": "projection",
    "reorder_home_view": "projection",
    "render_distribution_assets": "projection",
    "build_registration_count_audit": "projection",
    "audit_public_feed": "validation",
    "validate_update_snapshot": "validation",
    "write_snapshot_identity": "projection",
    "verify_snapshot_identity": "validation",
}


def test_update_workflow_instruments_every_declared_stage() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    found = dict(re.findall(r"--name ([a-z0-9_]+) --kind ([a-z]+)", text))
    assert found == EXPECTED_STAGES
    assert text.count('python scripts/run_stage.py --report "$UPDATE_STAGE_TELEMETRY"') == len(EXPECTED_STAGES)


def test_update_workflow_keeps_final_truth_gates_before_commit() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    validate = text.index("--name validate_update_snapshot")
    verify = text.index("--name verify_snapshot_identity")
    summary = text.index("Summarize update telemetry")
    commit = text.index("Commit generated data safely")
    assert validate < verify < summary < commit


def test_measurement_pr_does_not_add_stage_reuse_or_skip_switches() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "--reuse" not in text
    assert "--skip-stage" not in text
    assert "UPDATE_STAGE_TELEMETRY" in text
