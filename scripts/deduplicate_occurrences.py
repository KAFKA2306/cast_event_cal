from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from cast_event_cal.core import Event, render_ics

DEFAULT_EVENTS = Path("public/events.json")
DEFAULT_ICS = Path("public/calendar.ics")
DEFAULT_AUDIT = Path("public/event-duplicate-audit.json")

SOURCE_PRIORITY = {
    "repository_manual_events": 50,
    "vrchat_calendar_discovery": 45,
    "external_calendar_events": 40,
    "x_curated_events": 30,
    "yahoo_realtime_events": 20,
}

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
ORDINAL_RE = re.compile(r"第\s*(\d{1,4})\s*回")
SPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^0-9a-zぁ-んァ-ヶ一-龠]+", re.IGNORECASE)


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = URL_RE.sub("", text)
    text = SPACE_RE.sub("", text)
    return NON_WORD_RE.sub("", text)


def canonical_url(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw.startswith("https://"):
        return None
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    if host in {"twitter.com", "www.twitter.com", "www.x.com"}:
        host = "x.com"
    query = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
    ]
    return urlunparse(("https", host, parsed.path.rstrip("/"), "", urlencode(query), ""))


def source_record_id(event: dict[str, Any]) -> str:
    existing = str(event.get("source_record_id") or "").strip()
    if existing:
        return existing
    source = str(event.get("source") or "unknown").strip()
    source_id = str(event.get("source_id") or "").strip()
    url = canonical_url(event.get("url"))
    fallback = str(event.get("id") or "").strip()
    if source_id:
        payload = f"{source}|source-id|{source_id}"
    elif url:
        payload = f"{source}|url|{url}"
    else:
        payload = f"{source}|event-id|{fallback}"
    return "src_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def event_text(event: dict[str, Any]) -> str:
    return str(event.get("description") or event.get("title") or "")


def event_ordinal(event: dict[str, Any]) -> str | None:
    match = ORDINAL_RE.search(unicodedata.normalize("NFKC", event_text(event)))
    return match.group(1) if match else None


def similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_text = normalize_text(event_text(left))
    right_text = normalize_text(event_text(right))
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()


def occurrence_match(
    left: dict[str, Any], right: dict[str, Any]
) -> tuple[str, float] | None:
    if str(left.get("starts_at") or "") != str(right.get("starts_at") or ""):
        return None

    if source_record_id(left) == source_record_id(right):
        return "exact_source_record", 1.0

    left_url = canonical_url(left.get("url"))
    right_url = canonical_url(right.get("url"))
    if left_url and left_url == right_url:
        return "same_canonical_url", 1.0

    left_description = normalize_text(left.get("description"))
    right_description = normalize_text(right.get("description"))
    if len(left_description) >= 24 and left_description == right_description:
        return "exact_text_same_start", 0.99

    left_organizer = normalize_text(left.get("organizer"))
    right_organizer = normalize_text(right.get("organizer"))
    if not left_organizer or left_organizer != right_organizer:
        return None

    left_ordinal = event_ordinal(left)
    right_ordinal = event_ordinal(right)
    if (left_ordinal or right_ordinal) and left_ordinal != right_ordinal:
        return None

    score = similarity(left, right)
    if left_ordinal and right_ordinal and score >= 0.50:
        return "same_organizer_same_start_ordinal", round(
            min(0.96, 0.80 + score * 0.25), 4
        )
    if score >= 0.75:
        return "same_organizer_same_start_high_similarity", round(
            min(0.94, 0.74 + score * 0.25), 4
        )
    return None


def representative_score(event: dict[str, Any]) -> tuple[Any, ...]:
    scalar_fields = (
        "organizer",
        "location",
        "description",
        "url",
        "image_url",
        "primary_action_url",
        "vrchat_group_url",
        "official_x_url",
        "official_website_url",
    )
    completeness = sum(bool(event.get(field)) for field in scalar_fields)
    completeness += min(3, len(event.get("official_links") or []))
    completeness += min(2, len(event.get("related_links") or []))
    return (
        SOURCE_PRIORITY.get(str(event.get("source") or ""), 0),
        completeness,
        float(event.get("confidence") or 0.0),
        str(event.get("fetched_at") or ""),
        source_record_id(event),
    )


def provenance(event: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        deepcopy(row)
        for row in event.get("provenance") or []
        if isinstance(row, dict)
    ]
    rows.append(
        {
            "source_record_id": source_record_id(event),
            "event_id": event.get("id"),
            "source": event.get("source"),
            "source_id": event.get("source_id"),
            "url": event.get("url"),
            "organizer": event.get("organizer"),
            "fetched_at": event.get("fetched_at"),
        }
    )
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("source_record_id") or "") or json.dumps(
            row, ensure_ascii=False, sort_keys=True
        )
        selected.setdefault(key, row)
    return [selected[key] for key in sorted(selected)]


def unique_link_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        url = canonical_url(row.get("url"))
        key = url or json.dumps(row, ensure_ascii=False, sort_keys=True)
        selected.setdefault(key, deepcopy(row))
    return [selected[key] for key in sorted(selected)]


