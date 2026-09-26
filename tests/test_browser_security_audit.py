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
