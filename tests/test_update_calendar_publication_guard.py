from pathlib import Path


WORKFLOW = Path(".github/workflows/update-calendar-v2.yml")


def test_generated_snapshot_is_not_rebased_after_validation() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "VALIDATED_BASE_SHA=$(git rev-parse HEAD)" in text
    assert "git pull --rebase" not in text
    assert "git fetch origin main" in text
    assert 'REMOTE_MAIN_SHA=$(git rev-parse origin/main)' in text
    assert 'if [ "$REMOTE_MAIN_SHA" != "$VALIDATED_BASE_SHA" ]; then' in text
    assert "base_changed_after_validation" in text

    freshness = text.index("Gate generated snapshot freshness")
    fetch = text.index("git fetch origin main")
    push = text.index("git push origin HEAD:main")
    assert freshness < fetch < push
