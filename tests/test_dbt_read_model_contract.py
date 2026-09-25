import sqlite3
from pathlib import Path

import pytest

from scripts.build_dbt_read_model_fixture import build_fixture


def violation_counts(database: Path) -> dict[str, int]:
    connection = sqlite3.connect(database)
    try:
        duplicate = connection.execute(
            """
            select count(*)
            from (
                select source, source_id
                from source_records
                group by source, source_id
                having count(*) > 1
            )
            """
        ).fetchone()[0]
        orphan = connection.execute(
            """
            select count(*)
            from event_sources links
            left join event_occurrences events on events.event_id = links.event_id
            where events.event_id is null
            """
        ).fetchone()[0]
        invalid_decision = connection.execute(
            """
            select count(*)
            from source_records
            where decision not in ('accepted', 'rejected')
            """
        ).fetchone()[0]
    finally:
        connection.close()
    return {
        "duplicate": duplicate,
        "orphan": orphan,
        "invalid_decision": invalid_decision,
    }


def test_healthy_dbt_fixture_has_no_targeted_quality_violation(tmp_path: Path) -> None:
    database = tmp_path / "healthy.db"
    build_fixture(database, variant="healthy")

    assert violation_counts(database) == {
        "duplicate": 0,
        "orphan": 0,
        "invalid_decision": 0,
    }


@pytest.mark.parametrize("variant", ["duplicate", "orphan", "invalid_decision"])
def test_negative_dbt_fixture_contains_only_its_targeted_violation(
    tmp_path: Path,
    variant: str,
) -> None:
    database = tmp_path / f"{variant}.db"
    build_fixture(database, variant=variant)

    counts = violation_counts(database)
    assert counts[variant] > 0
    assert all(count == 0 for name, count in counts.items() if name != variant)
