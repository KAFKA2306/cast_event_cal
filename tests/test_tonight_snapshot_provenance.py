"""Browser-level provenance behavior: use published snapshot, never a stale literal."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js is required for browser JS behavior")
def test_tonight_source_revision_is_snapshot_driven_and_fails_closed() -> None:
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('public/tonight/kafka-signal.js', 'utf8');
const good = {schema_version: 1, source_revision: 'a'.repeat(40),
  events_sha256: 'b'.repeat(64), generated_at: '2026-10-25T08:06:18Z'};
async function scenario(payload, httpOk=true) {
  const footer = {items: [], querySelector: () => null, append(p) {this.items.push(p)}};
  const document = {
    readyState: 'complete', documentElement: {dataset: {}},
    querySelector: s => s === 'footer' ? footer : null,
    createElement: () => ({textContent: '', title: '', className: ''})
  };
  const fetch = async (url, options) => {
    assert.equal(url, '../snapshot.json');
    assert.equal(options.cache, 'no-store');
    if (!httpOk) throw Error('offline');
    return {ok: true, json: async () => payload};
  };
  vm.runInNewContext(source, {document, fetch});
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(footer.items.length, 1);
  return {label: footer.items[0].textContent,
    title: footer.items[0].title, revision: document.documentElement.dataset.snapshotSourceRevision};
}
(async () => {
  const ok = await scenario(good);
  assert.match(ok.label, /source aaaaaaaa$/);
  assert.equal(ok.revision, good.source_revision);
  assert.match(ok.title, /公開イベントデータの生成元/);
  const malformed = await scenario({...good, source_revision: '6cceef70'});
  assert.match(malformed.label, /UNVERIFIED$/);
  assert.equal(malformed.revision, 'UNVERIFIED');
  const offline = await scenario(good, false);
  assert.match(offline.label, /UNVERIFIED$/);
  assert.equal(offline.revision, 'UNVERIFIED');
})().catch(e => {console.error(e); process.exitCode = 1});
"""
    result = subprocess.run(
        [NODE, "-e", script], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_tonight_html_does_not_claim_a_static_commit() -> None:
    html = (ROOT / "public/tonight/index.html").read_text(encoding="utf-8")
    assert 'rel="publication-provenance" href="../snapshot.json"' in html
    assert 'name="kafka-signal-commit"' not in html


@pytest.mark.skipif(NODE is None, reason="Node.js is required for browser JS behavior")
def test_tonight_explanation_renders_untrusted_reason_as_text() -> None:
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('public/tonight/kafka-signal.js', 'utf8');
const hostile = '<img src=x onerror="globalThis.pwned=1">';
let explanation;
const details = {prepend(node) { explanation = node; }};
const card = {
  dataset: {},
  querySelector(selector) {
    if (selector === 'details .details-body') return details;
    if (selector === '[data-field="reason"]') return {textContent: hostile};
    if (selector === '[data-field="source"]') return {textContent: hostile};
    return null;
  }
};
const list = {querySelectorAll() {return [card];}};
const document = {
  readyState: 'complete',
  documentElement: {dataset: {}},
  querySelector(selector) {return selector === '#list' ? list : null;},
  createElement(tag) {
    return {
      tag, textContent: '', children: [],
      append(...items) {this.children.push(...items);},
      set innerHTML(value) {throw new Error('unsafe HTML parser used');}
    };
  }
};
class MutationObserver {observe() {}}
vm.runInNewContext(source, {document, MutationObserver});
assert.ok(explanation, 'explanation must be rendered');
assert.equal(explanation.children[0].textContent, 'この一覧に表示された理由');
assert.equal(explanation.children[1].tag, 'br');
assert.equal(typeof explanation.children[2], 'string');
assert.equal(explanation.children[2].split(hostile).length, 3);
assert.match(explanation.children[2], /これは公式説明ではなく/);
assert.equal(card.dataset.ksExplained, '1');
"""
    result = subprocess.run(
        [NODE, "-e", script], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
