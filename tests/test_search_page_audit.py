from pathlib import Path

from scripts.audit_search_pages import audit


def test_audit_detects_canonical_drift(tmp_path: Path) -> None:
    public = tmp_path / "public"
    page = public / "events" / "evt-1"
    page.mkdir(parents=True)
    (public / "sitemap.xml").write_text(
        '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/events/evt-1/</loc></url></urlset>',
        encoding="utf-8",
    )
    page.joinpath("index.html").write_text(
        '<meta name="description" content="x"><meta name="robots" content="index,follow"><meta property="og:title" content="x"><meta property="og:url" content="https://example.test/events/evt-1/"><link rel="canonical" href="https://wrong.test/events/evt-1/">',
        encoding="utf-8",
    )
    report = audit(public)
    assert report["status"] == "error"
    assert "canonical_mismatch:evt-1" in report["reasons"]


def test_audit_accepts_consistent_indexable_page(tmp_path: Path) -> None:
    public = tmp_path / "public"
    page = public / "events" / "evt-1"
    page.mkdir(parents=True)
    url = "https://example.test/events/evt-1/"
    (public / "sitemap.xml").write_text(
        f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{url}</loc></url></urlset>',
        encoding="utf-8",
    )
    page.joinpath("index.html").write_text(
        f'<meta name="description" content="x"><meta name="robots" content="index,follow"><meta property="og:title" content="x"><meta property="og:url" content="{url}"><link rel="canonical" href="{url}">',
        encoding="utf-8",
    )
    report = audit(public)
    assert report["status"] == "ok"
    assert report["checked_pages"] == 1
