from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SAFE_LINKS = ROOT / "public" / "tonight" / "safe-links.js"
TONIGHT = ROOT / "public" / "tonight" / "tonight.js"
INDEX = ROOT / "public" / "tonight" / "index.html"


def test_safe_link_contract_with_representative_untrusted_values() -> None:
    script = r'''
const safe = require(process.argv[1]);
const assert = require('assert');
assert.strictEqual(safe.safeExternalUrl('javascript:alert(1)'), null);
assert.strictEqual(safe.safeExternalUrl('data:text/html,<h1>x</h1>'), null);
assert.strictEqual(safe.safeExternalUrl('vbscript:msgbox(1)'), null);
assert.strictEqual(safe.safeExternalUrl('//example.com/event'), null);
assert.strictEqual(safe.safeExternalUrl('not a url'), null);
assert.strictEqual(safe.safeExternalUrl('http://example.com/event'), null);
assert.strictEqual(safe.safeExternalUrl('https://example.com/a?x=1&y=2'), 'https://example.com/a?x=1&y=2');
assert.strictEqual(safe.safeExternalUrl('https://example.com/イベント'), 'https://example.com/%E3%82%A4%E3%83%99%E3%83%B3%E3%83%88');

const created = [];
const documentRef = { createElement(tag) { const node = { tag }; created.push(node); return node; } };
const label = '<img src=x onerror=alert(1)>';
const anchor = safe.buildExternalLink(documentRef, label, 'https://example.com/event');
assert.strictEqual(anchor.tag, 'a');
assert.strictEqual(anchor.href, 'https://example.com/event');
assert.strictEqual(anchor.target, '_blank');
assert.strictEqual(anchor.rel, 'noopener noreferrer');
assert.strictEqual(anchor.textContent, label + ' ↗');
assert.strictEqual(safe.buildExternalLink(documentRef, label, 'javascript:alert(1)'), null);
'''
    subprocess.run(["node", "-e", script, str(SAFE_LINKS)], check=True)


def test_tonight_renderer_uses_dom_safe_link_contract() -> None:
    renderer = TONIGHT.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")

    assert "safeLinks.safeExternalUrl" in renderer
    assert "safeLinks.buildExternalLink" in renderer
    assert "container.replaceChildren" in renderer
    assert ".proof').innerHTML" not in renderer
    assert "safe-links.js" in index
    assert index.index("safe-links.js") < index.index("tonight.js")
