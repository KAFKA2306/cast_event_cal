from pathlib import Path

import pytest

from scripts.verify_calendar_subscription import verify_calendar_subscription_contract


def _surface(tmp_path: Path, *, canonical: str, alternate: str, readme_feed: str) -> Path:
    public = tmp_path / "public"
    public.mkdir()
    (public / "index.html").write_text(
        f'<link rel="canonical" href="{canonical}">\n'
        f'<link rel="alternate" type="text/calendar" title="Calendar" href="{alternate}">\n',
        encoding="utf-8",
    )
    (public / "calendar.ics").write_text("BEGIN:VCALENDAR\nEND:VCALENDAR\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(f"- iCalendar: {readme_feed}\n", encoding="utf-8")
    return tmp_path


def test_repository_calendar_subscription_contract() -> None:
    expected = "https://kafka2306.github.io/cast_event_cal/calendar.ics"
    assert verify_calendar_subscription_contract() == expected


def test_calendar_subscription_contract_rejects_conflicting_surface(tmp_path: Path) -> None:
    root = _surface(
        tmp_path,
        canonical="https://example.test/app/",
        alternate="calendar.ics",
        readme_feed="https://other.test/calendar.ics",
    )
    with pytest.raises(AssertionError, match="README calendar URL drift"):
        verify_calendar_subscription_contract(root)
