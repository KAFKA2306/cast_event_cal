"""Fail-closed permission gate for automated Yahoo! realtime retrieval.

Operator attestation enables bounded operation without publishing private proof.
It is not independent verification of third-party rights or permanent consent.
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
    if policy.get("allowed_endpoint") != ENDPOINT:
        return False, "permission_endpoint_mismatch"
    allowed = policy.get("allowed_activities")
    if (
        not isinstance(allowed, list)
        or not all(isinstance(value, str) for value in allowed)
        or not REQUIRED_ACTIVITIES.issubset(set(allowed))
    ):
        return False, "permission_scope_incomplete"

    current = (now or datetime.now(UTC)).astimezone(UTC)
    if policy.get("authorization_basis") == "operator_attestation":
        # A private declaration is an operational instruction, not independent
        # documentary proof of the issuer or an assertion of indefinite rights.
        if policy.get("authorization_verification") != "operator_reported_not_independently_verified":
            return False, "permission_attestation_invalid"
        if policy.get("authorization_reference") is not None or policy.get("valid_until") is not None:
            return False, "permission_attestation_conflicting_evidence"
        try:
            review_due = datetime.fromisoformat(
                str(policy["operator_review_due_at"]).replace("Z", "+00:00")
            )
        except (KeyError, ValueError, TypeError):
            return False, "permission_review_invalid"
        if review_due.tzinfo is None:
            return False, "permission_review_invalid"
        if review_due.astimezone(UTC) <= current:
            return False, "permission_review_overdue"
        return True, "operator_attested_review_pending"

    # Documented authorization continues to require a real reference and
    # independently stated expiry. Neither may be invented for a private claim.
    reference = policy.get("authorization_reference")
    if not isinstance(reference, str) or not reference.startswith("https://"):
        return False, "permission_evidence_missing"
    try:
        expires = datetime.fromisoformat(str(policy["valid_until"]).replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError):
        return False, "permission_expiry_invalid"
    if expires.tzinfo is None:
        return False, "permission_expiry_invalid"
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
