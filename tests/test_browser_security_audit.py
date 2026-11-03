import json
from pathlib import Path

from scripts import audit_browser_security as audit


def test_policy_rejects_wildcard_and_unsafe_eval():
    policy = json.loads(audit.POLICY.read_text(encoding="utf-8"))
    policy["directives"]["script-src"] = ["'self'", "'unsafe-eval'"]
    policy["directives"]["connect-src"] = ["*"]
    errors = audit.audit_policy(policy)
    assert any("unsafe-eval" in error for error in errors)
    assert any("connect-src" in error and "*" in error for error in errors)


def test_inventory_detects_inline_capabilities_and_origins():
    result = audit.inventory("""
      <style>body{}</style><script>fetch('https://example.test/api')</script>
      <script>eval('1')</script>
      <script>document.createElement('script')</script>
    """)
    assert result["origins"] == ["example.test"]
    assert result["inline_script_blocks"] == 3
    assert result["inline_style_blocks"] == 1
    assert result["eval_calls"] == 1
    assert result["dynamic_script_injection"] is True


def test_repository_policy_is_audit_only_and_fail_closed():
    report = audit.build_report()
    assert report["mode"] == "audit-only"
    assert report["policy_errors"] == []
    surface = report["surfaces"]["web/index.template.html"]
    assert "public/index.html" in report["surfaces"]
    assert "public/tonight/index.html" in report["surfaces"]
    assert not report["missing_surfaces"]
    assert surface["eval_calls"] == 0
    assert surface["dynamic_script_injection"] is False
    policy = json.loads(Path(audit.POLICY).read_text(encoding="utf-8"))
    assert policy["directives"]["frame-ancestors"] == ["'none'"]
    assert "*" not in sum(policy["directives"].values(), [])
    assert "'unsafe-eval'" not in sum(policy["directives"].values(), [])


def test_inventory_does_not_count_external_or_data_scripts_as_inline_execution():
    result = audit.inventory("""
      <script src="/assets/app.js"></script>
      <script type="application/ld+json">{"@context":"https://schema.org"}</script>
      <script type="module">window.ready = true</script>
      <script>window.ready = true</script>
    """)
    assert result["inline_script_blocks"] == 2
    assert result["external_script_blocks"] == 1


def test_missing_production_headers_are_reported_explicitly(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace

    monkeypatch.setattr(
        audit,
        "urlopen",
        lambda *_args, **_kwargs: nullcontext(
            SimpleNamespace(headers={"Content-Security-Policy": "default-src 'self'"})
        ),
    )
    headers = audit.read_headers("https://example.test/")
    assert headers["content-security-policy"] == "default-src 'self'"
    assert headers["referrer-policy"] == "missing"
    assert headers["x-content-type-options"] == "missing"
    assert headers["permissions-policy"] == "missing"


def test_final_get_headers_and_duplicate_csp_are_visible(monkeypatch):
    from contextlib import nullcontext
    from email.message import Message
    from types import SimpleNamespace

    headers = Message()
    headers.add_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; script-src https://unexpected.test")
    headers.add_header("Content-Security-Policy", "object-src 'none'")
    headers.add_header("X-Frame-Options", "DENY")
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request.get_method(), timeout))
        return nullcontext(SimpleNamespace(
            headers=headers,
            status=200,
            geturl=lambda: "https://example.test/tonight/",
        ))

    monkeypatch.setattr(audit, "urlopen", fake_urlopen)
    result = audit.read_production_response("http://example.test/tonight")
    assert requests == [("GET", 15)]
    assert result["final_url"] == "https://example.test/tonight/"
    assert result["status"] == 200
    assert result["headers"]["x-frame-options"] == "DENY"
    assert result["duplicate_header_counts"]["content-security-policy"] == 2
    assert any("duplicate directive script-src" in error for error in result["policy_errors"])
    assert result["headers"]["permissions-policy"] == "missing"


def test_policy_parser_rejects_conflicting_none_but_not_distinct_directives():
    assert audit.policy_directive_errors(["default-src 'self'; object-src 'none'"]) == []
    errors = audit.policy_directive_errors(["script-src 'none' https://unexpected.test"])
    assert any("combines 'none'" in error for error in errors)


def test_multiple_production_surfaces_keep_separate_final_response_evidence(monkeypatch):
    urls = ["https://example.test/", "https://example.test/tonight/", "https://example.test/events/one/"]
    monkeypatch.setattr(audit, "read_production_response", lambda url: {"final_url": url, "headers": {}})
    report = audit.build_report(urls)
    assert [entry["final_url"] for entry in report["production"]] == urls



def test_check_report_rejects_invalid_live_csp_without_enforcing_missing_headers():
    clean = {"policy_errors": [], "production": [
        {"final_url": "https://example.test/", "policy_errors": []},
        {"final_url": "https://example.test/tonight/", "policy_errors": []},
    ]}
    assert audit.check_report(clean) == []
    malformed = {"policy_errors": [], "production": [
        {"final_url": "https://example.test/tonight/", "policy_errors": [
            "CSP #1: duplicate directive script-src"
        ]},
    ]}
    assert audit.check_report(malformed) == [
        "https://example.test/tonight/: CSP #1: duplicate directive script-src"
    ]
    assert audit.check_report({"policy_errors": ["bad local policy"]}) == ["bad local policy"]


def test_representative_generated_pages_and_missing_entry_point(tmp_path):
    pages = (
        "web/index.template.html",
        "public/index.html",
        "public/tonight/index.html",
        "public/events/z/index.html",
        "public/events/a/index.html",
        "public/categories/community/index.html",
        "public/series/one/index.html",
    )
    for relative in pages:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<script>window.ready = true</script>", encoding="utf-8")
    selected, missing = audit.select_surfaces(tmp_path)
    assert [str(path.relative_to(tmp_path)) for path in selected] == [
        "web/index.template.html",
        "public/index.html",
        "public/tonight/index.html",
        "public/events/a/index.html",
        "public/categories/community/index.html",
        "public/series/one/index.html",
    ]
    assert missing == []
    (tmp_path / "public/tonight/index.html").unlink()
    _, missing = audit.select_surfaces(tmp_path)
    assert missing == ["public/tonight/index.html"]
    assert audit.check_report({"policy_errors": [], "missing_surfaces": missing}) == [
        "missing audit surface: public/tonight/index.html"
    ]


def test_missing_generated_family_fails_security_coverage(tmp_path):
    for relative in (
        "web/index.template.html",
        "public/index.html",
        "public/tonight/index.html",
        "public/events/one/index.html",
        "public/series/one/index.html",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<main>test</main>", encoding="utf-8")
    selected, missing = audit.select_surfaces(tmp_path)
    assert len(selected) == 5
    assert missing == ["public/categories/*/index.html"]
    assert audit.check_report({"policy_errors": [], "missing_surfaces": missing}) == [
        "missing audit surface: public/categories/*/index.html"
    ]


def test_live_http_status_must_be_200_even_when_policy_is_valid():
    report = {"policy_errors": [], "production": [
        {"final_url": "https://example.test/", "status": 200, "policy_errors": []},
        {"final_url": "https://example.test/tonight/", "status": 204, "policy_errors": []},
    ]}
    assert audit.check_report(report) == [
        "https://example.test/tonight/: unexpected HTTP status 204"
    ]
    report["production"][1]["status"] = 200
    assert audit.check_report(report) == []
