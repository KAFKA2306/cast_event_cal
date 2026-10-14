from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from audit_public_feed import _event_list, _identity, _load

SCHEMA_VERSION = "cast-event-cal.semantic-collision-audit.v1"
_WORDS = re.compile(r"[\w]+", re.UNICODE)


def _norm(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return " ".join(_WORDS.findall(unicodedata.normalize("NFKC", value).casefold())) or None


def _start(event: dict[str, Any]) -> str | None:
    value = event.get("start") or event.get("start_at") or event.get("start_datetime")
    return (
        value.strip().replace("Z", "+00:00")
        if isinstance(value, str) and value.strip()
        else None
    )


def _url_key(event: dict[str, Any]) -> str | None:
    for key in (
        "official_url",
        "participation_url",
        "join_url",
        "group_url",
        "url",
        "source_url",
    ):
        value = event.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        parsed = urlparse(value.strip())
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            path = parsed.path.rstrip("/") or "/"
            return f"{parsed.netloc.casefold()}{path}"
    return None


def _facts(event: dict[str, Any]) -> dict[str, str]:
    facts: dict[str, str] = {}
    start = _start(event)
    title = _norm(event.get("title") or event.get("name"))
    organizer = _norm(
        event.get("organizer")
        or event.get("organizer_name")
        or event.get("series")
        or event.get("series_name")
    )
    url = _url_key(event)
    if start:
        facts["start"] = start
    if title:
        facts["title"] = title
    if organizer:
        facts["organizer"] = organizer
    if url:
        facts["url"] = url
    for key in ("group_id", "world_id", "instance_id"):
        value = _norm(event.get(key))
        if value:
            facts[key] = value
    return facts


def audit(path: Path) -> dict[str, Any]:
    events = _event_list(_load(path))
    rows = []
    for event in events:
        identity = _identity(event)
        if identity:
            rows.append((identity, _facts(event)))
    groups: dict[str, list[tuple[str, dict[str, str]]]] = defaultdict(list)
    for identity, facts in rows:
        if "start" in facts:
            groups[facts["start"]].append((identity, facts))
    collisions = []
    insufficient = []
    for start, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        for i, (left_id, left) in enumerate(members):
            for right_id, right in members[i + 1 :]:
                if left_id == right_id:
                    continue
                evidence = sorted(
                    k
                    for k in set(left) & set(right)
                    if k != "start" and left[k] == right[k]
                )
                record = {
                    "member_ids": sorted([left_id, right_id]),
                    "start": start,
                    "evidence_fields": evidence,
                }
                strong = [
                    k
                    for k in evidence
                    if k in {"organizer", "url", "group_id", "world_id", "instance_id"}
                ]
                if "title" in evidence and strong:
                    record["classification"] = "high_confidence"
                    collisions.append(record)
                elif evidence:
                    record["classification"] = "review_candidate"
                    collisions.append(record)
                else:
                    record["classification"] = "insufficient_evidence"
                    insufficient.append(record)
    collisions.sort(
        key=lambda x: (x["member_ids"], x["classification"], x["evidence_fields"])
    )
    insufficient.sort(key=lambda x: x["member_ids"])
    return {
        "schema_version": SCHEMA_VERSION,
        "event_count": len(events),
        "collision_count": len(collisions),
        "collisions": collisions,
        "insufficient_evidence": insufficient,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only semantic collision audit for the published event feed"
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit(args.path)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
