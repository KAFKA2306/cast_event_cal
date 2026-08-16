from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

API_ROOT = "https://www.googleapis.com/webmasters/v3/sites"
READONLY_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
ROW_LIMIT = 25_000
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d .()_-]{7,}\d)(?!\d)")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def normalize_query(value: str) -> str:
    return " ".join(value.normalize("NFKC").lower().split()) if hasattr(value, "normalize") else " ".join(value.lower().split())


def normalized(value: str) -> str:
    import unicodedata

    return " ".join(unicodedata.normalize("NFKC", value).lower().split())


def sensitive_query(query: str) -> bool:
    return bool(EMAIL_RE.search(query) or PHONE_RE.search(query))


def position_band(position: float) -> str:
    if position <= 3:
        return "1-3"
    if position <= 10:
        return "4-10"
    if position <= 20:
        return "11-20"
    if position <= 50:
        return "21-50"
    return "51+"


def ratio_delta(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return (current - previous) / previous


def metric_row(row: dict[str, Any] | None) -> dict[str, float]:
    row = row or {}
    return {
        "clicks": float(row.get("clicks", 0.0)),
        "impressions": float(row.get("impressions", 0.0)),
        "ctr": float(row.get("ctr", 0.0)),
        "position": float(row.get("position", 0.0)),
    }


def compare_metrics(current: dict[str, Any] | None, previous: dict[str, Any] | None) -> dict[str, Any]:
    cur = metric_row(current)
    prev = metric_row(previous)
    return {
        "current": cur,
        "previous": prev,
        "delta": {
            "clicks": cur["clicks"] - prev["clicks"],
            "clicks_relative": ratio_delta(cur["clicks"], prev["clicks"]),
            "impressions": cur["impressions"] - prev["impressions"],
            "impressions_relative": ratio_delta(cur["impressions"], prev["impressions"]),
            "ctr": cur["ctr"] - prev["ctr"],
            "ctr_relative": ratio_delta(cur["ctr"], prev["ctr"]),
            "position": cur["position"] - prev["position"],
        },
    }


class SearchConsoleClient:
    def __init__(self, site_url: str, access_token: str) -> None:
        self.site_url = site_url
        self.endpoint = f"{API_ROOT}/{quote(site_url, safe='')}/searchAnalytics/query"
        self.client = httpx.Client(
            timeout=45.0,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )

    def close(self) -> None:
        self.client.close()

    def query(self, body: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(self.endpoint, json=body)
        response.raise_for_status()
        value = response.json()
        if not isinstance(value, dict):
            raise ValueError("Search Console returned a non-object response")
        return value

    def rows(self, start: date, end: date, dimensions: list[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        start_row = 0
        while True:
            response = self.query(
                {
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                    "dimensions": dimensions,
                    "type": "web",
                    "dataState": "final",
                    "rowLimit": ROW_LIMIT,
                    "startRow": start_row,
                }
            )
            batch = response.get("rows") or []
            if not isinstance(batch, list):
                raise ValueError("Search Console rows must be a list")
            rows.extend(row for row in batch if isinstance(row, dict))
            if len(batch) < ROW_LIMIT:
                break
            start_row += len(batch)
        return rows

    def total(self, start: date, end: date) -> dict[str, float]:
        response = self.query(
            {
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "type": "web",
                "dataState": "final",
                "rowLimit": 1,
            }
        )
        rows = response.get("rows") or []
        return metric_row(rows[0] if rows and isinstance(rows[0], dict) else None)

    def latest_finalized_date(self, today: date) -> date | None:
        rows = self.rows(today - timedelta(days=31), today, ["date"])
        dates: list[date] = []
        for row in rows:
            keys = row.get("keys") or []
            if keys:
                try:
                    dates.append(date.fromisoformat(str(keys[0])))
                except ValueError:
                    continue
        return max(dates) if dates else None


def access_token_from_environment() -> str:
    token = os.environ.get("SEARCH_CONSOLE_ACCESS_TOKEN", "").strip()
    if token:
        return token
    raw = os.environ.get("SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError(
            "Search Console credentials are not configured. Set SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON "
            "or SEARCH_CONSOLE_ACCESS_TOKEN."
        )
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("SEARCH_CONSOLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc
    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("service-account auth requires google-auth[requests]") from exc
    credentials = service_account.Credentials.from_service_account_info(info, scopes=[READONLY_SCOPE])
    credentials.refresh(Request())
    if not credentials.token:
        raise RuntimeError("service-account token refresh returned no token")
    return str(credentials.token)


def pair_rows(rows: list[dict[str, Any]]) -> tuple[dict[tuple[str, str], dict[str, Any]], int]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    redacted = 0
    for row in rows:
        keys = row.get("keys") or []
        if len(keys) < 2:
            continue
        query, page = str(keys[0]).strip(), str(keys[1]).strip()
        if not query or not page:
            continue
        if sensitive_query(query):
            redacted += 1
            continue
        result[(query, page)] = row
    return result, redacted


def brand_query(query: str, brand_terms: list[str]) -> bool:
    text = normalized(query)
    return any(normalized(term) in text for term in brand_terms if term.strip())


def ctr_benchmarks(rows: dict[tuple[str, str], dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in rows.values():
        metrics = metric_row(row)
        band = position_band(metrics["position"])
        totals[band][0] += metrics["clicks"]
        totals[band][1] += metrics["impressions"]
    return {
        band: (clicks / impressions if impressions else 0.0)
        for band, (clicks, impressions) in totals.items()
    }


def changes_for_window(changes_doc: dict[str, Any], start: date, end: date) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in changes_doc.get("changes") or []:
        if not isinstance(row, dict):
            continue
        try:
            changed = date.fromisoformat(str(row.get("date")))
        except ValueError:
            continue
        if start <= changed <= end:
            result.append(row)
    return result


def build_report(
    *,
    config: dict[str, Any],
    changes_doc: dict[str, Any],
    latest_finalized: date,
    current_total: dict[str, Any],
    previous_total: dict[str, Any],
    current_raw: list[dict[str, Any]],
    previous_raw: list[dict[str, Any]],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    window_days = int(config.get("window_days", 28))
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    min_impressions = int(config.get("min_impressions", 20))
    max_candidates = int(config.get("max_candidates", 100))
    brand_terms = [str(value) for value in config.get("brand_terms") or []]

    current_end = latest_finalized
    current_start = current_end - timedelta(days=window_days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=window_days - 1)

    current, current_redacted = pair_rows(current_raw)
    previous, previous_redacted = pair_rows(previous_raw)
    benchmarks = ctr_benchmarks(current)
    all_keys = sorted(set(current) | set(previous))
    rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for query, page in all_keys:
        comparison = compare_metrics(current.get((query, page)), previous.get((query, page)))
        cur = comparison["current"]
        band = position_band(cur["position"]) if cur["impressions"] else None
        benchmark = benchmarks.get(band, 0.0) if band else 0.0
        row = {
            "query": query,
            "page": page,
            "brand": brand_query(query, brand_terms),
            "position_band": band,
            "benchmark_ctr": benchmark if band else None,
            **comparison,
        }
        rows.append(row)
        if cur["impressions"] >= min_impressions and band and cur["ctr"] < benchmark:
            missed_clicks = (benchmark - cur["ctr"]) * cur["impressions"]
            candidates.append({**row, "estimated_missed_clicks_vs_band": missed_clicks})

    candidates.sort(
        key=lambda row: (
            float(row["estimated_missed_clicks_vs_band"]),
            float(row["current"]["impressions"]),
        ),
        reverse=True,
    )
    rows.sort(key=lambda row: (float(row["current"]["clicks"]), float(row["current"]["impressions"])), reverse=True)
    changes = changes_for_window(changes_doc, previous_start, current_end)
    generated = generated_at or datetime.now(timezone.utc)
    return {
        "schema_version": "search-console-growth.v1",
        "generated_at": generated.isoformat().replace("+00:00", "Z"),
        "site_url": str(config["site_url"]),
        "latest_finalized_date": latest_finalized.isoformat(),
        "windows": {
            "current": {"start": current_start.isoformat(), "end": current_end.isoformat(), "days": window_days},
            "previous": {"start": previous_start.isoformat(), "end": previous_end.isoformat(), "days": window_days},
        },
        "totals": compare_metrics(current_total, previous_total),
        "query_page_rows": rows,
        "candidates": candidates[:max_candidates],
        "candidate_contract": {
            "min_impressions": min_impressions,
            "ranking": "estimated_missed_clicks_vs_position_band_ctr",
            "position_bands": ["1-3", "4-10", "11-20", "21-50", "51+"],
            "current_band_ctr": benchmarks,
        },
        "brand_terms": brand_terms,
        "changes_in_comparison_window": changes,
        "privacy": {
            "obvious_pii_query_rows_dropped": current_redacted + previous_redacted,
            "stored_dimensions": ["query", "page"],
            "credentials_stored": False,
        },
        "generative_ai": {
            "status": "not_collected",
            "impressions": None,
            "note": "Dedicated Search Console generative-AI reports are a separate, limited-rollout surface; absence is not recorded as zero.",
        },
        "api_limitations": [
            "Search Analytics API returns top rows and does not guarantee every data row.",
            "Only finalized Search Console data is used.",
        ],
    }


def collect(config: dict[str, Any], changes_doc: dict[str, Any], today: date) -> dict[str, Any]:
    site_url = str(config.get("site_url") or "").strip()
    if not site_url.startswith("https://"):
        raise ValueError("site_url must be an HTTPS Search Console property URL")
    token = access_token_from_environment()
    client = SearchConsoleClient(site_url, token)
    try:
        latest = client.latest_finalized_date(today)
        if latest is None:
            return {
                "schema_version": "search-console-growth.v1",
                "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "site_url": site_url,
                "status": "no_finalized_rows",
                "latest_finalized_date": None,
                "generative_ai": {"status": "not_collected", "impressions": None},
            }
        days = int(config.get("window_days", 28))
        current_start = latest - timedelta(days=days - 1)
        previous_end = current_start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=days - 1)
        return build_report(
            config=config,
            changes_doc=changes_doc,
            latest_finalized=latest,
            current_total=client.total(current_start, latest),
            previous_total=client.total(previous_start, previous_end),
            current_raw=client.rows(current_start, latest, ["query", "page"]),
            previous_raw=client.rows(previous_start, previous_end, ["query", "page"]),
        )
    finally:
        client.close()


def write_report(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = str(report.get("latest_finalized_date") or date.today().isoformat())
    dated = output_root / f"{stamp}.json"
    latest = output_root / "latest.json"
    body = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    dated.write_text(body, encoding="utf-8")
    latest.write_text(body, encoding="utf-8")
    return dated, latest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/search_console_growth.json"))
    parser.add_argument("--changes", type=Path, default=Path("config/search_console_changes.json"))
    parser.add_argument("--output-root", type=Path, default=Path("audit/growth/search-console"))
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    report = collect(load_json(args.config), load_json(args.changes), args.today)
    dated, latest = write_report(report, args.output_root)
    print(json.dumps({"dated": str(dated), "latest": str(latest), "status": report.get("status", "ok")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
