"""Canonical dbt exposure links must not silently drift to another host."""
from pathlib import Path

from scripts.verify_dbt_exposure_origin import EXPECTED_TOKEN, audit


def test_repository_exposures_use_canonical_origin() -> None:
    path = Path(__file__).resolve().parents[1] / "analytics/dbt/models/exposures.yml"
    assert audit(path) == []


def test_legacy_and_wrong_default_hosts_fail(tmp_path: Path) -> None:
    path = tmp_path / "exposures.yml"
    path.write_text(
        "url: https://kafka2306.github.io/cast_event_cal/events.json\n",
        encoding="utf-8",
    )
    assert len(audit(path)) == 1

    path.write_text(
        "url: \"{{ env_var('CAST_EVENT_CAL_PUBLIC_ORIGIN', "
        "'https://wrong.example') }}/events.json\"\n",
        encoding="utf-8",
    )
    assert len(audit(path)) == 1

    path.write_text(f'url: "{EXPECTED_TOKEN}/events.json"\n', encoding="utf-8")
    assert audit(path) == []
