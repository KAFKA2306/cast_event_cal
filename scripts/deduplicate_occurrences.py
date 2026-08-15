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
    url = canonical_url(event.get("url")) or ""
    fallback = str(event.get("id") or "").strip()
    payload = "|".join((source, source_id, url, fallback))
    return "src_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def event_text(event: dict[str, Any]) -> str:
    return str(event.get("description") or event.get("title") or "")


def event_ordinal(event: dict[str, Any]) -> str | None:
    match = ORDINAL_RE.search(unicodedata.normalize("NFKC", event_text(event)))
    return match.group(1) if match else None


def comparable_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_text = normalize_text(event_text(left))
    right_text = normalize_text(event_text(right))
    if not left_text or not right_text:
        return 0.0
    return SequenceMatcher(None, left_text, right_text, autojunk=False).ratio()


def same_occurrence_reason(
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
    if (
        len(left_description) >= 24
        and left_description == right_description
    ):
        return "exact_text_same_start", 0.99

    left_title = normalize_text(left.get("title"))
    right_title = normalize_text(right.get("title"))
    if len(left_title) >= 20 and left_title == right_title:
        return "exact_title_same_start", 0.97

    left_organizer = normalize_text(left.get("organizer"))
    right_organizer = normalize_text(right.get("organizer"))
    if not left_organizer or left_organizer != right_organizer:
        return None

    left_ordinal = event_ordinal(left)
    right_ordinal = event_ordinal(right)
    if (left_ordinal or right_ordinal) and left_ordinal != right_ordinal:
        return None

    similarity = comparable_similarity(left, right)
    if left_ordinal and right_ordinal and similarity >= 0.50:
        return "same_organizer_same_start_ordinal", round(
            min(0.96, 0.80 + similarity * 0.25), 4
        )
    if similarity >= 0.72:
        return "same_organizer_same_start_high_similarity", round(
            min(0.94, 0.74 + similarity * 0.25), 4
        )
    return None


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        if self.rank[root_left] == self.rank[root_right]:
            self.rank[root_left] += 1


def completeness(event: dict[str, Any]) -> int:
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
    score = sum(bool(event.get(field)) for field in scalar_fields)
    score += min(3, len(event.get("official_links") or []))
    score += min(2, len(event.get("related_links") or []))
    return score


def representative_score(event: dict[str, Any]) -> tuple[Any, ...]:
    return (
        SOURCE_PRIORITY.get(str(event.get("source") or ""), 0),
        completeness(event),
        float(event.get("confidence") or 0.0),
        str(event.get("fetched_at") or ""),
        source_record_id(event),
    )


def unique_dicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = canonical_url(row.get("url")) or json.dumps(
            row, ensure_ascii=False, sort_keys=True
        )
        selected.setdefault(key, deepcopy(row))
    return [selected[key] for key in sorted(selected)]


def provenance_for(event: dict[str, Any]) -> list[dict[str, Any]]:
    existing = event.get("provenance")
    rows = [deepcopy(row) for row in existing or [] if isinstance(row, dict)]
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


def occurrence_id_for(
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
    elif len(descriptions) == 1 and (
        "exact_text_same_start" in reasons or "exact_title_same_start" in reasons
    ):
        payload = f"text|{start}|{next(iter(descriptions))}"
    elif len(organizers) == 1 and len(ordinals) == 1:
        payload = (
            f"organizer-ordinal|{start}|{next(iter(organizers))}|"
            f"{next(iter(ordinals))}"
        )
    else:
        member_keys = "|".join(sorted(source_record_id(member) for member in members))
        payload = f"members|{start}|{member_keys}"
    return "occ_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def merge_cluster(
    members: list[dict[str, Any]], reasons: list[tuple[str, float]]
) -> dict[str, Any]:
    representative = deepcopy(max(members, key=representative_score))
    reason_names = sorted({reason for reason, _confidence in reasons})
    occurrence_id = occurrence_id_for(members, reason_names)

    representative["id"] = occurrence_id
    representative["occurrence_id"] = occurrence_id
    representative["source_record_id"] = source_record_id(representative)
    representative["provenance"] = []
    for member in members:
        representative["provenance"].extend(provenance_for(member))
    representative["provenance"] = unique_dicts_by_source_record_id(
        representative["provenance"]
    )
    representative["merged_source_count"] = len(representative["provenance"])
    representative["merge_reason"] = reason_names
    representative["merge_confidence"] = min(
        (confidence for _reason, confidence in reasons), default=1.0
    )

    representative["tags"] = sorted(
        {
            str(tag)
            for member in members
            for tag in member.get("tags") or []
            if str(tag).strip()
        }
    )
    for field in ("official_links", "related_links"):
        representative[field] = unique_dicts(
            [
                row
                for member in members
                for row in member.get(field) or []
                if isinstance(row, dict)
            ]
        )

    fill_fields = (
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
    )
    ranked = sorted(members, key=representative_score, reverse=True)
    for field in fill_fields:
        if representative.get(field):
            continue
        for member in ranked:
            if member.get(field):
                representative[field] = deepcopy(member[field])
                break
    return representative


def unique_dicts_by_source_record_id(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("source_record_id") or "") or json.dumps(
            row, ensure_ascii=False, sort_keys=True
        )
        selected.setdefault(key, deepcopy(row))
    return [selected[key] for key in sorted(selected)]


def duplicate_groups(
    events: list[dict[str, Any]],
) -> tuple[list[list[int]], dict[tuple[int, int], tuple[str, float]], list[dict[str, Any]]]:
    union_find = UnionFind(len(events))
    edges: dict[tuple[int, int], tuple[str, float]] = {}
    ambiguous: list[dict[str, Any]] = []
    by_start: dict[str, list[int]] = defaultdict(list)
    for index, event in enumerate(events):
        by_start[str(event.get("starts_at") or "")].append(index)

    for indexes in by_start.values():
        for offset, left_index in enumerate(indexes):
            for right_index in indexes[offset + 1 :]:
                left = events[left_index]
                right = events[right_index]
                reason = same_occurrence_reason(left, right)
                if reason:
                    union_find.union(left_index, right_index)
                    edges[(left_index, right_index)] = reason
                    continue
                left_organizer = normalize_text(left.get("organizer"))
                right_organizer = normalize_text(right.get("organizer"))
                similarity = comparable_similarity(left, right)
                if (
                    left_organizer
                    and left_organizer == right_organizer
                    and similarity >= 0.45
                ):
                    ambiguous.append(
                        {
                            "left_id": left.get("id"),
                            "right_id": right.get("id"),
                            "starts_at": left.get("starts_at"),
                            "organizer": left.get("organizer"),
                            "similarity": round(similarity, 4),
                            "left_title": left.get("title"),
                            "right_title": right.get("title"),
                        }
                    )

    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(events)):
        grouped[union_find.find(index)].append(index)
    groups = sorted(
        (sorted(indexes) for indexes in grouped.values()),
        key=lambda indexes: indexes[0],
    )
    ambiguous.sort(
        key=lambda row: (
            str(row.get("starts_at")),
            str(row.get("organizer")),
            str(row.get("left_id")),
            str(row.get("right_id")),
        )
    )
    return groups, edges, ambiguous[:100]