def occurrence_id(
    members: list[dict[str, Any]], reasons: list[str]
) -> str:
    existing = {
        str(member.get("occurrence_id") or "").strip()
        for member in members
        if member.get("occurrence_id")
    }
    if len(existing) == 1:
        return next(iter(existing))

    start = str(members[0].get("starts_at") or "")
    urls = {canonical_url(member.get("url")) for member in members}
    urls.discard(None)
    descriptions = {normalize_text(member.get("description")) for member in members}
    descriptions.discard("")
    organizers = {normalize_text(member.get("organizer")) for member in members}
    organizers.discard("")
    ordinals = {event_ordinal(member) for member in members}
    ordinals.discard(None)

    if len(urls) == 1 and "same_canonical_url" in reasons:
        payload = f"url|{start}|{next(iter(urls))}"
    elif len(descriptions) == 1 and "exact_text_same_start" in reasons:
        payload = f"text|{start}|{next(iter(descriptions))}"
    elif len(organizers) == 1 and len(ordinals) == 1:
        payload = (
            f"organizer-ordinal|{start}|{next(iter(organizers))}|"
            f"{next(iter(ordinals))}"
        )
    else:
        payload = "members|" + start + "|" + "|".join(
            sorted(source_record_id(member) for member in members)
        )
    return "occ_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def merge_members(
    members: list[dict[str, Any]], matches: list[tuple[str, float]]
) -> dict[str, Any]:
    row = deepcopy(max(members, key=representative_score))
    representative_source_record_id = source_record_id(row)
    reasons = sorted({reason for reason, _confidence in matches})
    canonical_id = occurrence_id(members, reasons)

    row["id"] = canonical_id
    row["occurrence_id"] = canonical_id
    row["source_record_id"] = representative_source_record_id
    row["merge_reason"] = reasons
    row["merge_confidence"] = min(
        (confidence for _reason, confidence in matches), default=1.0
    )

    all_provenance = [entry for member in members for entry in provenance(member)]
    selected_provenance: dict[str, dict[str, Any]] = {}
    for entry in all_provenance:
        selected_provenance.setdefault(str(entry["source_record_id"]), entry)
    row["provenance"] = [
        selected_provenance[key] for key in sorted(selected_provenance)
    ]
    row["merged_source_count"] = len(row["provenance"])

    row["tags"] = sorted(
        {
            str(tag)
            for member in members
            for tag in member.get("tags") or []
            if str(tag).strip()
        }
    )
    for field in ("official_links", "related_links"):
        row[field] = unique_link_rows(
            [
                link
                for member in members
                for link in member.get(field) or []
                if isinstance(link, dict)
            ]
        )

    ranked = sorted(members, key=representative_score, reverse=True)
    for field in (
        "image_url",
        "image_kind",
        "primary_action_url",
        "primary_action_kind",
        "official_x_url",
        "official_website_url",
        "vrchat_group_url",
        "vrchat_group_image_url",
        "preferred_image_url",
        "preferred_image_kind",
    ):
        if row.get(field):
            continue
        row[field] = next(
            (deepcopy(member[field]) for member in ranked if member.get(field)),
            None,
        )
    return row


