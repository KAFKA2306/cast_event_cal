import json
import subprocess
from pathlib import Path

POLICY = Path('public/recommendation-policy.js')


def run_policy(events, context, now='2026-09-22T12:00:00Z'):
    script = f"""
const p=require('./{POLICY.as_posix()}');
const out=p.recommend({json.dumps(events)}, {json.dumps(context)}, new Date({json.dumps(now)}));
console.log(JSON.stringify(out.map(x=>({{id:x.event_id,score:x.score,reason:x.reason,version:x.policy_version}}))));
"""
    return json.loads(subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True).stdout)


def event(id_, start, category='community', **extra):
    return {'id': id_, 'starts_at': start, 'category': category, **extra}


def test_excludes_invalid_past_self_and_duplicate_identity():
    events = [
        event('past', '2026-09-22T11:00:00Z'),
        event('self', '2026-09-22T13:00:00Z'),
        {'id': 'bad', 'starts_at': 'unknown'},
        event('same', '2026-09-22T14:00:00Z'),
        event('same', '2026-09-22T15:00:00Z'),
        event('future', '2026-09-22T16:00:00Z'),
    ]
    out = run_policy(events, {'currentEventId': 'self'})
    assert [row['id'] for row in out] == ['same', 'future']


def test_ranking_is_deterministic_and_explains_canonical_category_match():
    events = [
        event('b', '2026-09-23T12:00:00Z', 'music'),
        event('a', '2026-09-23T12:00:00Z', 'music'),
        event('c', '2026-09-22T13:00:00Z', 'community'),
    ]
    context = {'preferredCategories': ['music'], 'seenIds': ['b']}
    first = run_policy(events, context)
    second = run_policy(list(reversed(events)), context)
    assert first == second
    assert [row['id'] for row in first] == ['a', 'b', 'c']
    assert first[0]['reason']['category_match'] == ['music']
    assert first[0]['version'] == 'recommendation.v1'


def test_empty_history_and_zero_candidates_are_normal():
    assert run_policy([], {}) == []
    out = run_policy([event('x', '2026-09-23T12:00:00Z')], {})
    assert [row['id'] for row in out] == ['x']
