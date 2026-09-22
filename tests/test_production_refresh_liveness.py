from pathlib import Path

WATCHDOG = Path(".github/workflows/production-refresh-liveness.yml")
PRODUCTION = Path(".github/workflows/update-calendar-v2.yml")


def test_liveness_watch_is_independent_from_production_workflow() -> None:
    text = WATCHDOG.read_text(encoding="utf-8")
    assert "schedule:" in text
    assert "update-calendar-v2.yml" in text
    assert "status: 'success'" in text
    assert "3 * 60 * 60 * 1000" in text
    assert "Production refresh SLA breached" in text


def test_watchdog_is_not_embedded_in_production_workflow() -> None:
    assert WATCHDOG != PRODUCTION
