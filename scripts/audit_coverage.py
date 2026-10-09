#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

STATUSES = {"found", "not_found", "unsupported", "source_unavailable"}
REASONS = {
    "query_vocabulary_miss",
    "result_window_ranking_miss",
    "engagement_threshold_miss",
    "parser_miss",
    "classifier_reject",
    "dedupe_identity_mismatch",
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def identities(event):
    return {
        str(event.get(key, ""))
        for key in ("event_identity", "canonical_identity", "id")
        if event.get(key)
    }


def audit(gold, run):
    events = run.get("events", [])
    supported = set(run.get("supported_sources", []))
    unavailable = set(run.get("source_unavailable", []))
    misses = run.get("miss_reasons", {})
    seen = set().union(*(identities(event) for event in events)) if events else set()
    rows = []
    for item in gold["items"]:
        ident = item["event_identity"]
        expected = set(item.get("expected_sources", []))
        status = "found" if ident in seen else None
        reason = None
        if status is None and expected and expected <= unavailable:
            status = "source_unavailable"
        if status is None and supported and expected and not (expected & supported):
            status = "unsupported"
        if status is None:
            status = "not_found"
            reason = misses.get(ident, "query_vocabulary_miss")
            if reason not in REASONS:
                raise ValueError(f"invalid miss reason for {ident}: {reason}")
        rows.append(
            {
                "event_identity": ident,
                "status": status,
                "miss_reason": reason,
                "category": item["category"],
                "expected_sources": sorted(expected),
            }
        )

    def groups(key, values):
        out = {}
        for value in sorted(values):
            subset = [
                row
                for row in rows
                if (
                    row[key] == value
                    if key == "category"
                    else value in row["expected_sources"]
                )
            ]
            measurable = [
                row for row in subset if row["status"] in {"found", "not_found"}
            ]
            found = sum(row["status"] == "found" for row in measurable)
            out[value] = {
                "found": found,
                "measurable": len(measurable),
                "recall": found / len(measurable) if measurable else None,
                "source_unavailable": sum(
                    row["status"] == "source_unavailable" for row in subset
                ),
                "unsupported": sum(row["status"] == "unsupported" for row in subset),
            }
        return out

    categories = {row["category"] for row in rows}
    sources = {source for row in rows for source in row["expected_sources"]}
    return {
        "schema_version": "cast-event-cal.coverage-audit.v1",
        "items": rows,
        "by_category": groups("category", categories),
        "by_source": groups("source", sources),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", default="config/coverage_gold.json")
    parser.add_argument("--run", required=True)
    parser.add_argument("--output")
    parser.add_argument("--baseline-report")
    args = parser.parse_args()
    report = audit(load(args.gold), load(args.run))
    if args.baseline_report:
        base = load(args.baseline_report)
        before = {
            item["event_identity"]: item["status"] for item in base.get("items", [])
        }
        report["delta"] = [
            {
                "event_identity": item["event_identity"],
                "before": before.get(item["event_identity"]),
                "after": item["status"],
            }
            for item in report["items"]
            if before.get(item["event_identity"]) != item["status"]
        ]
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
