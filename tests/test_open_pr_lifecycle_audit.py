from scripts.audit_open_pr_lifecycle import classify, exact_head_ci, referenced_issues, supersession


def test_issue_and_supersession_evidence_is_explicit() -> None:
    body = "Fixes #153\nSupersedes #154\nSuperseded by #173"
    assert referenced_issues(body) == [153]
    assert supersession(body) == {"supersedes": [154], "superseded_by": [173]}


def test_deploy_success_does_not_count_as_exact_head_ci() -> None:
    head = "abc123"
    runs = [
        {"head_sha": head, "name": "Cloudflare Preview Deploy", "status": "completed", "conclusion": "success", "created_at": "2026-09-26T00:00:00Z", "id": 1},
        {"head_sha": head, "name": "Audit open PR lifecycle", "status": "completed", "conclusion": "success", "created_at": "2026-09-26T00:01:00Z", "id": 2},
    ]
    result = exact_head_ci(runs, head)
    assert result["present"] is False
    assert result["generic_exact_head_actions"] == 2
    assert classify(behind=0, superseded_by=[], overlapping_newer_prs=[], head_age_days=1, ci_present=result["present"]) == "needs-ci"


def test_real_ci_on_exact_head_is_reported() -> None:
    head = "abc123"
    runs = [
        {"head_sha": head, "name": "CI", "status": "completed", "conclusion": "success", "created_at": "2026-09-26T00:02:00Z", "id": 3},
        {"head_sha": "old", "name": "CI", "status": "completed", "conclusion": "success", "created_at": "2026-09-26T00:03:00Z", "id": 4},
    ]
    result = exact_head_ci(runs, head)
    assert result["present"] is True
    assert result["run_id"] == 3


def test_lifecycle_status_prefers_supersession_then_rebase_then_ci_then_age() -> None:
    assert classify(behind=0, superseded_by=[173], overlapping_newer_prs=[], head_age_days=1, ci_present=False) == "superseded-candidate"
    assert classify(behind=0, superseded_by=[], overlapping_newer_prs=[182], head_age_days=1, ci_present=False) == "superseded-candidate"
    assert classify(behind=2, superseded_by=[], overlapping_newer_prs=[], head_age_days=40, ci_present=False) == "needs-rebase"
    assert classify(behind=0, superseded_by=[], overlapping_newer_prs=[], head_age_days=1, ci_present=False) == "needs-ci"
    assert classify(behind=0, superseded_by=[], overlapping_newer_prs=[], head_age_days=30, ci_present=True) == "stale-candidate"
    assert classify(behind=0, superseded_by=[], overlapping_newer_prs=[], head_age_days=29, ci_present=True) == "active"