def deduplicate_events(
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    working = [deepcopy(event) for event in events if isinstance(event, dict)]
    groups, edges, ambiguous = duplicate_groups(working)
    output: list[dict[str, Any]] = []
    cluster_audit: list[dict[str, Any]] = []
    negative_samples: list[dict[str, Any]] = []

    for indexes in groups:
        members = [working[index] for index in indexes]
        if len(members) == 1:
            row = deepcopy(members[0])
            row["source_record_id"] = source_record_id(row)
            row["occurrence_id"] = str(row.get("occurrence_id") or row.get("id"))
            output.append(row)
            continue

        member_edges = [
            reason
            for (left, right), reason in edges.items()
            if left in indexes and right in indexes
        ]
        merged = merge_cluster(members, member_edges)
        output.append(merged)
        cluster_audit.append(
            {
                "cluster_id": merged["occurrence_id"],
                "starts_at": merged.get("starts_at"),
                "title": merged.get("title"),
                "member_count": len(members),
                "member_ids": sorted(str(member.get("id")) for member in members),
                "source_record_ids": sorted(source_record_id(member) for member in members),
                "sources": sorted({str(member.get("source")) for member in members}),
                "reasons": sorted({reason for reason, _confidence in member_edges}),
                "confidence": min(
                    (confidence for _reason, confidence in member_edges), default=1.0
                ),
                "representative_source_record_id": merged["source_record_id"],
            }
        )

    merged_pairs = {
        tuple(sorted((str(row["member_ids"][0]), str(member_id))))
        for row in cluster_audit
        for member_id in row["member_ids"][1:]
    }
    by_start: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in working:
        by_start[str(event.get("starts_at") or "")].append(event)
    for rows in by_start.values():
        for offset, left in enumerate(rows):
            for right in rows[offset + 1 :]:
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
                        "similarity": round(comparable_similarity(left, right), 4),
                        "left_title": left.get("title"),
                        "right_title": right.get("title"),
                    }
                )
                if len(negative_samples) >= 10:
                    break
            if len(negative_samples) >= 10:
                break
        if len(negative_samples) >= 10:
            break

    output.sort(key=lambda row: (str(row.get("starts_at")), str(row.get("title"))))
    collapsed = len(working) - len(output)
    exact_source_duplicate_count = sum(
        "exact_source_record" in row["reasons"] for row in cluster_audit
    )
    audit = {
        "schema_version": "1.0",
        "policy_version": "canonical-occurrence.v1",
        "event_count_before": len(working),
        "event_count_after": len(output),
        "candidate_cluster_count": len(cluster_audit),
        "duplicate_cluster_count": len(cluster_audit),
        "duplicate_occurrence_count": collapsed,
        "duplicate_post_count": collapsed,
        "duplicate_rate": round(collapsed / len(working), 6) if working else 0.0,
        "exact_source_duplicate_count": exact_source_duplicate_count,
        "unresolved_ambiguous_cluster_count": len(ambiguous),
        "clusters": sorted(cluster_audit, key=lambda row: str(row["cluster_id"])),
        "ambiguous_candidates": ambiguous,
        "negative_samples": negative_samples,
    }
    return output, audit


