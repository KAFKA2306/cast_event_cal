from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path("public/tonight/outbound-url-safety.js")


def _evaluate(values: list[str]) -> list[str | None]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the production browser URL policy")
    harness = f"""
class HTMLAnchorElement {{}}
global.HTMLAnchorElement = HTMLAnchorElement;
global.document = {{querySelector: () => null}};
global.window = {{}};
global.MutationObserver = class {{}};
global.Node = {{ELEMENT_NODE: 1}};
require('./{SCRIPT.as_posix()}');
const values = {json.dumps(values)};
console.log(JSON.stringify(values.map(v => window.TonightOutboundUrlSafety.safeOutboundUrl(v))));
"""
    result = subprocess.run(
        [node, "-e", harness],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_outbound_policy_accepts_only_absolute_https() -> None:
    values = [
        "https://example.com/event",
        "https://例え.テスト/イベント?q=日本語",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "//evil.example/path",
        "not a url",
        " https://example.com/ok ",
        "https://example.com/evil\npath",
    ]
    actual = _evaluate(values)
    assert actual[0] == "https://example.com/event"
    assert actual[1] is not None and actual[1].startswith("https://")
    assert actual[2:8] == [None] * 6
    assert actual[8] == "https://example.com/ok"
    assert actual[9] is None


def test_tonight_loads_single_outbound_policy_after_renderer() -> None:
    html = Path("public/tonight/index.html").read_text(encoding="utf-8")
    assert html.count("./outbound-url-safety.js") == 1
    assert html.index("./tonight.js") < html.index("./outbound-url-safety.js")
