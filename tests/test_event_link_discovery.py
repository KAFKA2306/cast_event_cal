import httpx

from scripts.discover_event_links import classify, enrich


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
