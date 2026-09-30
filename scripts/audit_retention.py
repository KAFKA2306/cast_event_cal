from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "retention-policy.json"


def load_policy(path: Path = POLICY) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if policy.get("default_state") != "UNCLASSIFIED":
        raise ValueError("retention policy must fail closed to UNCLASSIFIED")
    required = {"class", "patterns", "purpose", "authority", "sensitivity", "minimum_required_fields", "retention_basis", "eligibility"}
    for rule in policy.get("rules", []):
        missing = required - set(rule)
        if missing:
            raise ValueError(f"retention rule missing fields: {sorted(missing)}")
    return policy


def classify(path: str, policy: dict) -> dict:
    matches = [rule for rule in policy["rules"] if any(fnmatch.fnmatch(path, pattern) for pattern in rule["patterns"])]
    if len(matches) > 1:
        return {"path": path, "state": "AMBIGUOUS", "classes": [rule["class"] for rule in matches]}
    if not matches:
        return {"path": path, "state": "UNCLASSIFIED"}
    rule = matches[0]
    return {"path": path, "state": "CLASSIFIED", "class": rule["class"], "eligibility": rule["eligibility"], "authority": rule["authority"]}


def inventory(root: Path = ROOT, policy_path: Path = POLICY) -> dict:
    policy = load_policy(policy_path)
    roots = ["data", "public", "artifacts", "reports", ".github/workflows"]
    paths: list[str] = []
    for name in roots:
        base = root / name
        if not base.exists():
            continue
        paths.extend(str(path.relative_to(root)).replace("\\", "/") for path in base.rglob("*") if path.is_file())
    rows = [classify(path, policy) for path in sorted(paths)]
    counts: dict[str, int] = {}
    for row in rows:
        key = row.get("class", row["state"])
        counts[key] = counts.get(key, 0) + 1
    return {"schema_version": policy["schema_version"], "mode": "read_only", "counts": counts, "unclassified": [row["path"] for row in rows if row["state"] == "UNCLASSIFIED"], "ambiguous": [row for row in rows if row["state"] == "AMBIGUOUS"], "records": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only retention inventory; never deletes data")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true", help="fail if a persistent path is unclassified or ambiguous")
    args = parser.parse_args()
    report = inventory()
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    if args.strict and (report["unclassified"] or report["ambiguous"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
