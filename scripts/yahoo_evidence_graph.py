from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
MAX_EVIDENCE_DISTANCE = timedelta(days=7)

GROUP_ID_RE = re.compile(r"\bgrp_[0-9a-f-]{8,}\b", re.IGNORECASE)
HASHTAG_RE = re.compile(r"#([0-9A-Za-z_ぁ-んァ-ヶ一-龠]+)")
QUOTED_NAME_RE = re.compile(r"[「『](?P<name>[^」』]{3,48})[」』]")
EXPLICIT_DATE_RE = re.compile(
    r"(?<!\d)(?:(?P<year>20\d{2})\s*[./／年-]\s*)?"
    r"(?P<month>1[0-2]|0?[1-9])\s*(?:[./／-]|\s*月\s*)\s*"
    r"(?P<day>3[01]|[12]?\d)\s*日?(?!\d)"
)
CLOCK_RE = re.compile(
    r"(?<!\d)(?P<hour>[01]?\d|2[0-3])(?:[:：時]\s*(?P<minute>\d{0,2}))(?!\d)"
)
RELATIVE_DAY_RE = re.compile(r"本日|今日|明日|今夜|今晩|この後")
STRONG_EVENT_SIGNAL_RE = re.compile(
    r"開催|OPEN|オープン|開場|開始|営業|JOIN|ジョイン|リクイン|request\s+invite|"
    r"Group\s*[+＋]|グループインスタンス|参加方法|ご参加ください|参加してください",
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


def event_fingerprints(row: dict[str, Any]) -> set[str]:
    author = _normalize_identity(str(row.get("author") or "").lstrip("@"))
    if not author:
        return set()
    text = str(row.get("text") or row.get("text_excerpt") or "")
    fingerprints: set[str] = set()

    for group_id in GROUP_ID_RE.findall(text):
        fingerprints.add(f"{author}|group:{group_id.casefold()}")

    for raw in HASHTAG_RE.findall(text):
        tag = _normalize_identity(raw)
        if len(tag) < 3 or tag in GENERIC_HASHTAGS:
            continue
        fingerprints.add(f"{author}|hashtag:{tag}")

    for match in QUOTED_NAME_RE.finditer(text):
        name = _normalize_identity(match.group("name"))
        if len(name) < 3 or name in GENERIC_QUOTED_NAMES:
            continue
        fingerprints.add(f"{author}|name:{name}")

    return fingerprints


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


def _clocks(text: str) -> set[tuple[int, int]]:
    results: set[tuple[int, int]] = set()
    normalized = unicodedata.normalize("NFKC", text)
    for match in CLOCK_RE.finditer(normalized):
        minute_text = match.group("minute")
        if minute_text and len(minute_text) not in {1, 2}:
            continue
        results.add((int(match.group("hour")), int(minute_text or 0)))
    return results


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
        nearby = [
            node
            for node in graph.get(fingerprint, [])
            if abs(node.anchor - anchor) <= MAX_EVIDENCE_DISTANCE
        ]
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
