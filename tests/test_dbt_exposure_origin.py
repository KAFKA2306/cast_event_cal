from pathlib import Path

from scripts.verify_dbt_exposure_origin import ENV_TOKEN, audit


def test_exposure_audit_accepts_authority_and_rejects_legacy_host(tmp_path: Path) -> None:
    expected = "https://vrc-cast-event-calender.pages.dev"
    exposures = tmp_path / "exposures.yml"
    exposures.write_text(
        f'url: "{ENV_TOKEN}/events.json"\nurl: "{ENV_TOKEN}/calendar.ics"\nurl: "{ENV_TOKEN}/tonight/"\n',
        encoding="utf-8",
    )
    assert audit(exposures, expected) == []

    exposures.write_text(
        "url: https://kafka2306.github.io/cast_event_cal/events.json\n",
        encoding="utf-8",
    )
    failures = audit(exposures, expected)
    assert len(failures) == 1
    assert "bypasses canonical origin authority" in failures[0]
