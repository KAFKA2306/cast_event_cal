from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / ".github/workflows/update-calendar-v2.yml"


def _section(text: str, start: str, end: str | None = None) -> str:
    chunk = text.split(start, 1)[1]
    return chunk.split(end, 1)[0] if end else chunk


def test_calendar_build_is_read_only_and_publish_is_the_only_writer() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    top = text.split("jobs:", 1)[0]
    build = _section(text, "  build:\n", "  publish:\n")
    publish = _section(text, "  publish:\n")

    assert "permissions:\n  contents: read" in top
    assert "contents: write" not in build
    assert "needs: build" in publish
    assert "permissions:\n      contents: write" in publish
    assert "actions/download-artifact@v5" in publish
    assert "git push origin HEAD:main" in publish


def test_validated_snapshot_crosses_jobs_as_an_explicit_artifact() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    build = _section(text, "  build:\n", "  publish:\n")

    assert "actions/upload-artifact@v4" in build
    assert "if-no-files-found: error" in build
    for required in (
        "data/discovered_events.json",
        "data/yahoo_realtime_events.json",
        "data/external_events.json",
        "public/",
    ):
        assert required in build
