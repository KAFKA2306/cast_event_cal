from pathlib import Path

from PIL import Image

from scripts.render_distribution_assets import QR_IMAGE, link_homepage, load_config, render_poster, render_use_page


def test_distribution_assets_render(tmp_path: Path) -> None:
    config = load_config()
    assert config["site_url"] == "https://kafka2306.github.io/cast_event_cal/"
    assert all(int(item["width"]) <= 2048 and int(item["height"]) <= 2048 for item in config["posters"])

    poster = tmp_path / "poster.webp"
    render_poster(config, QR_IMAGE, poster, 512, 512)
    with Image.open(poster) as image:
        assert image.format == "WEBP"
        assert image.size == (512, 512)

    page = tmp_path / "use" / "index.html"
    render_use_page(config, page)
    rendered = page.read_text(encoding="utf-8")
    assert config["site_url"] in rendered
    assert "poster-square.webp" in rendered
    assert "poster-portrait.webp" in rendered
    assert "../events.json" in rendered
    assert "../calendar.ics" in rendered


def test_homepage_distribution_link_is_idempotent(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    github = '<a href="https://github.com/KAFKA2306/cast_event_cal">GitHub</a>'
    page.write_text(f"<footer>{github}</footer>", encoding="utf-8")

    link_homepage(page)
    link_homepage(page)

    rendered = page.read_text(encoding="utf-8")
    assert rendered.count('href="use/"') == 1
    assert github in rendered
