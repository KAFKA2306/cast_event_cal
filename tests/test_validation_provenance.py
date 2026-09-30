from __future__ import annotations

import pytest

from scripts.build_validation_provenance import build_record


def test_success_is_bound_to_exact_commit_and_all_jobs() -> None:
    record = build_record(
        commit_sha="abc123",
        run={"id": 7, "run_attempt": 2, "head_sha": "abc123"},
        jobs=[{"name": "test (3.12)", "conclusion": "success"}, {"name": "audit", "conclusion": "success"}],
        validated_at="2026-09-30T12:00:00Z",
    )
    assert record["commit_sha"] == "abc123"
    assert record["run_attempt"] == 2
    assert record["result"] == "success"


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "skipped", None])
def test_non_success_required_job_fails_closed(conclusion: str | None) -> None:
    record = build_record(
        commit_sha="abc123",
        run={"id": 8, "run_attempt": 1, "head_sha": "abc123"},
        jobs=[{"name": "required", "conclusion": conclusion}],
        validated_at="2026-09-30T12:00:00Z",
    )
    assert record["result"] == "failure"


def test_empty_job_set_is_unknown() -> None:
    record = build_record(
        commit_sha="abc123",
        run={"id": 9, "run_attempt": 1, "head_sha": "abc123"},
        jobs=[],
        validated_at="2026-09-30T12:00:00Z",
    )
    assert record["result"] == "unknown"


def test_different_sha_is_never_relabelled_as_validated() -> None:
    with pytest.raises(ValueError, match="requested commit SHA"):
        build_record(
            commit_sha="mainsha",
            run={"id": 10, "run_attempt": 1, "head_sha": "prsha"},
            jobs=[{"name": "required", "conclusion": "success"}],
            validated_at="2026-09-30T12:00:00Z",
        )
