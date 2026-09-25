from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
MAX_EVIDENCE_DISTANCE = timedelta(days=7)
STRONG_CONTEXT_DISTANCE = timedelta(days=3)

STATUS_ID_RE = re.compile(r"\d{10,25}")
GROUP_ID_RE = re.compile(r"\bgrp_[0-9a-f-]{8,}\b", re.IGNORECASE)
HASHTAG_RE = re.compile(r"#([0-9A-Za-z_ぁ-んァ-ヶ一-龠]+)")
QUOTED_NAME_RE = re.compile(r"[「『【《〈](?P<name>[^」』】》〉]{3,48})[」』】》〉]")
TEXT_URL_RE = re.compile(r"https?://[^\s<>'\"）】]+", re.IGNORECASE)
EXPLICIT_DATE_RE = re.compile(
    r"(?<!\d)(?:(?P<year>20\d{2})\s*[./／年-]\s*)?"
    r"(?P<month>1[0-2]|0?[1-9])\s*(?:[./／-]|\s*月\s*)\s*"
    r"(?P<day>3[01]|[12]?\d)\s*日?(?!\d)"
)
COLON_CLOCK_RE = re.compile(
    r"(?<!\d)(?P<hour>[01]?\d|2[0-3])[:：](?P<minute>[0-5]?\d)(?!\d)"
)
JAPANESE_CLOCK_RE = re.compile(
    r"(?P<period>午前|午後|夜)?\s*(?P<hour>[01]?\d|2[0-3])\s*時"
    r"\s*(?:(?P<minute>[0-5]?\d)\s*分?|(?P<half>半))?"
)
RELATIVE_DAY_RE = re.compile(r"本日|今日|明日|今夜|今晩|この後")
STRONG_EVENT_SIGNAL_RE = re.compile(
    r"開催|OPEN|オープン|開場|開始|営業|JOIN|ジョイン|リクイン|request\s+invite|"
    r"Group\s*[+＋]|グループインスタンス|参加方法|ご参加ください|参加してください|"
    r"集合|入場|会場|お越しください|ご来場|ご来店",
    re.IGNORECASE,
)
GENERIC_HASHTAGS = {
    "vrchat",
    "vrc",
    "vrchatjp",
    "vrchat_jp",
    "vrchatイベント",
    "vrcイベント",
}
GENERIC_QUOTED_NAMES = {
    "イベント",
    "交流会",
    "集会",
    "営業",
    "vrchat",
    "vrc",
}
IGNORED_LINK_HOSTS = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "t.co",
    "booth.pm",
    "www.booth.pm",
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
}


@dataclass(frozen=True)
class EvidenceNode:
    status_id: str
    anchor: datetime
    text: str


@dataclass(frozen=True)
class CorroboratedResolution:
    event_at: datetime
    method: str
    anchor: datetime
    event_fingerprint: str
    corroborating_source_ids: tuple[str, ...]

    def evidence(self, utc_text: Callable[[datetime], str]) -> dict[str, Any]:
        return {
            "method": self.method,
            "anchor": utc_text(self.anchor),
            "resolved_at": utc_text(self.event_at),
            "timezone": "Asia/Tokyo",
            "event_fingerprint": self.event_fingerprint,
            "corroborating_source_ids": list(self.corroborating_source_ids),
        }