def event_from_public_row(row: dict[str, Any]) -> Event:
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


def rewrite_ics(rows: list[dict[str, Any]], generated_at: str, output: Path) -> None:
    instant = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    events = [event_from_public_row(row) for row in rows]
    output.write_text(render_ics(events, instant), encoding="utf-8", newline="")


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
    if not isinstance(rows, list):
        raise ValueError("events document must contain an events array")
    deduped, audit = deduplicate_events(rows)
    generated_at = str(document.get("generated_at") or "")
    if not generated_at:
        raise ValueError("events document must contain generated_at")

    audit["generated_at"] = generated_at
    document["events"] = deduped
    document["count"] = len(deduped)
    document["occurrence_dedup"] = {
        "policy_version": audit["policy_version"],
        "event_count_before": audit["event_count_before"],
        "event_count_after": audit["event_count_after"],
        "duplicate_occurrence_count": audit["duplicate_occurrence_count"],
        "duplicate_cluster_count": audit["duplicate_cluster_count"],
    }

    args.events.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.audit.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rewrite_ics(deduped, generated_at, args.ics)
    print(
        "Occurrence dedup: "
        f"before={audit['event_count_before']} after={audit['event_count_after']} "
        f"collapsed={audit['duplicate_occurrence_count']} "
        f"clusters={audit['duplicate_cluster_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
