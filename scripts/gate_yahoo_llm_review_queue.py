from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

QUEUE_PATH = Path("data/yahoo_llm_review_queue.json")
AUDIT_PATH = Path("public/yahoo-llm-review-queue-audit.json")
VOLATILE_ITEM_KEYS = {"first_queued_at", "last_queued_at"}


def semantic_projection(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("queue items must be an array")
    normalized = []
    for item in items:
        if not isinstance(item, dict) or not item.get("status_id"):
            raise ValueError("queue item must contain status_id")
        normalized.append({k: v for k, v in item.items() if k not in VOLATILE_ITEM_KEYS})
    normalized.sort(key=lambda row: str(row["status_id"]))
    return {
        "schema_version": payload.get("schema_version"),
        "policy": payload.get("policy"),
        "items": normalized,
    }


def semantic_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        semantic_projection(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def head_payload(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "show", f"HEAD:{path.as_posix()}"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise ValueError(f"HEAD:{path} must contain an object")
    return payload


def gate(queue_path: Path = QUEUE_PATH, audit_path: Path = AUDIT_PATH) -> bool:
    current = load_payload(queue_path)
    previous = head_payload(queue_path)
    if semantic_hash(current) != semantic_hash(previous):
        return True
    subprocess.run(["git", "restore", "--source=HEAD", "--", str(queue_path), str(audit_path)], check=True)
    return False


def main() -> int:
    changed = gate()
    print("Yahoo LLM review queue semantic change:", "yes" if changed else "no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