def _normalize_identity(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", "", normalized).strip("_-・:：")


def _status_value(row: dict[str, Any], key: str) -> str | None:
    value = str(row.get(key) or "").strip()
    return value if STATUS_ID_RE.fullmatch(value) else None


def _canonical_link(value: str) -> str | None:
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold()
    if parsed.scheme not in {"http", "https"} or not host or host in IGNORED_LINK_HOSTS:
        return None
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/")
    if path in {"", "/"}:
        return None
    return urlunsplit(("https", host, path, "", ""))


def _linked_urls(row: dict[str, Any], text: str) -> set[str]:
    raw_values: set[str] = set(TEXT_URL_RE.findall(text))
    supplied = row.get("linked_urls")
    if isinstance(supplied, list):
        raw_values.update(str(value) for value in supplied if isinstance(value, str))
    return {
        canonical
        for raw in raw_values
        if (canonical := _canonical_link(raw)) is not None
    }


def event_fingerprints(row: dict[str, Any]) -> set[str]:
    text = str(row.get("text") or row.get("text_excerpt") or "")
    author = _normalize_identity(str(row.get("author") or "").lstrip("@"))
    fingerprints: set[str] = set()

    status_id = _status_value(row, "status_id")
    conversation_id = _status_value(row, "conversation_id")
    in_reply_to = _status_value(row, "in_reply_to_status_id")
    quoted = _status_value(row, "quoted_status_id")

    if status_id:
        fingerprints.add(f"status:{status_id}")
    if conversation_id:
        fingerprints.add(f"thread:{conversation_id}")
    if in_reply_to:
        fingerprints.add(f"status:{in_reply_to}")
    if quoted:
        fingerprints.add(f"status:{quoted}")

    tags = {
        tag
        for raw in HASHTAG_RE.findall(text)
        if len(tag := _normalize_identity(raw)) >= 3 and tag not in GENERIC_HASHTAGS
    }
    names = {
        name
        for match in QUOTED_NAME_RE.finditer(text)
        if len(name := _normalize_identity(match.group("name"))) >= 3
        and name not in GENERIC_QUOTED_NAMES
    }
    series_tokens = {f"hashtag:{tag}" for tag in tags} | {f"name:{name}" for name in names}

    links = _linked_urls(row, text)
    combined_group_text = " ".join([text, *sorted(links)])
    group_ids = {group_id.casefold() for group_id in GROUP_ID_RE.findall(combined_group_text)}

    if author:
        for token in series_tokens:
            fingerprints.add(f"{author}|{token}")
        for group_id in group_ids:
            fingerprints.add(f"{author}|group:{group_id}")
        for linked_url in links:
            fingerprints.add(f"{author}|url:{linked_url}")

    # Cross-author evidence requires both a shared platform/link identity and a
    # shared event/series identity. A Group or community URL alone can host
    # multiple events and is not sufficient to inherit a date or clock.
    for token in series_tokens:
        for group_id in group_ids:
            fingerprints.add(f"group:{group_id}|{token}")
        for linked_url in links:
            fingerprints.add(f"url:{linked_url}|{token}")

    return fingerprints


def _evidence_window(fingerprint: str) -> timedelta:
    if fingerprint.startswith(("status:", "thread:")):
        return MAX_EVIDENCE_DISTANCE
    if "group:" in fingerprint or "url:" in fingerprint:
        return STRONG_CONTEXT_DISTANCE
    return MAX_EVIDENCE_DISTANCE


def _nearby_nodes(
    graph: dict[str, list[EvidenceNode]],
    fingerprint: str,
    anchor: datetime,
) -> list[EvidenceNode]:
    limit = _evidence_window(fingerprint)
    return [
        node
        for node in graph.get(fingerprint, [])
        if abs(node.anchor - anchor) <= limit
    ]


def build_evidence_graph(
    rows: list[dict[str, Any]],
    *,
    anchor_for: Callable[[dict[str, Any]], datetime],
) -> dict[str, list[EvidenceNode]]:
    graph: dict[str, list[EvidenceNode]] = {}
    for row in rows:
        status_id = str(row.get("status_id") or "")
        if not status_id:
            continue
        text = str(row.get("text") or row.get("text_excerpt") or "")
        node = EvidenceNode(status_id=status_id, anchor=anchor_for(row), text=text)
        for fingerprint in event_fingerprints(row):
            graph.setdefault(fingerprint, []).append(node)
    for nodes in graph.values():
        nodes.sort(key=lambda item: (item.anchor, item.status_id))
    return graph


def _explicit_dates(text: str, anchor: datetime) -> set[date]:
    results: set[date] = set()
    for match in EXPLICIT_DATE_RE.finditer(unicodedata.normalize("NFKC", text)):
        year = int(match.group("year") or anchor.year)
        month = int(match.group("month"))
        day = int(match.group("day"))
        try:
            value = date(year, month, day)
        except ValueError:
            continue
        if not match.group("year") and value < (anchor.date() - timedelta(days=2)):
            if anchor.month == 12 and month == 1:
                try:
                    value = date(anchor.year + 1, month, day)
                except ValueError:
                    continue
        results.add(value)
    for match in RELATIVE_DAY_RE.finditer(text):
        offset = 1 if match.group(0) == "明日" else 0
        results.add((anchor + timedelta(days=offset)).date())
    return results


def _normalize_hour(period: str | None, hour: int) -> int | None:
    if period == "午前":
        if hour == 12:
            return 0
        return hour if 0 <= hour <= 11 else None
    if period == "午後":
        if hour == 12:
            return 12
        return hour + 12 if 0 <= hour <= 11 else None
    if period == "夜":
        if hour == 12:
            return None
        return hour + 12 if 1 <= hour <= 11 else None
    return hour


def _clocks(text: str) -> set[tuple[int, int]]:
    results: set[tuple[int, int]] = set()
    normalized = unicodedata.normalize("NFKC", text)

    occupied: list[tuple[int, int]] = []
    for match in JAPANESE_CLOCK_RE.finditer(normalized):
        hour = _normalize_hour(match.group("period"), int(match.group("hour")))
        if hour is None:
            continue
        minute = 30 if match.group("half") else int(match.group("minute") or 0)
        results.add((hour, minute))
        occupied.append((match.start(), match.end()))

    for match in COLON_CLOCK_RE.finditer(normalized):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        results.add((int(match.group("hour")), int(match.group("minute"))))
    return results


def corroboration_blocker(
    row: dict[str, Any],
    *,
    graph: dict[str, list[EvidenceNode]],
    anchor: datetime,
    actual_now: datetime,
) -> str:
    if resolve_corroborated_datetime(
        row,
        graph=graph,
        anchor=anchor,
        actual_now=actual_now,
    ) is not None:
        return "resolvable"

    fingerprints = sorted(event_fingerprints(row))
    if not fingerprints:
        return "no_event_fingerprint"

    peer_groups = [
        _nearby_nodes(graph, fingerprint, anchor)
        for fingerprint in fingerprints
    ]
    peer_groups = [
        nodes
        for nodes in peer_groups
        if len({node.status_id for node in nodes}) >= 2
    ]
    if not peer_groups:
        return "no_peer_evidence"

    signaled = [
        nodes
        for nodes in peer_groups
        if any(STRONG_EVENT_SIGNAL_RE.search(node.text) for node in nodes)
    ]
    if not signaled:
        return "no_strong_event_signal"

    date_ready: list[tuple[list[EvidenceNode], set[date]]] = []
    for nodes in signaled:
        dates: set[date] = set()
        for node in nodes:
            dates.update(_explicit_dates(node.text, node.anchor))
        if len(dates) == 1:
            date_ready.append((nodes, dates))
    if not date_ready:
        return "missing_or_conflicting_date"

    clock_ready: list[tuple[list[EvidenceNode], set[date], set[tuple[int, int]]]] = []
    for nodes, dates in date_ready:
        clocks: set[tuple[int, int]] = set()
        for node in nodes:
            clocks.update(_clocks(node.text))
        if len(clocks) == 1:
            clock_ready.append((nodes, dates, clocks))
    if not clock_ready:
        return "missing_or_conflicting_clock"

    current_id = str(row.get("status_id") or "")
    cross_source = False
    within_window = False
    now_jst = actual_now.astimezone(JST)
    for nodes, dates, clocks in clock_ready:
        evidence_ids = {node.status_id for node in nodes}
        if current_id not in evidence_ids or len(evidence_ids) < 2:
            continue
        cross_source = True
        event_date = next(iter(dates))
        hour, minute = next(iter(clocks))
        event_at = datetime(
            event_date.year,
            event_date.month,
            event_date.day,
            hour,
            minute,
            tzinfo=JST,
        )
        if now_jst - timedelta(hours=12) <= event_at <= now_jst + timedelta(days=180):
            within_window = True
            break
    if not cross_source:
        return "single_source_only"
    if not within_window:
        return "out_of_publication_window"
    return "conflicting_fingerprint_resolution"


def resolve_corroborated_datetime(
    row: dict[str, Any],
    *,
    graph: dict[str, list[EvidenceNode]],
    anchor: datetime,
    actual_now: datetime,
) -> CorroboratedResolution | None:
    candidates: list[CorroboratedResolution] = []
    status_id = str(row.get("status_id") or "")

    for fingerprint in sorted(event_fingerprints(row)):
        nearby = _nearby_nodes(graph, fingerprint, anchor)
        if len({node.status_id for node in nearby}) < 2:
            continue
        if not any(STRONG_EVENT_SIGNAL_RE.search(node.text) for node in nearby):
            continue

        dates: set[date] = set()
        clocks: set[tuple[int, int]] = set()
        date_sources: set[str] = set()
        clock_sources: set[str] = set()
        for node in nearby:
            node_dates = _explicit_dates(node.text, node.anchor)
            node_clocks = _clocks(node.text)
            if node_dates:
                dates.update(node_dates)
                date_sources.add(node.status_id)
            if node_clocks:
                clocks.update(node_clocks)
                clock_sources.add(node.status_id)

        if len(dates) != 1 or len(clocks) != 1:
            continue
        evidence_ids = tuple(sorted(date_sources | clock_sources))
        if len(evidence_ids) < 2 or status_id not in evidence_ids:
            continue

        event_date = next(iter(dates))
        hour, minute = next(iter(clocks))
        event_at = datetime(
            event_date.year,
            event_date.month,
            event_date.day,
            hour,
            minute,
            tzinfo=JST,
        )
        now_jst = actual_now.astimezone(JST)
        if event_at < now_jst - timedelta(hours=12):
            continue
        if event_at > now_jst + timedelta(days=180):
            continue
        candidates.append(
            CorroboratedResolution(
                event_at=event_at,
                method="corroborated_event_fingerprint_date_clock",
                anchor=anchor,
                event_fingerprint=fingerprint,
                corroborating_source_ids=evidence_ids,
            )
        )

    unique_times = {item.event_at for item in candidates}
    if len(unique_times) != 1:
        return None
    return sorted(candidates, key=lambda item: item.event_fingerprint)[0]
