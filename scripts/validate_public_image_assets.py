from __future__ import annotations

import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import httpx

AUDIT_PATH = Path("public/image-reachability-audit.json")
IMAGE_FIELDS = (
    ("preferred_image_url", "preferred_image_kind"),
    ("vrchat_group_image_url", None),
    ("image_url", "image_kind"),
)


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def probe_image(url: str) -> tuple[bool, str]:
    try:
        with httpx.Client(
            timeout=8,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 cast-event-cal/2", "Range": "bytes=0-0"},
        ) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if not content_type.startswith("image/"):
                    return False, f"unexpected_content_type:{content_type or 'missing'}"
                return True, "ok"
    except httpx.HTTPStatusError as exc:
        return False, f"http_{exc.response.status_code}"
    except httpx.HTTPError as exc:
        return False, type(exc).__name__


def sanitize_event_images(
    events: list[dict[str, Any]],
    *,
    probe: Callable[[str], tuple[bool, str]] = probe_image,
    max_workers: int = 12,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    urls = sorted(
        {
            value
            for event in events
            for field, _kind_field in IMAGE_FIELDS
            if (value := str(event.get(field) or "")).startswith("https://")
        }
    )
    results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(urls) or 1))) as executor:
        futures = {executor.submit(probe, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                results[url] = future.result()
            except Exception as exc:  # fail closed for an optional visual asset
                results[url] = (False, type(exc).__name__)

    failures: Counter[str] = Counter()
    failed_urls: list[dict[str, str]] = []
    for url, (ok, reason) in results.items():
        if not ok:
            failures[reason] += 1
            failed_urls.append({"url": url, "reason": reason})

    sanitized: list[dict[str, Any]] = []
    stripped_fields = 0
    events_degraded = 0
    for event in events:
        row = dict(event)
        degraded = False
        for field, kind_field in IMAGE_FIELDS:
            url = str(row.get(field) or "")
            if url.startswith("https://") and not results.get(url, (False, "not_checked"))[0]:
                row[field] = None
                if kind_field:
                    row[kind_field] = None
                stripped_fields += 1
                degraded = True
        if degraded:
            events_degraded += 1
        sanitized.append(row)

    audit = {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "policy": "fail-closed-for-unreachable-optional-image-assets",
        "checked_url_count": len(urls),
        "reachable_url_count": sum(ok for ok, _reason in results.values()),
        "failed_url_count": len(failed_urls),
        "events_degraded": events_degraded,
        "stripped_image_fields": stripped_fields,
        "failures": dict(sorted(failures.items())),
        "failed_urls": failed_urls,
    }
    return sanitized, audit


def write_audit(audit: dict[str, Any], path: Path = AUDIT_PATH) -> None:
    path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
