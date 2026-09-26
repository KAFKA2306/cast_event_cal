from __future__ import annotations

import json
from pathlib import Path

from scripts import fetch_vrchat_calendar as calendar
from scripts.fetch_vrchat_calendar import normalize_event, run_discovery


def sample_event(**overrides):
    event = {
        "id": "cal_6b182f0c-61ef-4bdf-97fe-94f63bcba27b",
        "ownerId": "grp_71a7ff59-112c-4e78-a990-c7cc650776e5",
        "title": "日本語ゲーム交流会",
        "description": "初心者歓迎",
        "startsAt": "2026-08-10T12:00:00Z",
        "endsAt": "2026-08-10T13:00:00Z",
        "accessType": "public",
        "category": "gaming",
        "languages": ["jpn"],
        "platforms": ["standalonewindows", "android"],
        "tags": ["beginner"],
        "isDraft": False,
        "deletedAt": None,
    }
    event.update(overrides)
    return event


def test_normalize_event_accepts_public_calendar_event():
    event = normalize_event(sample_event())
    assert event is not None
    assert event["source_id"].startswith("cal_")
    assert event["starts_at"] == "2026-08-10T12:00:00Z"
    assert event["url"].endswith("/calendar/cal_6b182f0c-61ef-4bdf-97fe-94f63bcba27b")
    assert {"VRChat", "公式カレンダー", "jpn", "android"} <= set(event["tags"])


def test_normalize_event_rejects_non_public_or_deleted_event():
    assert normalize_event(sample_event(accessType="group")) is None
    assert normalize_event(sample_event(deletedAt="2026-08-01T00:00:00Z")) is None
    assert normalize_event(sample_event(isDraft=True)) is None


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, payloads, **kwargs):
        self.payloads = list(payloads)
        self.headers = kwargs.get("headers", {})
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url, *, params):
        self.calls.append((url, params))
        return FakeResponse(self.payloads.pop(0))


def test_missing_cookie_uses_anonymous_public_discover(tmp_path: Path, monkeypatch):
    output = tmp_path / "discovered.json"
    health = tmp_path / "health.json"
    exclude = tmp_path / "manual.json"
    output.write_text("[]", encoding="utf-8")
    exclude.write_text("[]", encoding="utf-8")

    client = FakeClient(
        [{"results": [sample_event()], "nextCursor": ""}]
        + [
            {"results": [], "nextCursor": ""}
            for _ in range(len(calendar.ANONYMOUS_DISCOVER_CATEGORY_GROUPS) - 1)
        ]
    )
    monkeypatch.setattr(calendar.httpx, "Client", lambda **kwargs: (
        setattr(client, "headers", kwargs.get("headers", {})) or client
    ))

    result = run_discovery(
        cookie=None,
        output=output,
        health_output=health,
        exclude=exclude,
        terms=["日本語"],
        page_size=100,
        max_pages=1,
        timeout=1.0,
    )

    assert result == 0
    events = json.loads(output.read_text(encoding="utf-8"))
    assert [event["source_id"] for event in events] == [
        "cal_6b182f0c-61ef-4bdf-97fe-94f63bcba27b"
    ]
    assert "Cookie" not in client.headers
    assert client.calls[0][0] == calendar.DISCOVER_API_URL
    assert client.calls[0][1]["personalizedResults"] == "exclude"
    assert len(client.calls) == len(calendar.ANONYMOUS_DISCOVER_CATEGORY_GROUPS)
    assert client.calls[0][1]["categories"] == "arts"
    assert client.calls[1][1]["categories"] == "avatars"

    health_data = json.loads(health.read_text(encoding="utf-8"))
    assert health_data["status"] == "degraded"
    assert health_data["event_count"] == 1
    assert health_data["query_count"] == 0
    assert health_data["routes"] == {"discover": 1, "search": 0}
    assert health_data["discover_request_count"] == len(
        calendar.ANONYMOUS_DISCOVER_CATEGORY_GROUPS
    )
    assert "anonymous public discover" in health_data["reason"]


def test_anonymous_discover_failure_preserves_existing_cache(tmp_path: Path, monkeypatch):
    output = tmp_path / "discovered.json"
    health = tmp_path / "health.json"
    exclude = tmp_path / "manual.json"
    cached = [{"source_id": "cal_cached", "title": "cached", "starts_at": "2026-08-10T12:00:00Z"}]
    output.write_text(json.dumps(cached), encoding="utf-8")
    exclude.write_text("[]", encoding="utf-8")

    class FailingClient(FakeClient):
        def get(self, url, *, params):
            raise RuntimeError("temporary outage")

    client = FailingClient([])
    monkeypatch.setattr(calendar.httpx, "Client", lambda **kwargs: client)

    result = run_discovery(
        cookie=None,
        output=output,
        health_output=health,
        exclude=exclude,
        terms=["日本語"],
        page_size=100,
        max_pages=1,
        timeout=1.0,
    )

    assert result == 0
    assert json.loads(output.read_text(encoding="utf-8")) == cached
    health_data = json.loads(health.read_text(encoding="utf-8"))
    assert health_data["status"] == "degraded"
    assert health_data["event_count"] == 1
    assert "preserved previous discovery cache" in health_data["reason"]
