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
