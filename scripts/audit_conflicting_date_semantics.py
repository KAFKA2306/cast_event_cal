from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import audit_partial_ambiguous_replay as replay_audit
from scripts import fetch_yahoo_realtime as implementation
from scripts import reclassify_yahoo_archive as archive
from scripts import yahoo_evidence_graph as evidence_graph

HISTORY_PATH = Path("public/yahoo-candidate-history.json")
TARGET_DECISIONS = {"partial_datetime", "ambiguous_datetime"}

DEADLINE_RE = re.compile(
    r"締切|〆切|応募期限|応募期間|募集期限|募集期間|募集終了|受付期限|受付締切|"
    r"エントリー期限|エントリー締切|申込期限|申込締切|申し込み期限|申し込み締切"
)
RANGE_RE = re.compile(
    r"開催期間|会期|期間[：:]|"
    r"\d{1,2}\s*(?:[./／]|月)\s*\d{1,2}\s*日?\s*"
    r"(?:[-~〜～]|から)\s*"
    r"(?:\d{1,2}\s*(?:[./／]|月)\s*)?\d{1,2}\s*日?"
)
MULTI_OCCURRENCE_RE = re.compile(
    r"毎週|毎月|隔週|定期開催|複数回|複数日|両日|各日|全\s*\d+\s*回|"
    r"第\s*\d+\s*回.*第\s*\d+\s*回|"
    r"開催日[：:].{0,80}(?:、|,|・|と|及び|&|＆)"
)
PAST_REPORT_RE = re.compile(
    r"活動報告|開催報告|イベントレポート|レポート|開催しました|開催いたしました|"
    r"終了しました|終了いたしました|ご参加ありがとうございました|"
    r"先日.{0,40}開催|昨日.{0,40}開催|振り返り"
)


def fingerprint_class(value: str) -> str:
    if value.startswith("thread:"):
        return "thread"
    if value.startswith("eventtitle:"):
        return "event_title"
    if value.startswith(("group:", "groupcode:")) or "|group:" in value or "|groupcode:" in value:
        return "vrchat_group"
    if value.startswith(("officialurl:", "url:")) or "|url:" in value or "|shorturl:" in value:
        return "url"
    if "|hashtag:" in value or "|name:" in value:
        return "author_series"
    if value.startswith("status:"):
        return "status"
    return "other"


def conflicting_groups(
    row: dict[str, Any],
    *,
    graph: dict[str, list[evidence_graph.EvidenceNode]],
    anchor: Any,
) -> list[tuple[str, list[evidence_graph.EvidenceNode], set[Any]]]:
    groups: list[tuple[str, list[evidence_graph.EvidenceNode], set[Any]]] = []
    for fingerprint in sorted(evidence_graph.event_fingerprints(row)):
        nodes = evidence_graph._nearby_nodes(graph, fingerprint, anchor)
        if len({node.status_id for node in nodes}) < 2:
            continue
        if not any(evidence_graph.STRONG_EVENT_SIGNAL_RE.search(node.text) for node in nodes):
            continue
        dates = set()
        for node in nodes:
            dates.update(evidence_graph._explicit_dates(node.text, node.anchor))
        if len(dates) > 1:
            groups.append((fingerprint, nodes, dates))
    return groups


def semantic_signals(texts: list[str]) -> set[str]:
    joined = "\n".join(texts)
    signals: set[str] = set()
    if DEADLINE_RE.search(joined):
        signals.add("application_or_recruitment_deadline")
    if RANGE_RE.search(joined):
        signals.add("event_range")
    if MULTI_OCCURRENCE_RE.search(joined):
        signals.add("multiple_occurrences")
    if PAST_REPORT_RE.search(joined):
        signals.add("past_event_or_activity_report")
    if any(evidence_graph.STRONG_EVENT_SIGNAL_RE.search(text) for text in texts):
        signals.add("event_occurrence")
    return signals


def semantic_bucket(signals: set[str]) -> str:
    # Exclusive audit bucket only. Priority is intentionally conservative:
    # non-occurrence date roles win over a generic event signal.
    for bucket in (
        "application_or_recruitment_deadline",
        "event_range",
        "multiple_occurrences",
        "past_event_or_activity_report",
        "event_occurrence",
    ):
        if bucket in signals:
            return bucket
    return "other_or_unknown"


