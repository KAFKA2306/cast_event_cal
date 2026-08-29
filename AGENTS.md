# cast_event_cal Agent Contract

## Short-context start

Read this file, then only the canonical files and source evidence needed for the current task. Do not preload all event data, Issues, PR history, docs, audits, or source archives.

For non-trivial work keep one bounded workline:

- **Goal** — observable outcome
- **Contract** — what may/may not change
- **Acceptance** — deterministic completion conditions
- **Evidence** — current source/files/tests/audits/CI/production receipts
- **Next action** — one exact action if unfinished

Continue an existing Issue/PR when it owns the same outcome. Durable state belongs in canonical data/audits or that workline, not chat memory.

## Mission and authority

This repository owns VRChat event source collection, source identity/timestamps, normalization/classification, accepted/rejected candidate state, ontology, canonical `public/` snapshot generation, and their audits.

`KAFKA2306/vrc_cast_event_calender` is projection/delivery only; do not duplicate collectors, classifiers, ontology ownership, or the canonical event database there.

Priority: current user request > current canonical data/schema/code/audits > current primary source evidence > exact-head tests/CI > current architecture docs > Issue/PR history > conversation memory/inference.

## Evidence rules

Classify material claims as `VERIFIED`, `OBSERVED`, `INFERRED`, or `UNVERIFIED`. Fabrication is forbidden.

- never infer missing dates, participation methods, metrics, organizer identity, ontology matches, or source timestamps.
- relative dates such as `今日` / `明日` are interpreted from the source post timestamp, not collection time.
- prefer organizer/official first-party sources for current event facts.
- unresolved contradictory evidence narrows/rejects a claim; it is not guessed through.
- rejection is a valid result and must preserve the reason needed for replay/improvement.

## Canonical verification

Run the narrowest relevant check first:

```bash
ruff check cast_event_cal scripts tests main_executor.py
pytest tests
python scripts/materialize_events.py
python main_executor.py run --strict
python scripts/render_frontend.py
```

Escalate only when the affected contract requires it. A command not run is not PASS. Build/collection/dispatch success is not proof that the public artifact is correct.

## Change and automation rules

- one outcome, one canonical workline/ledger/pipeline/authority.
- `DELETE > MERGE > REPLACE > ADD`; remove superseded paths only after current references prove them unused.
- do not silently replace healthy state with empty/partial data after a source failure.
- do not turn unavailable fields into plausible defaults or hide rejects/failure reasons.
- do not use LLM-only judgment as the deterministic daily acceptance path without an explicit contract change.
- generated/public projections are weaker evidence than the canonical source state that produced them.
- comments should explain non-obvious rationale/external constraints, not narrate code.

## PR, publication, continuation

Use one reviewable PR workline and verify the exact head for the changed surface. Merge requires the bounded repository-local acceptance criteria and relevant deterministic checks, not unrelated external claims.

Publication is separate: when a public surface changes, verify the merged revision and applicable production read-back directly. CI or workflow dispatch alone is not production evidence.

If work stops, record the last verified revision, evidence already acquired, unresolved evidence/failing stage, blocker, and one exact next action in the existing Issue/PR or canonical state surface. Do not create a second agent-state database.

Complete only when the requested Goal is directly inspected, canonical state remains truthful/replayable, required checks and exact-head CI pass, required production postconditions are verified, and task-created duplicate/superseded residue is removed.
