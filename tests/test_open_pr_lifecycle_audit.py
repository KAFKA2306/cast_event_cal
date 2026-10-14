from scripts.audit_open_pr_lifecycle import classify, referenced_issues, supersession


def test_issue_and_supersession_evidence_is_explicit() -> None:
    body = "Fixes #153\nSupersedes #154\nSuperseded by #173"
    assert referenced_issues(body) == [153]
    assert supersession(body) == {"supersedes": [154], "superseded_by": [173]}


def test_lifecycle_status_prefers_supersession_then_rebase_then_age() -> None:
    assert classify(behind=0, superseded_by=[173], overlapping_newer_prs=[], head_age_days=1) == "superseded-candidate"
    assert classify(behind=0, superseded_by=[], overlapping_newer_prs=[182], head_age_days=1) == "superseded-candidate"
    assert classify(behind=2, superseded_by=[], overlapping_newer_prs=[], head_age_days=40) == "needs-rebase"
    assert classify(behind=0, superseded_by=[], overlapping_newer_prs=[], head_age_days=30) == "stale-candidate"
    assert classify(behind=0, superseded_by=[], overlapping_newer_prs=[], head_age_days=29) == "active"
