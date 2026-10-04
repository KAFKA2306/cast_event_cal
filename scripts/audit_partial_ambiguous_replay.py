from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import fetch_yahoo_realtime as implementation
from scripts import reclassify_yahoo_archive as archive
from scripts import yahoo_evidence_graph as evidence_graph

HISTORY_PATH = Path("public/yahoo-candidate-history.json")
TARGET_DECISIONS = {"partial_datetime", "ambiguous_datetime"}

DEADLINE_RE = re.compile(
    r"応募|募集|申込|申し込み|エントリー|予約|受付|締切|〆切|期限|(?:までに|までの)"
)
PERIOD_RE = re.compile(
    r"開催期間|展示期間|公開期間|営業期間|"
    r"\d{1,2}\s*[./／月-]\s*\d{1,2}\s*日?\s*(?:[〜～~]|から).{0,24}"
    r"\d{1,2}\s*[./／月-]\s*\d{1,2}\s*日?(?:\s*まで)?"
)
MULTI_OCCURRENCE_RE = re.compile(
    r"毎週|隔週|毎月|定期|各日|両日|複数日|全\d+回|"
    r"第\d+回.{0,24}第\d+回|"
    r"\d{1,2}\s*[./／月-]\s*\d{1,2}\s*日?\s*[・,、/&＋+]\s*"
    r"\d{1,2}\s*[./／月-]\s*\d{1,2}\s*日?"
)
PAST_REPORT_RE = re.compile(
    r"開催しました|開催いたしました|終了しました|終了いたしました|"
    r"ご参加ありがとうございました|ご来場ありがとうございました|"
    r"活動報告|開催報告|イベントレポート|先日|昨日"
)


def fingerprint_family(value: str) -> str:
    """Map concrete fingerprints to stable audit-only identity families."""
    if value.startswith(("thread:", "status:")):
        return "thread"
    if value.startswith("eventtitle:"):
        return "event_title"
    if value.startswith("officialurl:") or value.startswith("url:") or "|url:" in value or "|shorturl:" in value:
        return "url"
    if value.startswith(("group:", "groupcode:")) or "|group:" in value or "|groupcode:" in value:
        return "vrchat_group"
    if "|" in value and ("|hashtag:" in value or "|name:" in value):
        return "author_series"
    return "other"


def fingerprint_kind(value: str) -> str:
    if "|" in value:
        return "scoped_composite"
    return value.split(":", 1)[0] if ":" in value else "other"


def date_blocker_detail(
    row: dict[str, Any],
    *,
    graph: dict[str, list[evidence_graph.EvidenceNode]],
    anchor: Any,
) -> str:
    """Distinguish absent date evidence from genuinely conflicting dates."""
    peer_groups = [
        evidence_graph._nearby_nodes(graph, fingerprint, anchor)
        for fingerprint in sorted(evidence_graph.event_fingerprints(row))
    ]
    peer_groups = [
        nodes for nodes in peer_groups if len({node.status_id for node in nodes}) >= 2
    ]
    signaled = [
        nodes
        for nodes in peer_groups
        if any(evidence_graph.STRONG_EVENT_SIGNAL_RE.search(node.text) for node in nodes)
    ]
    date_sets = []
    for nodes in signaled:
        dates = set()
        for node in nodes:
            dates.update(evidence_graph._explicit_dates(node.text, node.anchor))
        date_sets.append(dates)
    if not any(date_sets):
        return "missing_date"
    if any(len(dates) > 1 for dates in date_sets):
        return "conflicting_date"
    return "missing_date"


def conflicting_date_context(
    row: dict[str, Any],
    *,
    graph: dict[str, list[evidence_graph.EvidenceNode]],
    anchor: Any,
) -> tuple[list[evidence_graph.EvidenceNode], list[str]]:
    """Return peer evidence groups that actually contain more than one date."""
    nodes_by_id: dict[str, evidence_graph.EvidenceNode] = {}
    fingerprints: list[str] = []
    for fingerprint in sorted(evidence_graph.event_fingerprints(row)):
        nodes = evidence_graph._nearby_nodes(graph, fingerprint, anchor)
        if len({node.status_id for node in nodes}) < 2:
            continue
        if not any(evidence_graph.STRONG_EVENT_SIGNAL_RE.search(node.text) for node in nodes):
            continue
        dates = {
            event_date
            for node in nodes
            for event_date in evidence_graph._explicit_dates(node.text, node.anchor)
        }
        if len(dates) <= 1:
            continue
        fingerprints.append(fingerprint)
        for node in nodes:
            nodes_by_id[node.status_id] = node
    return (
        sorted(nodes_by_id.values(), key=lambda item: (item.anchor, item.status_id)),
        fingerprints,
    )


