"""Fail-closed permission gate for automated Yahoo! realtime retrieval.

Approval is documentary evidence, not an environment toggle. No existing
cache, successful run, or lack of authentication proves redistribution rights.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

POLICY_PATH = Path(__file__).resolve().parents[1] / "config/yahoo_access.json"
ENDPOINT = "https://search.yahoo.co.jp/realtime/search"
REQUIRED_ACTIVITIES = {"automated_collection", "public_redistribution"}


def permission_status(*, policy_path: Path = POLICY_PATH, now: datetime | None = None) -> tuple[bool, str]:
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "permission_record_missing_or_invalid"
    if not isinstance(policy, dict) or policy.get("approved") is not True:
        return False, "permission_unverified"
    if policy.get("authority") != "LINE Yahoo":
        return False, "permission_authority_unverified"
    reference = policy.get("authorization_reference")
    if not isinstance(reference, str) or not reference.startswith("https://"):
        return False, "permission_evidence_missing"
    if policy.get("allowed_endpoint") != ENDPOINT:
        return False, "permission_endpoint_mismatch"
    allowed = policy.get("allowed_activities")
    if not isinstance(allowed, list) or not REQUIRED_ACTIVITIES.issubset(set(allowed)):
        return False, "permission_scope_incomplete"
    try:
        expires = datetime.fromisoformat(str(policy["valid_until"]).replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError):
        return False, "permission_expiry_invalid"
    if expires.tzinfo is None:
        return False, "permission_expiry_invalid"
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if expires.astimezone(UTC) <= current:
        return False, "permission_expired"
    return True, "permission_record_approved"


def require_permission(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "search.yahoo.co.jp" or parsed.path != "/realtime/search":
        raise PermissionError("Yahoo retrieval URL outside approved scope")
    allowed, reason = permission_status()
    if not allowed:
        raise PermissionError(f"Yahoo automated collection disabled: {reason}")
