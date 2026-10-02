from __future__ import annotations

import argparse
import json
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
            date_blocker_counts[
                date_blocker_detail(
                    row,
                    graph=graph,
                    anchor=archive.source_anchor(row, replay_now),
                )
            ] += 1

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
        "schema_version": "1.2",
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
