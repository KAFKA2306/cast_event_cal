from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_HISTORY = Path("public/yahoo-candidate-history.json")
DEFAULT_OUTPUT = Path("public/yahoo-query-expert-model.json")
Z_95 = 1.959963984540054


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def wilson_lower(successes: int, total: int, z: float = Z_95) -> float:
    if total <= 0:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denominator)


def candidate_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("candidates", [])
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)]


def is_accepted(row: dict[str, Any]) -> bool:
    return str(row.get("last_decision") or row.get("decision") or "").casefold() == "accepted"


def query_keys(row: dict[str, Any]) -> list[str]:
    values = row.get("query_keys") or []
    return sorted({str(value).strip() for value in values if str(value).strip()})


def build_model(
    rows: list[dict[str, Any]],
    *,
    minimum_support: int = 20,
    minimum_accepted: int = 2,
    minimum_wilson_precision: float = 0.05,
    minimum_ensemble_coverage: float = 0.90,
) -> dict[str, Any]:
    observations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    accepted_ids: set[str] = set()
    for row in rows:
        status_id = str(row.get("status_id") or "")
        if is_accepted(row) and status_id:
            accepted_ids.add(status_id)
        for key in query_keys(row):
            observations[key].append(row)

    experts: list[dict[str, Any]] = []
    expert_positive_ids: dict[str, set[str]] = {}
    for key, seen in observations.items():
        positives = [row for row in seen if is_accepted(row)]
        positive_ids = {str(row.get("status_id")) for row in positives if row.get("status_id")}
        support = len(seen)
        accepted = len(positives)
        precision = accepted / support if support else 0.0
        lower = wilson_lower(accepted, support)
        reasons = Counter(str(row.get("last_reason") or row.get("reason") or "accepted") for row in seen)
        eligible = support >= minimum_support and accepted >= minimum_accepted and lower >= minimum_wilson_precision
        if eligible:
            tier = "precision" if lower >= 0.15 else "balanced" if lower >= 0.08 else "recall"
        else:
            tier = "exploration"
        experts.append(
            {
                "query_key": key,
                "support": support,
                "accepted": accepted,
                "rejected": support - accepted,
                "precision": round(precision, 6),
                "wilson_precision_lower_95": round(lower, 6),
                "positive_coverage": round(len(positive_ids) / len(accepted_ids), 6) if accepted_ids else 0.0,
                "tier": tier,
                "eligible": eligible,
                "top_rejection_reasons": dict(reasons.most_common(5)),
            }
        )
        expert_positive_ids[key] = positive_ids

    experts.sort(
        key=lambda row: (
            not row["eligible"],
            -float(row["wilson_precision_lower_95"]),
            -int(row["accepted"]),
            str(row["query_key"]),
        )
    )
    promoted = [row for row in experts if row["eligible"]]
    covered = set().union(*(expert_positive_ids[row["query_key"]] for row in promoted)) if promoted else set()
    ensemble_coverage = len(covered) / len(accepted_ids) if accepted_ids else 0.0

    ablations: list[dict[str, Any]] = []
    for expert in promoted:
        remaining = [row for row in promoted if row["query_key"] != expert["query_key"]]
        remaining_ids = set().union(*(expert_positive_ids[row["query_key"]] for row in remaining)) if remaining else set()
        coverage = len(remaining_ids) / len(accepted_ids) if accepted_ids else 0.0
        ablations.append(
            {
                "removed_query_key": expert["query_key"],
                "coverage_without_expert": round(coverage, 6),
                "marginal_positive_coverage": round(ensemble_coverage - coverage, 6),
                "unique_accepted_count": len(covered - remaining_ids),
            }
        )
    ablations.sort(key=lambda row: (-row["marginal_positive_coverage"], row["removed_query_key"]))

    status = "ready" if promoted and ensemble_coverage >= minimum_ensemble_coverage else "insufficient_evidence"
    return {
        "schema_version": "1.0",
        "model_type": "evidence_gated_query_experts",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": status,
        "fail_closed": True,
        "thresholds": {
            "minimum_support": minimum_support,
            "minimum_accepted": minimum_accepted,
            "minimum_wilson_precision": minimum_wilson_precision,
            "minimum_ensemble_coverage": minimum_ensemble_coverage,
        },
        "training_rows": len(rows),
        "accepted_universe_count": len(accepted_ids),
        "promoted_expert_count": len(promoted),
        "ensemble_positive_coverage": round(ensemble_coverage, 6),
        "recommended_query_keys": [row["query_key"] for row in promoted] if status == "ready" else [],
        "experts": experts,
        "leave_one_expert_out_ablation": ablations,
        "promotion_policy": "No production query plan change unless status is ready and regression tests verify all hard validity gates remain unchanged.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an evidence-gated Yahoo query expert ensemble")
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--minimum-support", type=int, default=20)
    parser.add_argument("--minimum-accepted", type=int, default=2)
    parser.add_argument("--minimum-wilson-precision", type=float, default=0.05)
    parser.add_argument("--minimum-ensemble-coverage", type=float, default=0.90)
    args = parser.parse_args()
    payload = build_model(
        candidate_rows(read_json(args.history)),
        minimum_support=args.minimum_support,
        minimum_accepted=args.minimum_accepted,
        minimum_wilson_precision=args.minimum_wilson_precision,
        minimum_ensemble_coverage=args.minimum_ensemble_coverage,
    )
    write_json(args.output, payload)
    print(json.dumps({key: payload[key] for key in ("status", "training_rows", "accepted_universe_count", "promoted_expert_count", "ensemble_positive_coverage")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
