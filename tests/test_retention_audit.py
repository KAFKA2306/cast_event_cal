from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_retention import classify, inventory, load_policy


def test_policy_covers_required_lifecycle_classes() -> None:
    policy = load_policy()
    classes = {rule["class"] for rule in policy["rules"]}
    assert {
        "canonical_provenance",
        "raw_source_text",
        "accepted_canonical_facts",
        "rejected_candidate_evidence",
        "unresolved_evidence",
        "generated_public_projection",
        "operator_audit_replay",
        "ci_actions_artifact",
        "interaction_analytics",
    } <= classes


def test_unknown_path_fails_closed_without_deletion_eligibility() -> None:
    policy = load_policy()
    row = classify("mystery/private-copy.json", policy)
    assert row == {"path": "mystery/private-copy.json", "state": "UNCLASSIFIED"}
    assert "eligibility" not in row


def test_generated_projection_is_not_canonical_retention_authority() -> None:
    policy = load_policy()
    row = classify("public/events.json", policy)
    assert row["state"] == "CLASSIFIED"
    assert row["class"] == "generated_public_projection"
    assert row["eligibility"] == "replaceable_projection"


def test_inventory_is_read_only_and_reports_unclassified(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "manual_events.json").write_text("[]", encoding="utf-8")
    (tmp_path / "data" / "unknown.bin").write_text("x", encoding="utf-8")
    policy = {
        "schema_version": "1.0",
        "default_state": "UNCLASSIFIED",
        "rules": [{
            "class": "accepted_canonical_facts",
            "patterns": ["data/manual_events.json"],
            "purpose": "facts",
            "authority": "canonical",
            "sensitivity": "public_facts",
            "minimum_required_fields": ["identity"],
            "retention_basis": "reproducibility",
            "eligibility": "retain"
        }]
    }
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    report = inventory(tmp_path, policy_path)
    assert report["mode"] == "read_only"
    assert report["unclassified"] == ["data/unknown.bin"]
    assert (tmp_path / "data" / "unknown.bin").exists()
