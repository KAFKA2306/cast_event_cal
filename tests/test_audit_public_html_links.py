from __future__ import annotations

from pathlib import Path

from scripts.audit_public_html_links import audit_html, audit_public_html


def test_static_html_accepts_internal_navigation_and_https(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<a href="#events">section</a>'
        '<a href="/events/123">internal</a>'
        '<a href="../calendar.ics">relative</a>'
        '<a href="https://example.com/join">external</a>',
        encoding="utf-8",
    )
    assert audit_html(page) == []


def test_static_html_rejects_executable_and_ambiguous_targets(
    tmp_path: Path,
) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<a href="javascript:alert(1)">script</a>'
        '<a href="data:text/html,hello">data</a>'
        '<a href="//evil.example/join">protocol-relative</a>'
        '<a href="http://example.com">plaintext</a>'
        '<a href="https://user:pass@example.com">userinfo</a>'
        '<a href="https://example.com:bad/path">bad-port</a>'
        '<a href="https:///missing-host">missing-host</a>'
        '<a href="\\evil.example">backslash</a>'
        '<a href="jav&#x61;script:alert(1)">encoded</a>',
        encoding="utf-8",
    )
    failures = audit_html(page)
    assert len(failures) == 9
    assert sum("javascript:alert(1)" in failure for failure in failures) == 2


def test_directory_audit_includes_nested_generated_pages(tmp_path: Path) -> None:
    nested = tmp_path / "events" / "one"
    nested.mkdir(parents=True)
    (tmp_path / "index.html").write_text(
        '<a href="https://example.com">safe</a>', encoding="utf-8"
    )
    (nested / "index.html").write_text(
        '<a href="javascript:alert(1)">unsafe</a>', encoding="utf-8"
    )
    failures = audit_public_html(tmp_path)
    assert len(failures) == 1
    assert str(nested / "index.html") in failures[0]