def cluster_events(
    events: list[dict[str, Any]],
) -> tuple[list[list[int]], dict[tuple[int, int], tuple[str, float]], list[dict[str, Any]]]:
    parent = list(range(len(events)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    by_start: dict[str, list[int]] = defaultdict(list)
    for index, event in enumerate(events):
        by_start[str(event.get("starts_at") or "")].append(index)

    matches: dict[tuple[int, int], tuple[str, float]] = {}
    ambiguous: list[dict[str, Any]] = []
    for indexes in by_start.values():
        for left, right in combinations(indexes, 2):
            result = occurrence_match(events[left], events[right])
            if result:
                matches[(left, right)] = result
                union(left, right)
                continue
            left_organizer = normalize_text(events[left].get("organizer"))
            right_organizer = normalize_text(events[right].get("organizer"))
            score = similarity(events[left], events[right])
            if left_organizer and left_organizer == right_organizer and score >= 0.45:
                ambiguous.append(
                    {
                        "left_id": events[left].get("id"),
                        "right_id": events[right].get("id"),
                        "starts_at": events[left].get("starts_at"),
                        "organizer": events[left].get("organizer"),
                        "similarity": round(score, 4),
                        "left_title": events[left].get("title"),
                        "right_title": events[right].get("title"),
                    }
                )

    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(events)):
        groups[find(index)].append(index)
    return (
        sorted((sorted(group) for group in groups.values()), key=lambda group: group[0]),
        matches,
        sorted(
            ambiguous,
            key=lambda row: (
                str(row.get("starts_at")),
                str(row.get("organizer")),
                str(row.get("left_id")),
                str(row.get("right_id")),
            ),
        )[:100],
    )


def deduplicate_events(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    working = [deepcopy(event) for event in events if isinstance(event, dict)]
    groups, matches, ambiguous = cluster_events(working)
    output: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    merged_pairs: set[tuple[str, str]] = set()

    for indexes in groups:
        members = [working[index] for index in indexes]
        if len(members) == 1:
            row = deepcopy(members[0])
            row["source_record_id"] = source_record_id(row)
            row["occurrence_id"] = str(row.get("occurrence_id") or row.get("id"))
            row.setdefault("provenance", provenance(row))
            row.setdefault("merged_source_count", len(row["provenance"]))
            row.setdefault("merge_reason", [])
            row.setdefault("merge_confidence", 1.0)
            output.append(row)
            continue

        member_matches = [
            result
            for (left, right), result in matches.items()
            if left in indexes and right in indexes
        ]
        merged = merge_members(members, member_matches)
        output.append(merged)
        member_ids = sorted(str(member.get("id")) for member in members)
        merged_pairs.update(tuple(sorted(pair)) for pair in combinations(member_ids, 2))
        clusters.append(
            {
                "cluster_id": merged["occurrence_id"],
                "starts_at": merged.get("starts_at"),
                "title": merged.get("title"),
                "member_count": len(members),
                "member_ids": member_ids,
                "source_record_ids": sorted(source_record_id(member) for member in members),
                "sources": sorted({str(member.get("source")) for member in members}),
                "reasons": sorted({reason for reason, _confidence in member_matches}),
                "confidence": min(
                    (confidence for _reason, confidence in member_matches), default=1.0
                ),
                "representative_source_record_id": merged["source_record_id"],
            }
        )

    negative_samples: list[dict[str, Any]] = []
    by_start: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in working:
        by_start[str(event.get("starts_at") or "")].append(event)
    for rows in by_start.values():
        for left, right in combinations(rows, 2):
            pair = tuple(sorted((str(left.get("id")), str(right.get("id")))))
            if pair in merged_pairs:
                continue
            negative_samples.append(
                {
                    "left_id": left.get("id"),
                    "right_id": right.get("id"),
                    "starts_at": left.get("starts_at"),
                    "left_organizer": left.get("organizer"),
                    "right_organizer": right.get("organizer"),
                    "similarity": round(similarity(left, right), 4),
                    "left_title": left.get("title"),
                    "right_title": right.get("title"),
                }
            )
            if len(negative_samples) == 10:
                break
        if len(negative_samples) == 10:
            break

    output.sort(key=lambda row: (str(row.get("starts_at")), str(row.get("title"))))
    collapsed = len(working) - len(output)
    audit = {
        "schema_version": "1.0",
        "policy_version": "canonical-occurrence.v1",
        "event_count_before": len(working),
        "event_count_after": len(output),
        "candidate_cluster_count": len(clusters),
        "duplicate_cluster_count": len(clusters),
        "duplicate_occurrence_count": collapsed,
        "duplicate_post_count": collapsed,
        "duplicate_rate": round(collapsed / len(working), 6) if working else 0.0,
        "exact_source_duplicate_count": sum(
            "exact_source_record" in cluster["reasons"] for cluster in clusters
        ),
        "unresolved_ambiguous_cluster_count": len(ambiguous),
        "clusters": sorted(clusters, key=lambda row: str(row["cluster_id"])),
        "ambiguous_candidates": ambiguous,
        "negative_samples": negative_samples,
    }
    return output, audit


def public_event(row: dict[str, Any]) -> Event:
    return Event(
        id=str(row.get("occurrence_id") or row.get("id")),
        title=str(row.get("title") or "VRChat event"),
        starts_at=str(row["starts_at"]),
        ends_at=row.get("ends_at"),
        organizer=row.get("organizer"),
        location=row.get("location"),
        description=row.get("description"),
        url=row.get("url"),
        image_url=row.get("image_url"),
        category=row.get("category"),
        status=str(row.get("status") or "scheduled"),
        source=str(row.get("source") or "unknown"),
        source_id=row.get("source_id"),
        fetched_at=row.get("fetched_at"),
        tags=list(row.get("tags") or []),
        confidence=float(row.get("confidence") or 0.0),
        review_required=bool(row.get("review_required", False)),
    ).normalized()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collapse duplicate source posts into canonical event occurrences"
    )
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--ics", type=Path, default=DEFAULT_ICS)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    document = json.loads(args.events.read_text(encoding="utf-8"))
    rows = document.get("events", [])
    generated_at = str(document.get("generated_at") or "")
    if not isinstance(rows, list):
        raise ValueError("events document must contain an events array")
    if not generated_at:
        raise ValueError("events document must contain generated_at")

    deduped, audit = deduplicate_events(rows)
    audit["generated_at"] = generated_at
    document["events"] = deduped
    document["count"] = len(deduped)
    document["occurrence_dedup"] = {
        key: audit[key]
        for key in (
            "policy_version",
            "event_count_before",
            "event_count_after",
            "duplicate_occurrence_count",
            "duplicate_cluster_count",
        )
    }

    args.events.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.audit.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    args.ics.write_text(
        render_ics([public_event(row) for row in deduped], generated),
        encoding="utf-8",
        newline="",
    )
    print(
        "Occurrence dedup: "
        f"before={audit['event_count_before']} after={audit['event_count_after']} "
        f"collapsed={audit['duplicate_occurrence_count']} "
        f"clusters={audit['duplicate_cluster_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
