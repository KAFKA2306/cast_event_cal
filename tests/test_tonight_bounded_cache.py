from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_tonight_cached_snapshot_is_validated_and_expires() -> None:
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('public/tonight/tonight.js', 'utf8');
const marker = 'init()})();';
assert.ok(source.endsWith(marker));
const testSource = source.slice(0, -marker.length)
  + 'globalThis.__test={snapshot,cacheSnapshot,cachedSnapshot};})();';
const storage = new Map();
const localStorage = {
  getItem: key => storage.has(key) ? storage.get(key) : null,
  setItem: (key, value) => storage.set(key, String(value)),
};
const context = {Date, localStorage, URL, URLSearchParams, Intl};
vm.runInNewContext(testSource, context);
const api = context.__test;
const now = Date.now();
const event = {id:'sample', starts_at:new Date(now+3600000).toISOString()};
const valid = {generated_at:new Date(now-600000).toISOString(), events:[event]};
assert.equal(api.snapshot(valid).events.length, 1);
api.cacheSnapshot(valid);
assert.equal(api.cachedSnapshot().events[0].id, 'sample');
assert.equal(api.cachedSnapshot().ageMinutes, 10);
assert.throws(() => api.snapshot({generated_at:valid.generated_at, events:[]}), /invalid snapshot/);
assert.throws(() => api.snapshot({generated_at:'invalid', events:[event]}), /invalid snapshot/);
assert.throws(() => api.snapshot({generated_at:new Date(now+3600000).toISOString(), events:[event]}), /invalid snapshot/);
const key = [...storage.keys()][0];
assert.ok(key);
storage.set(key, JSON.stringify({data:{...valid,generated_at:new Date(now-25*3600000).toISOString()}}));
assert.equal(api.cachedSnapshot(), null);
storage.set(key, '{invalid json');
assert.equal(api.cachedSnapshot(), null);
storage.set(key, JSON.stringify({data:valid}));
localStorage.setItem = () => { throw new Error('quota exceeded'); };
assert.doesNotThrow(() => api.cacheSnapshot(valid));
assert.equal(api.cachedSnapshot().events[0].id, 'sample');
"""
    subprocess.run(["node", "-e", script], cwd=ROOT, check=True, capture_output=True, text=True)
