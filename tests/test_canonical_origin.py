from pathlib import Path

from scripts.verify_canonical_origin import audit


def test_audit_accepts_one_origin_and_rejects_legacy_host(tmp_path: Path) -> None:
    expected = "https://vrc-cast-event-calender.pages.dev"
    (tmp_path / "events" / "evt").mkdir(parents=True)
    (tmp_path / "index.html").write_text(
        f'<link rel="canonical" href="{expected}/"><meta property="og:url" content="{expected}/">',
        encoding="utf-8",
    )
    (tmp_path / "events" / "evt" / "index.html").write_text(
        f'<link rel="canonical" href="{expected}/events/evt/">', encoding="utf-8"
    )
    (tmp_path / "sitemap.xml").write_text(
        f'<urlset><url><loc>{expected}/</loc></url><url><loc>{expected}/events/evt/</loc></url></urlset>',
        encoding="utf-8",
    )
    assert audit(tmp_path, expected) == []

    (tmp_path / "events" / "evt" / "index.html").write_text(
        '<link rel="canonical" href="https://kafka2306.github.io/cast_event_cal/events/evt/">',
        encoding="utf-8",
    )
    failures = audit(tmp_path, expected)
    assert len(failures) == 1
    assert "kafka2306.github.io" in failures[0]


def test_audit_fails_closed_for_missing_public_artifacts(tmp_path: Path) -> None:
    expected = "https://vrc-cast-event-calender.pages.dev"
    findings = audit(tmp_path, expected)
    assert any("missing root index.html" in row for row in findings)
    assert any("missing sitemap.xml" in row for row in findings)


def test_audit_reports_missing_canonical(tmp_path: Path) -> None:
    expected = "https://vrc-cast-event-calender.pages.dev"
    (tmp_path / "index.html").write_text("<title>Missing canonical</title>", encoding="utf-8")
    (tmp_path / "sitemap.xml").write_text(f"<urlset><url><loc>{expected}/</loc></url></urlset>", encoding="utf-8")
    assert any("missing canonical" in row for row in audit(tmp_path, expected))
