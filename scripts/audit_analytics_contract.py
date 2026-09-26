from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "config" / "analytics_event_contract.json"


def load_contract(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("analytics contract must be an object")
    return value


def validate_record(record: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    event_type = str(record.get("event_type") or "")
    spec = contract.get("event_types", {}).get(event_type)
    if not isinstance(spec, dict):
        return [f"unknown_event_type:{event_type or 'missing'}"]
    for field in contract.get("common_required", []):
        if record.get(field) in (None, ""):
            errors.append(f"missing:{field}")
    for field in spec.get("required", []):
        if record.get(field) in (None, ""):
            errors.append(f"missing:{field}")
    if record.get("schema_version") != contract.get("schema_version"):
        errors.append("schema_version_mismatch")
    if record.get("observation_kind") not in contract.get("observation_kinds", []):
        errors.append("invalid_observation_kind")
    if record.get("referrer_state") and record.get("referrer_state") not in contract.get("referrer_states", []):
        errors.append("invalid_referrer_state")
    for field in contract.get("forbidden_fields", []):
        if field in record:
            errors.append(f"forbidden:{field}")
    return sorted(set(errors))


def empty_projection(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": contract["schema_version"],
        "status": "NOT_OBSERVED",
        "event_counts": {name: 0 for name in sorted(contract["event_types"])},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    contract = load_contract(args.contract)
    if args.record is None:
        print(json.dumps(empty_projection(contract), ensure_ascii=False, sort_keys=True))
        return 0
    record = json.loads(args.record.read_text(encoding="utf-8"))
    errors = validate_record(record, contract)
    print(json.dumps({"status": "ok" if not errors else "invalid", "errors": errors}, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
