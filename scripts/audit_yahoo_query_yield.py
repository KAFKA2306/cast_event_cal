from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HISTORY_PATH = Path("public/yahoo-candidate-history.json")
CLASSIFIER_AUDIT_PATH = Path("public/yahoo-classifier-audit.json")
OUTPUT_PATH = Path("public/yahoo-query-yield-audit.json")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("candidates", [])
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def build_query_yield_audit(
    candidates: list[dict[str, Any]], query_results: list[dict[str, Any]]
) -> dict[str, Any]:
    by_query: dict[str, dict[str, Any]] = {}
    candidate_queries: dict[str, set[str]] = {}
    for row in candidates:
        status_id = str(row.get("status_id") or "")
        keys = {str(key) for key in row.get("query_keys", []) if str(key)}
        candidate_queries[status_id] = keys
        for key in keys:
            bucket = by_query.setdefault(key, {
                "observed_candidates": 0,
                "accepted_candidates": 0,
                "rejected_candidates": 0,
                "unique_only_candidates": 0,
                "unique_only_accepted": 0,
                "rejection_reasons": Counter(),
            })
            bucket["observed_candidates"] += 1
            accepted = row.get("last_decision") == "accepted"
            if accepted:
                bucket["accepted_candidates"] += 1
            elif row.get("last_decision") == "rejected":
                bucket["rejected_candidates"] += 1
                bucket["rejection_reasons"][str(row.get("last_reason") or "unknown")] += 1
            if len(keys) == 1:
                bucket["unique_only_candidates"] += 1
                if accepted:
                    bucket["unique_only_accepted"] += 1

    network: dict[str, dict[str, Any]] = {}
    for result in query_results:
        key = str(result.get("key") or "")
        if key:
            network[key] = result

    rows: list[dict[str, Any]] = []
    for key in sorted(set(by_query) | set(network)):
        counts = by_query.get(key, {})
        net = network.get(key, {})
        observed = int(counts.get("observed_candidates", 0))
        accepted = int(counts.get("accepted_candidates", 0))
        rejected = int(counts.get("rejected_candidates", 0))
        unique_only = int(counts.get("unique_only_candidates", 0))
        unique_accepted = int(counts.get("unique_only_accepted", 0))
        raw = net.get("raw_candidates")
        html_bytes = net.get("html_bytes")
        duration_ms = net.get("duration_ms")
        reasons = counts.get("rejection_reasons", Counter())
        missing_datetime = int(reasons.get("missing_datetime", 0))

        if unique_accepted > 0:
            classification = "productive"
        elif accepted > 0 and unique_only == 0:
            classification = "redundant"
        elif observed >= 10 and rejected and missing_datetime / rejected >= 0.75:
            classification = "high-noise"
        else:
            classification = "insufficient-evidence"

        row = {
            "query_key": key,
            "group": net.get("group"),
            "term": net.get("term"),
            "classification": classification,
            "observed_candidates": observed,
            "accepted_candidates": accepted,
            "rejected_candidates": rejected,
            "unique_only_candidates": unique_only,
            "unique_only_accepted": unique_accepted,
            "duplicate_discovery_candidates": max(0, observed - unique_only),
            "rejection_reasons": dict(sorted(reasons.items())),
            "missing_datetime_rejections": missing_datetime,
            "raw_candidates": raw,
            "duration_ms": duration_ms,
            "response_bytes": html_bytes,
            "accepted_per_request": accepted if net.get("status") == "ok" else None,
            "accepted_per_mb": (
                round(accepted / (int(html_bytes) / 1_000_000), 6)
                if isinstance(html_bytes, int) and html_bytes > 0 else None
            ),
            "coverage_evidence": "unavailable",
        }
        rows.append(row)

    return {
        "schema_version": "1.0",
        "policy": {
            "read_only": True,
            "auto_disable_queries": False,
            "coverage_evidence_required_before_removal": True,
            "classification_is_review_candidate_only": True,
        },
        "candidate_count": len(candidates),
        "query_count": len(rows),
        "queries": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, default=HISTORY_PATH)
    parser.add_argument("--classifier-audit", type=Path, default=CLASSIFIER_AUDIT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args(argv)

    candidates = _rows(read_json(args.history, []))
    classifier_audit = read_json(args.classifier_audit, {})
    query_results = classifier_audit.get("query_results", []) if isinstance(classifier_audit, dict) else []
    payload = build_query_yield_audit(candidates, query_results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
