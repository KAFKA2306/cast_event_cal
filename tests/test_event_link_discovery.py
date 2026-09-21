from collections import Counter

import httpx

from scripts.discover_event_links import classify, enrich, request_counter


def test_classify_participation_links() -> None:
    assert classify("https://forms.gle/example") == ("application", "応募・申込")
    assert classify("https://vrchat.com/home/group/grp_123") == ("vrchat_group", "VRChat Group")
    assert classify("https://x.com/example/status/123") == ("announcement", "公式告知")


def test_primary_action_prefers_application() -> None:
    event = {
        "url": "https://x.com/example/status/123",
        "description": "応募 https://forms.gle/example 参加 https://vrchat.com/home/group/grp_123",
        "official_links": [],
    }
    with httpx.Client() as client:
        result = enrich(event, client)
    assert result["primary_action_url"] == "https://forms.gle/example"
    assert result["primary_action_kind"] == "application"
    assert [row["kind"] for row in result["official_links"]][:3] == ["application", "vrchat_group", "announcement"]


def test_shortener_resolution_counts_actual_requests() -> None:
    stats: Counter[str] = Counter()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "bit.ly":
            return httpx.Response(302, headers={"Location": "https://example.com/event"}, request=request)
        return httpx.Response(200, request=request)

    event = {
        "url": "https://bit.ly/event",
        "official_links": [],
    }
    with httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        event_hooks={"request": [request_counter(stats)]},
    ) as client:
        result = enrich(event, client, resolution_stats=stats)

    assert stats["shortener_resolution_attempts"] == 1
    assert stats["network_requests"] == 2
    assert result["related_links"][0]["url"] == "https://example.com/event"
