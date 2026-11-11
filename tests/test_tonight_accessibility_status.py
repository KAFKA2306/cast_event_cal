"""Exercise Tonight's rendered status with a tiny browser-like environment."""
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_tonight_has_one_polite_result_status_and_an_error_alert() -> None:
    html = (ROOT / "public/tonight/index.html").read_text(encoding="utf-8")
    assert html.count('role="status"') == 1
    assert 'id="announcer"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-atomic="true"' in html
    assert 'id="error" class="state error" role="alert"' in html
    assert 'id="list" class="event-list" aria-busy="true"' in html


def test_zero_results_are_announced_and_typing_is_coalesced_without_focus_move() -> None:
    if not shutil.which("node"):
        pytest.skip("Node is required to exercise the published Tonight JS")

    js = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('public/tonight/tonight.js', 'utf8');
const marker = 'init()})();';
assert.ok(source.endsWith(marker));
const instrumented = source.slice(0, -marker.length)
    + 'globalThis.__api={state,render};})();';
const elements = new Map();
let focusMoves = 0;
const node = () => ({
    textContent:'',innerHTML:'',hidden:false,
    replaceChildren(){},
    setAttribute(name,value){this[name]=value},
    focus(){focusMoves++},
});
let nextTimer = 0;
const pending = new Map();
const ctx = {
    document:{querySelector(selector){
        if(!elements.has(selector))elements.set(selector,node());
        return elements.get(selector);
    }},
    location:{pathname:'/tonight/',search:''},
    history:{replaceState(){}},
    Date,Intl,URL,URLSearchParams,
    setTimeout(fn){const id=++nextTimer;pending.set(id,fn);return id},
    clearTimeout(id){pending.delete(id)},
};
vm.runInNewContext(instrumented,ctx);
ctx.__api.render();
assert.match(elements.get('#announcer').textContent,/0件/);
assert.equal(elements.get('#list')['aria-busy'],'false');
ctx.__api.state.q='a';
ctx.__api.render();
ctx.__api.state.q='ab';
ctx.__api.render();
assert.equal(pending.size,1,'stale search announcements must be canceled');
[...pending.values()][0]();
assert.match(elements.get('#announcer').textContent,/0件/);
assert.equal(focusMoves,0);
"""
    subprocess.run(
        ["node", "-e", js],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