def classify_conflicting_date_semantics(
    row: dict[str, Any],
    *,
    graph: dict[str, list[evidence_graph.EvidenceNode]],
    anchor: Any,
) -> tuple[str, list[str], list[str]]:
    """Classify conflicting-date evidence without changing publication decisions."""
    nodes, fingerprints = conflicting_date_context(row, graph=graph, anchor=anchor)
    texts = [node.text for node in nodes]
    if not texts:
        texts = [str(row.get("text") or row.get("text_excerpt") or "")]
    combined = "\n".join(texts)

    if DEADLINE_RE.search(combined):
        semantic = "application_or_recruitment_deadline"
    elif PERIOD_RE.search(combined):
        semantic = "event_period"
    elif PAST_REPORT_RE.search(combined):
        semantic = "past_event_or_activity_report"
    else:
        unique_dates = {
            event_date
            for node in nodes
            for event_date in evidence_graph._explicit_dates(node.text, node.anchor)
        }
        dated_occurrence_nodes = sum(
            bool(evidence_graph._explicit_dates(node.text, node.anchor))
            and bool(evidence_graph.STRONG_EVENT_SIGNAL_RE.search(node.text))
            for node in nodes
        )
        if MULTI_OCCURRENCE_RE.search(combined) or (
            len(unique_dates) > 1 and dated_occurrence_nodes >= 2
        ):
            semantic = "multiple_occurrences"
        elif evidence_graph.STRONG_EVENT_SIGNAL_RE.search(combined):
            semantic = "event_occurrence"
        else:
            semantic = "other_or_undetermined"

    families = sorted({fingerprint_family(value) for value in fingerprints})
    return semantic, families, fingerprints


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
    evidence_graph.add_external_event_evidence(
        graph, implementation.read_array(archive.EXTERNAL_EVENTS_PATH)
    )
    x_ids = implementation.known_x_ids(implementation.read_array(implementation.X_EVENTS_PATH))
    accepted, _rejected, evaluated = archive.reclassify(
        history,
        actual_now=replay_now,
        x_ids=x_ids,
        external_events=implementation.read_array(archive.EXTERNAL_EVENTS_PATH),
    )

    target_rows = [
        row for row in evaluated
        if str(row.get("publishability_decision") or "") in TARGET_DECISIONS
    ]
    decision_counts = Counter(str(row.get("publishability_decision") or "") for row in target_rows)
    blocker_counts = Counter(str(row.get("resolution_blocker") or "none") for row in target_rows)
    blocker_by_decision: dict[str, Counter[str]] = {decision: Counter() for decision in sorted(TARGET_DECISIONS)}
    identity_by_blocker: dict[str, Counter[str]] = {}
    date_blocker_counts: Counter[str] = Counter()
    conflicting_semantics: Counter[str] = Counter()
    conflicting_fingerprint_families: Counter[str] = Counter()
    conflicting_semantics_by_family: dict[str, Counter[str]] = {}
    conflicting_fingerprints: Counter[str] = Counter()
    conflicting_samples: dict[str, list[dict[str, Any]]] = {}
    for row in target_rows:
        decision = str(row.get("publishability_decision") or "")
        blocker = str(row.get("resolution_blocker") or "none")
        blocker_by_decision[decision][blocker] += 1
        kinds = {fingerprint_kind(str(value)) for value in row.get("event_fingerprints") or []}
        bucket = identity_by_blocker.setdefault(blocker, Counter())
        if not kinds:
            bucket["none"] += 1
        for kind in kinds:
            bucket[kind] += 1
        if blocker == "missing_or_conflicting_date":
            row_anchor = archive.source_anchor(row, replay_now)
            detail = date_blocker_detail(
                row,
                graph=graph,
                anchor=row_anchor,
            )
            date_blocker_counts[detail] += 1
            if detail == "conflicting_date":
                semantic, families, fingerprints = classify_conflicting_date_semantics(
                    row,
                    graph=graph,
                    anchor=row_anchor,
                )
                conflicting_semantics[semantic] += 1
                for family in families or ["other"]:
                    conflicting_fingerprint_families[family] += 1
                    conflicting_semantics_by_family.setdefault(family, Counter())[semantic] += 1
                for fingerprint in set(fingerprints):
                    conflicting_fingerprints[fingerprint] += 1
                sample_bucket = conflicting_samples.setdefault(semantic, [])
                if len(sample_bucket) < 5:
                    sample_bucket.append({
                        "status_id": str(row.get("status_id") or ""),
                        "fingerprint_families": families,
                        "event_fingerprints": fingerprints,
                        "text_excerpt": str(row.get("text") or row.get("text_excerpt") or "")[:220],
                    })

    promoted = [event for event in accepted if str(event.get("date_resolution_method") or "").startswith("corroborated_")]
    promotions_without_provenance = [
        str(event.get("source_status_id") or event.get("source_id") or "")
        for event in promoted
        if not event.get("date_resolution_evidence")
    ]

    no_peer = blocker_counts.get("no_peer_evidence", 0)
    evidence_graph_matched = len(target_rows) - no_peer
    evidence_graph_conflicted = blocker_counts.get("conflicting_fingerprint_resolution", 0)
    enriched_unresolved = evidence_graph_matched

    samples: dict[str, list[dict[str, Any]]] = {}
    for row in target_rows:
        blocker = str(row.get("resolution_blocker") or "none")
        bucket = samples.setdefault(blocker, [])
        if len(bucket) >= 5:
            continue
        bucket.append({
            "status_id": str(row.get("status_id") or ""),
            "decision": str(row.get("publishability_decision") or ""),
            "event_fingerprints": list(row.get("event_fingerprints") or []),
            "text_excerpt": str(row.get("text") or row.get("text_excerpt") or "")[:220],
        })

    return {
        "schema_version": "1.3",
        "resolver_version": "partial-ambiguous-replay-v1",
        "replay_generated_at": implementation.utc_text(replay_now),
        "input_partial": decision_counts.get("partial_datetime", 0),
        "input_ambiguous": decision_counts.get("ambiguous_datetime", 0),
        "input_total": len(target_rows),
        "evidence_graph_matched": evidence_graph_matched,
        "evidence_graph_conflicted": evidence_graph_conflicted,
        "newly_resolved_partial": 0,
        "newly_resolved_ambiguous": 0,
        "enriched_unresolved": enriched_unresolved,
        "confirmed_non_event": 0,
        "past_only": blocker_counts.get("out_of_publication_window", 0),
        "resolution_blocker_counts": dict(sorted(blocker_counts.items())),
        "resolution_blocker_counts_by_decision": {
            decision: dict(sorted(counts.items())) for decision, counts in blocker_by_decision.items()
        },
        "fingerprint_kind_counts_by_blocker": {
            blocker: dict(sorted(counts.items())) for blocker, counts in sorted(identity_by_blocker.items())
        },
        "date_blocker_detail_counts": dict(sorted(date_blocker_counts.items())),
        "conflicting_date_semantic_counts": dict(sorted(conflicting_semantics.items())),
        "conflicting_date_fingerprint_family_counts": dict(
            sorted(conflicting_fingerprint_families.items())
        ),
        "conflicting_date_semantic_counts_by_fingerprint_family": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(conflicting_semantics_by_family.items())
        },
        "top_conflicting_date_fingerprints": [
            {"fingerprint": fingerprint, "count": count}
            for fingerprint, count in sorted(
                conflicting_fingerprints.items(),
                key=lambda item: (-item[1], item[0]),
            )[:50]
        ],
        "conflicting_date_samples": {
            key: conflicting_samples[key] for key in sorted(conflicting_samples)
        },
        "corroborated_promotions": len(promoted),
        "promotions_without_provenance": len(promotions_without_provenance),
        "promotion_ids_without_provenance": promotions_without_provenance,
        "blocker_samples": {key: samples[key] for key in sorted(samples)},
    }


def assert_safety(report: dict[str, Any]) -> None:
    assert report["input_total"] == report["input_partial"] + report["input_ambiguous"]
    assert report["evidence_graph_matched"] + report["resolution_blocker_counts"].get("no_peer_evidence", 0) == report["input_total"]
    assert sum(report["date_blocker_detail_counts"].values()) == report[
        "resolution_blocker_counts"
    ].get("missing_or_conflicting_date", 0)
    assert sum(report["conflicting_date_semantic_counts"].values()) == report[
        "date_blocker_detail_counts"
    ].get("conflicting_date", 0)
    assert report["promotions_without_provenance"] == 0, report["promotion_ids_without_provenance"]


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
