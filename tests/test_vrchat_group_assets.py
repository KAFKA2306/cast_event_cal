from scripts.enrich_vrchat_group_assets import extract_group_image, group_url


def test_extract_group_image_from_open_graph_metadata() -> None:
    page = '<html><head><meta property="og:image" content="https://assets.vrchat.com/group.jpg"></head></html>'
    assert extract_group_image(page) == "https://assets.vrchat.com/group.jpg"


def test_extract_group_image_accepts_reversed_attribute_order() -> None:
    page = '<meta content="https://assets.vrchat.com/group.webp" name="twitter:image">'
    assert extract_group_image(page) == "https://assets.vrchat.com/group.webp"


def test_group_url_prefers_official_vrchat_group_link() -> None:
    event = {
        "url": "https://x.com/example/status/123",
        "official_links": [
            {
                "url": "https://vrchat.com/home/group/grp_db9d6929-5d48-4047-8aea-36d560bcec26",
                "kind": "vrchat_group",
            }
        ],
    }
    assert group_url(event) == "https://vrchat.com/home/group/grp_db9d6929-5d48-4047-8aea-36d560bcec26"
