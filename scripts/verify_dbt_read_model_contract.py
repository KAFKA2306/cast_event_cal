from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

if __package__:
    from scripts.build_dbt_read_model_fixture import build_fixture
else:
    from build_dbt_read_model_fixture import build_fixture

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "analytics" / "dbt"
TARGET = PROJECT / "target"
MODEL_TABLES = (
    "stg_source_records",
    "stg_event_occurrences",
    "stg_event_sources",
    "stg_collection_runs",
    "fct_collection_runs",
    "fct_publication_quality",
)
NEGATIVE_CASES = {
    "duplicate": "unique_pair",
    "orphan": "relationships",
    "invalid_decision": "accepted_values",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dbt_environment(canonical_db: Path, analytics_db: Path, schema_dir: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "DBT_CANONICAL_DB": str(canonical_db.resolve()),
            "DBT_ANALYTICS_DB": str(analytics_db.resolve()),
            "DBT_SCHEMA_DIR": str(schema_dir.resolve()),
        }
    )
    return environment


def run_dbt_build(
    canonical_db: Path,
    analytics_db: Path,
    schema_dir: Path,
    *,
    label: str,
) -> dict[str, Any]:
    shutil.rmtree(TARGET, ignore_errors=True)
    analytics_db.unlink(missing_ok=True)
    before_hash = file_sha256(canonical_db)

    started = time.perf_counter()
    completed = subprocess.run(
        [
            "dbt",
            "build",
            "--project-dir",
            str(PROJECT),
            "--profiles-dir",
            str(PROJECT),
        ],
        env=dbt_environment(canonical_db, analytics_db, schema_dir),
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed_seconds = round(time.perf_counter() - started, 3)

    after_hash = file_sha256(canonical_db)
    if before_hash != after_hash:
        raise RuntimeError(f"dbt mutated canonical input during {label}")

    return {
        "label": label,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed_seconds,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "canonical_sha256": before_hash,
    }


def logical_digest(database: Path) -> str:
    connection = sqlite3.connect(database)
    try:
        payload: list[dict[str, Any]] = []
        for table in MODEL_TABLES:
            columns = [
                str(row[1])
                for row in connection.execute(f'pragma table_info("{table}")').fetchall()
            ]
            if not columns:
                raise RuntimeError(f"missing dbt output table: {table}")
            order_by = ", ".join(f'"{column}"' for column in columns)
            rows = connection.execute(
                f'select * from "{table}" order by {order_by}'
            ).fetchall()
            payload.append(
                {
                    "table": table,
                    "columns": columns,
                    "rows": rows,
                }
            )
    finally:
        connection.close()

    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def target_bytes() -> int:
    if not TARGET.exists():
        return 0
    return sum(path.stat().st_size for path in TARGET.rglob("*") if path.is_file())


def tail_output(result: dict[str, Any], *, lines: int = 40) -> str:
    combined = f"{result['stdout']}\n{result['stderr']}".strip().splitlines()
    return "\n".join(combined[-lines:])


def verify(report_path: Path) -> dict[str, Any]:
    if shutil.which("dbt") is None:
        raise RuntimeError("dbt executable is not installed")

    with tempfile.TemporaryDirectory(prefix="cast-event-dbt-") as temporary:
        temp_root = Path(temporary)
        schema_dir = temp_root / "schemas"
        schema_dir.mkdir()

        healthy_db = temp_root / "healthy.db"
        build_fixture(healthy_db, variant="healthy")

        first_analytics = temp_root / "analytics-first.db"
        first = run_dbt_build(
            healthy_db,
            first_analytics,
            schema_dir,
            label="healthy-first",
        )
        if first["returncode"] != 0:
            raise RuntimeError(f"healthy dbt build failed:\n{tail_output(first)}")
        first_digest = logical_digest(first_analytics)

        negative_results: list[dict[str, Any]] = []
        for variant, expected_marker in NEGATIVE_CASES.items():
            broken_db = temp_root / f"{variant}.db"
            broken_analytics = temp_root / f"analytics-{variant}.db"
            build_fixture(broken_db, variant=variant)
            result = run_dbt_build(
                broken_db,
                broken_analytics,
                schema_dir,
                label=variant,
            )
            output = f"{result['stdout']}\n{result['stderr']}"
            if result["returncode"] == 0:
                raise RuntimeError(f"negative fixture unexpectedly passed: {variant}")
            if expected_marker not in output:
                raise RuntimeError(
                    f"negative fixture failed for the wrong reason: {variant}\n{tail_output(result)}"
                )
            negative_results.append(
                {
                    "variant": variant,
                    "expected_test_marker": expected_marker,
                    "returncode": result["returncode"],
                    "elapsed_seconds": result["elapsed_seconds"],
                }
            )

        second_analytics = temp_root / "analytics-second.db"
        second = run_dbt_build(
            healthy_db,
            second_analytics,
            schema_dir,
            label="healthy-second",
        )
        if second["returncode"] != 0:
            raise RuntimeError(f"second healthy dbt build failed:\n{tail_output(second)}")
        second_digest = logical_digest(second_analytics)
        if first_digest != second_digest:
            raise RuntimeError(
                f"same canonical input produced different logical outputs: {first_digest} != {second_digest}"
            )

        report = {
            "schema_version": "1.0",
            "adapter": {
                "name": "dbt-sqlite",
                "version": importlib.metadata.version("dbt-sqlite"),
            },
            "healthy_runs": [
                {
                    "label": first["label"],
                    "elapsed_seconds": first["elapsed_seconds"],
                    "logical_sha256": first_digest,
                },
                {
                    "label": second["label"],
                    "elapsed_seconds": second["elapsed_seconds"],
                    "logical_sha256": second_digest,
                },
            ],
            "negative_fixtures": negative_results,
            "canonical_input_sha256": second["canonical_sha256"],
            "analytics_db_bytes": second_analytics.stat().st_size,
            "dbt_target_bytes": target_bytes(),
            "public_output_written": False,
        }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the dbt canonical read-model quality boundary")
    parser.add_argument(
        "--report",
        type=Path,
        default=TARGET / "contract-verification.json",
    )
    args = parser.parse_args()
    report = verify(args.report)
    print(
        "dbt read-model contract: PASS "
        f"adapter={report['adapter']['version']} "
        f"logical_sha256={report['healthy_runs'][0]['logical_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
