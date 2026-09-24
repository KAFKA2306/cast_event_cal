from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("public/yahoo-candidate-history.json")
DEFAULT_OUTPUT = Path("build/yahoo-datetime-vocabulary-audit.json")

CLOCK_RE = re.compile(r"(?<!\d)(?:[01]?\d|2[0-3])(?:[:：時]\s*\d{0,2})(?!\d)")
EXPLICIT_DATE_RE = re.compile(
    r"(?:20\d{2}\s*[./／年-]\s*)?\d{1,2}\s*[./／月-]\s*\d{1,2}\s*日?"
)
DDMMYYYY_RE = re.compile(r"(?<!\d)\d{1,2}\s*/\s*\d{1,2}\s*/\s*20\d{2}(?!\d)")
RELATIVE_RE = re.compile(r"本日|今日|明日|今夜|今晩|今週|来週|週末|(?:月|火|水|木|金|土|日)曜日")
RECURRING_RE = re.compile(r"毎(?:週|月|日)|(?:毎週\s*)?(?:月|火|水|木|金|土|日)曜日")
COMMERCE_RE = re.compile(r"販売|発売|セール|BOOTH|プレゼント|キャンペーン", re.IGNORECASE)
ANNOUNCEMENT_RE = re.compile(r"告知|開催(?:します|いたします|予定|決定)?|OPEN|オープン|開場|開始|営業(?:します|予定)?", re.IGNORECASE)
PAST_REPORT_RE = re.compile(r"参加してき|行ってき|楽しかった|昨日|先日|でした|してきました|お邪魔(?:しました|してき)", re.IGNORECASE)
PERSONAL_RE = re.compile(r"仕事|帰宅|寝ます|寝る|出社|改変|お着替え|プレイ時間|VRC(?:に)?(?:います|入る|潜る)", re.IGNORECASE)

EVENT_RE = re.compile(
    r"集会|交流会|イベント|開催|営業|公演|ライブ|撮影会|演奏会|DJ|勉強会|祭|参加|JOIN|"
    r"リクイン|Group\s*[+＋]|グループインスタンス|request\s+invite",
    re.IGNORECASE,
)


