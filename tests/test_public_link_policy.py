from pathlib import Path

from scripts.audit_public_links import audit_html
from scripts.public_link_policy import first_safe_public_url, safe_public_url


def test_safe_public_url_accepts_only_well_formed_https() -> None:
    good = "https://example.com/event?id=1#join"
    assert safe_public_url(good) == good
    for value in (
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "//example.com/event",
        "http://example.com/event",
        "https:///missing-host",
        "https://user:pass@example.com/event",
        "https://example.com:bad/event",
        "not a url",
        "",
        None,
    ):
        assert safe_public_url(value) is None


def test_selector_skips_poisoned_candidate_without_rewriting_valid_url() -> None:
    valid = "https://vrc.group/SAFE.1234"
    assert first_safe_public_url("javascript:alert(1)", valid) == valid
    assert first_safe_public_url("data:text/plain,no", "//evil.example") is None


def test_generated_html_audit_allows_internal_and_https_but_rejects_executable_scheme(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<a href="/events/x/">internal</a><a href="https://example.com/x">safe</a>',
        encoding="utf-8",
    )
    assert audit_html(page) == []
    page.write_text('<a href="javascript:alert(1)">bad</a>', encoding="utf-8")
    assert audit_html(page) == [f"{page}:javascript:alert(1)"]
