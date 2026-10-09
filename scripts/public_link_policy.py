from __future__ import annotations

from urllib.parse import urlsplit

ALLOWED_PUBLIC_SCHEMES = frozenset({"https"})


def safe_public_url(value: object) -> str | None:
    """Return a browser-safe absolute public URL or fail closed.

    Public outbound links are HTTPS-only. Relative URLs belong to internal
    navigation and must not pass through this external-link authority.
    """
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate or candidate.startswith("//"):
        return None
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    if parsed.scheme.lower() not in ALLOWED_PUBLIC_SCHEMES:
        return None
    if not parsed.hostname or parsed.username or parsed.password:
        return None
    try:
        _ = parsed.port
    except ValueError:
        return None
    return candidate


def first_safe_public_url(*values: object) -> str | None:
    for value in values:
        safe = safe_public_url(value)
        if safe is not None:
            return safe
    return None
