"""Browser search regression: visible content, Unicode normalization, and audit-field isolation."""

import json
import subprocess


def test_search_matches_normalized_visible_text_not_internal_metadata() -> None:
    program = r"""
const fs = require('node:fs');
const source = fs.readFileSync('web/index.template.html', 'utf8');
const lines = source.split(/\r?\n/);
const pick = name => {
  const line = lines.find(value => value.startsWith(`function ${name}(`));
  if (!line) throw new Error(`missing frontend function: ${name}`);
  return line;
};
const fields = {
  '#q': {value: ' ＡＩ　勉強会 '},
  '#category': {value: 'all'},
  '#source': {value: 'all'},
  '#include-deadlines': {checked: false}
};
const $ = selector => fields[selector];
const starts_at = new Date(Date.now() + 86400000).toISOString();
const state = {
  range: 'all',
  events: [
    {id: 'visible', title: 'AI 勉強会', category: 'lecture', starts_at},
    {id: 'hidden-evidence', title: '一般イベント', category: 'lecture',
     category_evidence: ['AI 勉強会'], starts_at},
    {id: 'hidden-source', title: '一般イベント', category: 'lecture',
     source: 'AI 勉強会', starts_at}
  ]
};
const code = [pick('searchNormalize'), pick('filtered'), 'return filtered();'].join('\n');
const matched = new Function('state', '$', 'categoryKey', 'eventLinks', 'rangeEnd', code)(
  state, $, value => value, () => [], () => new Date(Date.now() + 120 * 86400000)
);
process.stdout.write(JSON.stringify(matched.map(event => event.id)));
"""
    result = subprocess.run(["node", "-e", program], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == ["visible"]
