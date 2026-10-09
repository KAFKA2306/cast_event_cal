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