def read_candidates(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("candidates", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError("Yahoo candidate history must contain a candidates array")
    return [row for row in rows if isinstance(row, dict)]


def temporal_features(text: str) -> dict[str, bool]:
    return {
        "explicit_date": bool(EXPLICIT_DATE_RE.search(text) or DDMMYYYY_RE.search(text)),
        "clock": bool(CLOCK_RE.search(text)),
        "relative": bool(RELATIVE_RE.search(text)),
        "recurring": bool(RECURRING_RE.search(text)),
    }


def classify_missing_datetime(text: str) -> str:
    features = temporal_features(text)
    if features["recurring"]:
        return "recurring_datetime"
    if features["explicit_date"] and features["clock"]:
        return "explicit_datetime_unsupported"
    if features["relative"] and features["clock"]:
        return "relative_datetime_unsupported"
    if features["explicit_date"] or features["clock"] or features["relative"]:
        return "partial_datetime"
    return "no_datetime_evidence"


def evidence_role(text: str) -> str:
    event = bool(EVENT_RE.search(text))
    commerce = bool(COMMERCE_RE.search(text))
    if event and commerce:
        return "event_and_commerce"
    if event:
        return "event_only"
    if commerce:
        return "commerce_only"
    return "neither"


def occurrence_decision(text: str) -> str:
    """Read-only semantic decision for temporal-evidence candidates.

    This deliberately does not resolve a timestamp. It answers whether the
    temporal evidence is eligible to be associated with an event occurrence.
    """
    features = temporal_features(text)
    if not any(features.values()):
        return "no_datetime_evidence"
    if COMMERCE_RE.search(text) and not EVENT_RE.search(text):
        return "non_event_commerce"
    if PAST_REPORT_RE.search(text):
        return "past_event_or_report"
    if PERSONAL_RE.search(text) and not ANNOUNCEMENT_RE.search(text):
        return "non_event_personal"
    if not EVENT_RE.search(text):
        return "non_event"
    if features["recurring"]:
        return "recurring_event"
    if not ANNOUNCEMENT_RE.search(text):
        return "ambiguous_datetime"
    if (features["explicit_date"] or features["relative"]) and features["clock"]:
        return "resolvable_event_candidate"
    return "partial_datetime"


def build(rows: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = Counter()
    reasons = Counter()
    buckets = Counter()
    roles = Counter()
    bucket_roles: Counter[str] = Counter()
    occurrence_decisions = Counter()
    examples: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        decision = str(row.get("last_decision") or "unknown")
        reason = str(row.get("last_reason") or ("accepted" if decision == "accepted" else "unknown"))
        decisions[decision] += 1
        reasons[reason] += 1
        if reason != "missing_datetime":
            continue
        text = str(row.get("text") or row.get("text_excerpt") or "")
        bucket = classify_missing_datetime(text)
        role = evidence_role(text)
        buckets[bucket] += 1
        roles[role] += 1
        bucket_roles[f"{bucket}:{role}"] += 1
        if bucket != "no_datetime_evidence":
            occurrence_decisions[occurrence_decision(text)] += 1
        sample = examples.setdefault(bucket, [])
        if len(sample) < 5:
            sample.append({
                "status_id": str(row.get("status_id") or ""),
                "url": str(row.get("url") or ""),
                "role": role,
                "text_excerpt": re.sub(r"\s+", " ", text).strip()[:240],
            })

    missing = reasons["missing_datetime"]
    classified = sum(buckets.values())
    temporal = missing - buckets["no_datetime_evidence"]
    return {
        "schema_version": "1.0",
        "policy_version": "issue-196-read-only-audit.v1",
        "candidate_count": len(rows),
        "decision_counts": dict(sorted(decisions.items())),
        "rejection_reason_counts": dict(sorted(reasons.items())),
        "missing_datetime_count": missing,
        "missing_datetime_classified_count": classified,
        "missing_datetime_unclassified_count": missing - classified,
        "temporal_evidence_count": temporal,
        "temporal_evidence_ratio": round(temporal / missing, 6) if missing else 0.0,
        "north_star_min_resolved_count": 2200,
        "north_star_min_resolved_ratio": round(2200 / missing, 6) if missing else 0.0,
        "bucket_counts": dict(sorted(buckets.items())),
        "evidence_role_counts": dict(sorted(roles.items())),
        "bucket_role_counts": dict(sorted(bucket_roles.items())),
        "occurrence_decision_counts": dict(sorted(occurrence_decisions.items())),
        "occurrence_decision_total": sum(occurrence_decisions.values()),
        "temporal_unclassified_count": temporal - sum(occurrence_decisions.values()),
        "examples": {key: examples[key] for key in sorted(examples)},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--assert-complete", action="store_true")
    args = parser.parse_args()
    payload = build(read_candidates(args.input))
    if args.assert_complete and payload["missing_datetime_unclassified_count"] != 0:
        raise SystemExit("missing_datetime audit left unclassified rows")
    if args.assert_complete and payload["temporal_unclassified_count"] != 0:
        raise SystemExit("temporal-evidence audit left unclassified rows")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "Yahoo datetime audit: "
        f"candidates={payload['candidate_count']} missing={payload['missing_datetime_count']} "
        f"temporal={payload['temporal_evidence_count']} unclassified={payload['missing_datetime_unclassified_count']}"
    )
    print("bucket_counts=" + json.dumps(payload["bucket_counts"], ensure_ascii=False, sort_keys=True))
    print("occurrence_decision_counts=" + json.dumps(payload["occurrence_decision_counts"], ensure_ascii=False, sort_keys=True))
    print("evidence_role_counts=" + json.dumps(payload["evidence_role_counts"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