def audit() -> dict[str, Any]:
    payload = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    history = [row for row in payload.get("candidates", []) if isinstance(row, dict)]
    replay_now = implementation.parse_instant(str(payload.get("generated_at") or ""))
    if replay_now is None:
        raise AssertionError("history generated_at is required for deterministic replay")

    archive.configure_archive_classifier()
    graph = evidence_graph.build_evidence_graph(
        history,
        anchor_for=lambda row: archive.source_anchor(row, replay_now),
    )
    external_events = implementation.read_array(archive.EXTERNAL_EVENTS_PATH)
    evidence_graph.add_external_event_evidence(graph, external_events)
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    _accepted, _rejected, evaluated = archive.reclassify(
        history,
        actual_now=replay_now,
        x_ids=x_ids,
        external_events=external_events,
    )

    target_rows = [
        row
        for row in evaluated
        if str(row.get("publishability_decision") or "") in TARGET_DECISIONS
        and str(row.get("resolution_blocker") or "") == "missing_or_conflicting_date"
    ]

    semantic_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    fingerprint_class_row_ids: dict[str, set[str]] = defaultdict(set)
    fingerprint_exact_row_ids: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    conflicting_ids: set[str] = set()

    for row in target_rows:
        anchor = archive.source_anchor(row, replay_now)
        if replay_audit.date_blocker_detail(row, graph=graph, anchor=anchor) != "conflicting_date":
            continue

        groups = conflicting_groups(row, graph=graph, anchor=anchor)
        if not groups:
            raise AssertionError("conflicting_date row has no conflicting fingerprint group")

        status_id = str(row.get("status_id") or "")
        conflicting_ids.add(status_id)

        texts: list[str] = []
        seen_nodes: set[str] = set()
        row_fingerprints: list[str] = []
        row_dates: set[str] = set()
        row_classes: set[str] = set()

        for fingerprint, nodes, dates in groups:
            row_fingerprints.append(fingerprint)
            row_dates.update(value.isoformat() for value in dates)
            klass = fingerprint_class(fingerprint)
            row_classes.add(klass)
            fingerprint_class_row_ids[klass].add(status_id)
            fingerprint_exact_row_ids[fingerprint].add(status_id)
            for node in nodes:
                node_key = f"{node.status_id}|{node.anchor.isoformat()}"
                if node_key in seen_nodes:
                    continue
                seen_nodes.add(node_key)
                texts.append(node.text)

        signals = semantic_signals(texts)
        bucket = semantic_bucket(signals)
        semantic_counts[bucket] += 1
        for signal in signals:
            signal_counts[signal] += 1

        if len(samples[bucket]) < 5:
            samples[bucket].append(
                {
                    "status_id": status_id,
                    "semantic_signals": sorted(signals),
                    "fingerprint_classes": sorted(row_classes),
                    "event_fingerprints": sorted(row_fingerprints),
                    "conflicting_dates": sorted(row_dates),
                    "text_excerpt": str(row.get("text") or row.get("text_excerpt") or "")[:240],
                }
            )

    return {
        "schema_version": "1.0",
        "audit_kind": "conflicting-date-semantics",
        "replay_generated_at": implementation.utc_text(replay_now),
        "input_conflicting_date": len(conflicting_ids),
        "semantic_bucket_counts": dict(sorted(semantic_counts.items())),
        "semantic_signal_counts_nonexclusive": dict(sorted(signal_counts.items())),
        "fingerprint_class_row_counts": {
            key: len(values) for key, values in sorted(fingerprint_class_row_ids.items())
        },
        "fingerprint_exact_row_counts": {
            key: len(values)
            for key, values in sorted(
                fingerprint_exact_row_ids.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
        },
        "samples_by_semantic_bucket": {
            key: samples[key] for key in sorted(samples)
        },
        "publication_changes": 0,
        "events_json_writes": 0,
        "datetime_promotions": 0,
    }


def assert_safety(report: dict[str, Any]) -> None:
    assert report["input_conflicting_date"] == sum(report["semantic_bucket_counts"].values())
    assert report["publication_changes"] == 0
    assert report["events_json_writes"] == 0
    assert report["datetime_promotions"] == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assert-safety", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = audit()
    if args.assert_safety:
        assert_safety(report)

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
