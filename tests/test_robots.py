from pathlib import Path

import pytest

from scripts.generate_robots import render_robots, write_robots


def sitemap(urls: list[str]) -> str:
    rows = "".join(f"<url><loc>{url}</loc></url>" for url in urls)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{rows}</urlset>"
    )


def test_robots_is_byte_stable_and_has_one_canonical_sitemap(tmp_path: Path) -> None:
    base = "https://vrc-cast-event-calender.pages.dev"
    (tmp_path / "sitemap.xml").write_text(
        sitemap([f"{base}/", f"{base}/events/a/"]), encoding="utf-8"
    )
    first = write_robots(tmp_path, base).read_bytes()
    second = write_robots(tmp_path, base).read_bytes()
    assert first == second
    text = first.decode()
    assert text == f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n"
    assert text.count("Sitemap:") == 1
    assert "Disallow: /" not in text


def test_legacy_host_cannot_enter_projection() -> None:
    base = "https://vrc-cast-event-calender.pages.dev"
    assert "github.io" not in render_robots(base)


@pytest.mark.parametrize(
    "base",
    ["http://example.com", "example.com", "https://user:pass@example.com"],
)
def test_invalid_canonical_origin_fails_closed(base: str) -> None:
    with pytest.raises(ValueError):
        render_robots(base)


def test_sitemap_origin_drift_fails(tmp_path: Path) -> None:
    base = "https://vrc-cast-event-calender.pages.dev"
    (tmp_path / "sitemap.xml").write_text(
        sitemap(["https://legacy.example/events/a/"]), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="outside the canonical"):
        write_robots(tmp_path, base)
