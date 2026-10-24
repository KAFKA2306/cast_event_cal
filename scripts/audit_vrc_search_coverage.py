from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cast_event_cal import core
from scripts import fetch_external_calendars as external
from scripts.deduplicate_occurrences import deduplicate_events

DEFAULT_EXTERNAL_CONFIG = Path("config/external_calendars.yaml")
DEFAULT_SOURCES_CONFIG = Path("config/sources.yaml")
DEFAULT_EXTERNAL_EVENTS = Path("data/external_events.json")
DEFAULT_HEALTH = Path("public/health.json")


def _source_path(config_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (config_path.parent.parent / path).resolve()


def _read_public_health(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _source_rows(
    sources_config_path: Path,
    *,
    external_rows: list[dict[str, Any]] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    config = core.load_config(sources_config_path)
    selected: list[tuple[str, dict[str, Any]]] = []
    for source in config.get("sources", []):
        if (
            not isinstance(source, dict)
            or not source.get("enabled", True)
            or source.get("type") != "manual_json"
        ):
            continue
        name = core.clean_text(source.get("name"))
        if name == "external_calendar_events" and external_rows is not None:
            rows = external_rows
        else:
            path = _source_path(sources_config_path, str(source["path"]))
            rows = external.read_json_array(path)
        selected.extend((name, row) for row in rows if isinstance(row, dict))
    return selected


def _public_count(
    sources_config_path: Path,
    *,
    external_rows: list[dict[str, Any]] | None,
    now: datetime,
) -> tuple[int, int]:
    config = core.load_config(sources_config_path)
    fetched_at = core.normalize_datetime(now)
    events: list[core.Event] = []
    for source_name, row in _source_rows(
        sources_config_path,
        external_rows=external_rows,
    ):
        try:
            events.append(core.build_event(row, source_name, fetched_at))
        except (TypeError, ValueError):
            continue
    normalized = core.deduplicate(events)
    window = config.get("window", {})
    normalized = core.filter_window(
        normalized,
        past_days=int(window.get("past_days", 1)),
        future_days=int(window.get("future_days", 120)),
        now=now,
    )
    public_rows, _audit = deduplicate_events(
        [asdict(event) for event in normalized]
    )
    return len(normalized), len(public_rows)


def audit(
    *,
    external_config_path: Path,
    sources_config_path: Path,
    external_events_path: Path,
    health_path: Path,
    output_path: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    generated_at = (now or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    config = external.load_config(external_config_path)
    source = next(
        (
            row
            for row in config.get("sources", [])
            if isinstance(row, dict)
            and row.get("enabled", True)
            and row.get("type") == "vrc_search_pages"
        ),
        None,
    )
    if source is None:
        raise RuntimeError("enabled vrc_search_pages source is not configured")

    window = config.get("window", {})
    start = generated_at - timedelta(days=int(window.get("past_days", 1)))
    end = generated_at + timedelta(days=int(window.get("future_days", 120)))
    timeout = float(config.get("http", {}).get("timeout_seconds", external.DEFAULT_TIMEOUT))
    fetched_at = external.utc_text(generated_at)

    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": external.USER_AGENT},
    ) as client:
        discovered = external.collect_vrc_search_pages(
            client,
            source,
            config_path=external_config_path,
            fetched_at=fetched_at,
            start=start,
            end=end,
        )

    previous_external = external.read_json_array(external_events_path)
    source_name = external.clean_text(source["name"])
    retained_external = [
        row
        for row in previous_external
        if external.clean_text(row.get("source")) != source_name
    ]
    gathered_external = [*retained_external, *discovered]

    dedupe_reference: list[dict[str, Any]] = []
    for value in config.get("dedupe_against", []):
        dedupe_reference.extend(
            external.read_json_array(external.resolve_path(external_config_path, str(value)))
        )
    expanded_external, external_excluded = external.deduplicate_external(
        gathered_external,
        dedupe_reference,
    )

    normalized_before, public_before = _public_count(
        sources_config_path,
        external_rows=previous_external,
        now=generated_at,
    )
    normalized_after, public_after = _public_count(
        sources_config_path,
        external_rows=expanded_external,
        now=generated_at,
    )
    health = _read_public_health(health_path)
    published_baseline = health.get("event_count")

    report = {
        "schema_version": "1.0",
        "generated_at": fetched_at,
        "source": source_name,
        "configured_page_count": min(
            len(external.source_urls(source, external_config_path)),
            int(source.get("max_pages", 8)),
        ),
        "vrc_search_discovered": len(discovered),
        "external_events_before": len(previous_external),
        "external_events_after": len(expanded_external),
        "external_events_delta": len(expanded_external) - len(previous_external),
        "external_deduplicated_against_existing": external_excluded,
        "normalized_before": normalized_before,
        "normalized_after": normalized_after,
        "normalized_delta": normalized_after - normalized_before,
        "public_before_simulated": public_before,
        "public_after_simulated": public_after,
        "public_net_delta": public_after - public_before,
        "production_health_event_count": published_baseline,
        "baseline_matches_production_health": (
            isinstance(published_baseline, int) and published_baseline == public_before
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only live audit of VRC Search publication-count contribution"
    )
    parser.add_argument("--external-config", type=Path, default=DEFAULT_EXTERNAL_CONFIG)
    parser.add_argument("--sources-config", type=Path, default=DEFAULT_SOURCES_CONFIG)
    parser.add_argument("--external-events", type=Path, default=DEFAULT_EXTERNAL_EVENTS)
    parser.add_argument("--health", type=Path, default=DEFAULT_HEALTH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(
        external_config_path=args.external_config,
        sources_config_path=args.sources_config,
        external_events_path=args.external_events,
        health_path=args.health,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
