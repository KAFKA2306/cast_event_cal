from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_module():
    path = Path(__file__).parents[1] / "scripts" / "fetch_vrchat_calendar.py"
    spec = importlib.util.spec_from_file_location("fetch_vrchat_calendar", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, *, params):
        self.calls.append((url, params))
        return FakeResponse(self.payloads.pop(0))


def test_discover_route_uses_next_cursor():
    module = load_module()
    client = FakeClient(
        [
            {"results": [{"id": "cal_1"}], "nextCursor": "cursor-2"},
            {"results": [{"id": "cal_2"}], "nextCursor": ""},
        ]
    )
    rows = module.fetch_discover(client, page_size=80, max_pages=3)
    assert [row["id"] for row in rows] == ["cal_1", "cal_2"]
    assert client.calls[0][0] == module.DISCOVER_API_URL
    assert client.calls[0][1]["scope"] == "upcoming"
    assert client.calls[1][1] == {"n": 80, "nextCursor": "cursor-2"}


def test_normalize_event_builds_shareable_official_url():
    module = load_module()
    event = module.normalize_event(
        {
            "id": "cal_11111111-1111-1111-1111-111111111111",
            "ownerId": "grp_22222222-2222-2222-2222-222222222222",
            "title": "公開技術イベント",
            "startsAt": "2026-08-05T12:00:00Z",
            "endsAt": "2026-08-05T13:00:00Z",
            "accessType": "public",
            "category": "education",
            "languages": ["jpn"],
            "platforms": ["standalonewindows", "android"],
            "featured": True,
            "occurrenceKind": "single",
        }
    )
    assert event is not None
    assert event["url"].endswith(
        "/grp_22222222-2222-2222-2222-222222222222/calendar/cal_11111111-1111-1111-1111-111111111111"
    )
    assert "公式カレンダー" in event["tags"]
    assert "featured" in event["tags"]
