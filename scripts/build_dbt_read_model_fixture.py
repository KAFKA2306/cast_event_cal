from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

VARIANTS = {"healthy", "duplicate", "orphan", "invalid_decision"}


def build_fixture(path: Path, *, variant: str = "healthy") -> None:
    if variant not in VARIANTS:
        raise ValueError(f"unsupported fixture variant: {variant}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)

    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            create table source_records (
                source text,
                source_id text,
                source_url text,
                canonical_url text,
                source_created_at text,
                first_seen_at text,
                last_seen_at text,
                observed_at text,
                content_hash text,
                decision text,
                reason text,
                parser_version text,
                schema_version text
            );

            create table event_occurrences (
                event_id text,
                title text,
                starts_at text,
                ends_at text,
                organizer_id text,
                series_id text,
                category text,
                participation_url text,
                lifecycle text
            );

            create table event_sources (
                event_id text,
                source text,
                source_id text,
                evidence_type text,
                confidence real
            );

            create table collection_runs (
                run_id text,
                started_at text,
                completed_at text,
                source text,
                status text,
                fetched_count integer,
                accepted_count integer,
                rejected_count integer
            );
            """
        )

        source_records = [
            (
                "yahoo",
                "y-1",
                "https://example.invalid/y-1",
                "https://example.invalid/events/1",
                "2026-09-25T09:00:00Z",
                "2026-09-25T09:01:00Z",
                "2026-09-25T09:02:00Z",
                "2026-09-25T09:02:00Z",
                "hash-y-1",
                "accepted",
                None,
                "fixture-v1",
                "1.0",
            ),
            (
                "manual",
                "m-1",
                "https://example.invalid/m-1",
                "https://example.invalid/events/2",
                "2026-09-25T10:00:00Z",
                "2026-09-25T10:01:00Z",
                "2026-09-25T10:02:00Z",
                "2026-09-25T10:02:00Z",
                "hash-m-1",
                "accepted",
                None,
                "fixture-v1",
                "1.0",
            ),
            (
                "x",
                "x-1",
                "https://example.invalid/x-1",
                None,
                "2026-09-25T11:00:00Z",
                "2026-09-25T11:01:00Z",
                "2026-09-25T11:02:00Z",
                "2026-09-25T11:02:00Z",
                "hash-x-1",
                "rejected",
                "missing_datetime",
                "fixture-v1",
                "1.0",
            ),
        ]
        if variant == "duplicate":
            source_records.append(
                (
                    "yahoo",
                    "y-1",
                    "https://example.invalid/y-1-duplicate",
                    "https://example.invalid/events/1",
                    "2026-09-25T09:00:00Z",
                    "2026-09-25T09:01:00Z",
                    "2026-09-25T09:03:00Z",
                    "2026-09-25T09:03:00Z",
                    "hash-y-1-duplicate",
                    "accepted",
                    None,
                    "fixture-v1",
                    "1.0",
                )
            )
        if variant == "invalid_decision":
            source_records.append(
                (
                    "external",
                    "e-1",
                    "https://example.invalid/e-1",
                    None,
                    "2026-09-25T12:00:00Z",
                    "2026-09-25T12:01:00Z",
                    "2026-09-25T12:02:00Z",
                    "2026-09-25T12:02:00Z",
                    "hash-e-1",
                    "maybe",
                    None,
                    "fixture-v1",
                    "1.0",
                )
            )

        connection.executemany(
            """
            insert into source_records values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            source_records,
        )
        connection.executemany(
            "insert into event_occurrences values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "event-1",
                    "Fixture Event One",
                    "2026-09-26T10:00:00Z",
                    "2026-09-26T12:00:00Z",
                    "org-1",
                    "series-1",
                    "community",
                    "https://example.invalid/join/1",
                    "upcoming",
                ),
                (
                    "event-2",
                    "Fixture Event Two",
                    "2026-09-27T10:00:00Z",
                    None,
                    None,
                    None,
                    "technology",
                    "https://example.invalid/join/2",
                    "upcoming",
                ),
            ],
        )

        event_sources = [
            ("event-1", "yahoo", "y-1", "announcement", 1.0),
            ("event-2", "manual", "m-1", "curated", 1.0),
        ]
        if variant == "orphan":
            event_sources.append(("missing-event", "yahoo", "y-1", "announcement", 1.0))
        connection.executemany(
            "insert into event_sources values (?, ?, ?, ?, ?)",
            event_sources,
        )
        connection.executemany(
            "insert into collection_runs values (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "run-yahoo-1",
                    "2026-09-25T08:59:00Z",
                    "2026-09-25T09:03:00Z",
                    "yahoo",
                    "ok",
                    2,
                    1,
                    1,
                ),
                (
                    "run-manual-1",
                    "2026-09-25T09:59:00Z",
                    "2026-09-25T10:03:00Z",
                    "manual",
                    "ok",
                    1,
                    1,
                    0,
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic #158-compatible SQLite schema fixture")
    parser.add_argument("output", type=Path)
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="healthy")
    args = parser.parse_args()
    build_fixture(args.output, variant=args.variant)
    print(f"built dbt read-model fixture: variant={args.variant} path={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
