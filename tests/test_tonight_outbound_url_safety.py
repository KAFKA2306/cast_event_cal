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


def test_browser_boundary_rechecks_attribute_mutations_and_clicks() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required for browser behavior regression")
    harness = """
const assert = require('node:assert/strict');
class HTMLAnchorElement {
  constructor(href) {
    this.attrs = {href};
    this.nodeType = 1;
    this.removed = false;
    this.target = '_blank';
    this.rel = '';
  }
  getAttribute(k) {return this.attrs[k] ?? null;}
  setAttribute(k,v) {this.attrs[k] = v;}
  remove() {this.removed = true;}
  querySelectorAll() {return [];}
  closest(q) {return q === 'a[href]' && this.getAttribute('href') !== null ? this : null;}
}
global.HTMLAnchorElement = HTMLAnchorElement;
global.Node = {ELEMENT_NODE: 1};
let observer, clickHandler;
const anchors = [new HTMLAnchorElement('https://example.com/event'), new HTMLAnchorElement('#events')];
const list = {
  querySelectorAll() {return anchors;},
  addEventListener(type, fn, capture) {
    assert.equal(type, 'click');
    assert.equal(capture, true);
    clickHandler = fn;
  }
};
global.document = {querySelector() {return list;}};
global.window = {};
global.MutationObserver = class {
  constructor(fn) {observer = fn;}
  observe(element, options) {
    assert.equal(element, list);
    assert.equal(options.attributes, true);
    assert.deepEqual(options.attributeFilter, ['href']);
  }
};
require('./public/tonight/outbound-url-safety.js');
assert.equal(anchors[0].rel, 'noopener noreferrer');
assert.equal(anchors[1].removed, false);
const changed = anchors[0];
changed.setAttribute('href', 'javascript:alert(1)');
let prevented = false;
clickHandler({target: changed, preventDefault() {prevented = true;}});
assert.equal(changed.removed, true);
assert.equal(prevented, true);
const mutated = new HTMLAnchorElement('https://user@example.com');
observer([{type: 'attributes', target: mutated, addedNodes: []}]);
assert.equal(mutated.removed, true);
const inserted = new HTMLAnchorElement('data:text/html,bad');
observer([{type: 'childList', addedNodes: [inserted]}]);
assert.equal(inserted.removed, true);
const relative = new HTMLAnchorElement('/events/1');
observer([{type: 'childList', addedNodes: [relative]}]);
assert.equal(relative.removed, false);
"""
    subprocess.run([node, "-e", harness], check=True, capture_output=True, text=True)


def test_outbound_policy_rejects_credentials_and_malformed_authorities() -> None:
    actual = _evaluate([
        "https://user:pass@example.com/join",
        "https://user@example.com",
        "https://example.com:bad/join",
        "https:\\example.com",
        "https://example.com/join",
    ])
    assert actual[:4] == [None] * 4
    assert actual[4] == "https://example.com/join"
