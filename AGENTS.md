# AGENTS.md — cast_event_cal Agent Operating Contract

This file is the canonical operating contract for coding and repository agents working in `KAFKA2306/cast_event_cal`.

## 1. Mission

Improve the VRChat event intelligence system through the smallest evidence-backed change that makes the canonical event state more correct, reproducible, inspectable, and resumable.

Optimize for:

1. evidence before coverage;
2. deterministic classification and replay;
3. one canonical workline per outcome;
4. explicit source/provenance boundaries;
5. verification before completion claims;
6. durable continuation after interruption;
7. cleanup at the fixed point.

Candidate count, event count, scraped page count, or tool activity is not the goal.

## 2. Source-of-truth precedence

When information conflicts, use this order:

1. current user request and explicit acceptance criteria;
2. current canonical data, schemas, code, and deterministic audit logic in this repository;
3. current primary/official source response and preserved source observation metadata;
4. exact-head test/CI results and generated audit artifacts;
5. current architecture/methodology documentation;
6. Issue/PR prose and historical reports;
7. previous conversation context, memory, or inference.

Stale prose is a hypothesis, not ground truth. Never rewrite historical evidence merely to make it agree with a newer interpretation.

## 3. Contract before change

For non-trivial work define before editing:

- **Goal** — the observable repository or product outcome;
- **Contract** — what may change and what must remain unchanged;
- **Acceptance Criteria** — deterministic conditions that can falsify completion;
- **Evidence** — source records, files, tests, audits, CI runs, hashes, or production receipts;
- **Stopping Condition** — the fixed point after which further work is a separate outcome.

The Contract is both the minimum required result and the maximum allowed scope.

## 4. Canonical responsibility boundary

This repository owns:

- source collection and source identity;
- observation timestamps;
- normalization and deterministic classification;
- accepted and rejected candidate ledgers;
- event/category ontology;
- canonical `public/` snapshot generation;
- quality/audit evidence for those responsibilities.

`KAFKA2306/vrc_cast_event_calender` is a projection/delivery repository. Do not duplicate collectors, classifiers, ontology ownership, or an alternate canonical event database there.

Generated/public projections are not stronger evidence than the canonical source state that produced them.

## 5. Goal-driven execution loop

For work that needs more than one edit, keep one Goal active and iterate:

```text
inspect current state
  -> define smallest change
  -> implement
  -> run the cheapest relevant verifier
  -> inspect evidence
  -> repair if falsified
  -> escalate verification only as needed
  -> stop at the fixed point
```

A failed check is input to the next repair, not a reason to relabel the task successful. Do not stop after a plausible patch when the owning postcondition is inspectable.

## 6. Durable continuation and canonical workline

Before creating work:

1. inspect current `main`, relevant Issues, open PRs, branches, workflows, and canonical data/audits;
2. continue the existing Issue/branch/PR when it already owns the same outcome;
3. otherwise create one bounded workline;
4. do not create competing branches, alternate ledgers, duplicate manifests, or second pipelines for the same Goal.

When work cannot finish, leave the canonical workline resumable. Record the last verified revision, failing stage or unresolved evidence, exact blocker, and next action in the owning Issue/PR or existing canonical state surface. Do not invent a second state database solely for agent memory.

Persistent event observations, accepted/rejected decisions, source timestamps, and audits belong in the repository's existing canonical ledgers/artifacts, not in chat history.

## 7. Evidence and claim discipline

Material operational claims must be treated as one of:

- **VERIFIED** — directly supported by current source/repository/test/audit/CI evidence;
- **OBSERVED** — explicitly supplied as an observation;
- **INFERRED** — derived from evidence and reported as inference;
- **UNVERIFIED** — not yet inspected and never stated as fact;
- **FABRICATED** — forbidden.

Do not infer missing event dates, participation methods, retweet counts, organizer identity, ontology matches, or source timestamps. Preserve unknown/ambiguous states and fail closed where the owning contract requires evidence.

Relative dates such as `今日`, `本日`, and `明日` belong to the source post timestamp, not the collection/reprocessing date.

Reject is a first-class result. Preserve the reason needed for later classifier improvement and replay.

## 8. External-source rule

For current externally verifiable event facts:

- prefer organizer/official first-party sources;
- retain source identity and observation time required by the canonical schema;
- do not upgrade a search snippet or community summary into primary evidence when the official source is available;
- when source semantics or provider behavior changes, verify the current response before changing canonical parsing/classification;
- if contradictory evidence cannot be resolved, narrow or reject the claim rather than guessing.

## 9. Verification ladder

Use the narrowest relevant check first, then escalate when the affected contract requires it.

Current canonical local checks include:

```bash
ruff check cast_event_cal scripts tests main_executor.py
pytest tests
python scripts/materialize_events.py
python main_executor.py run --strict
python scripts/render_frontend.py
```

For workflow/publication changes, verify the exact workflow head and the applicable production read-back. A command that did not run is not PASS. A build or dispatch is not proof that the public artifact is correct.

## 10. Automation contract

Scheduled collection/classification must use the same canonical rules and evidence boundaries as manual work.

Automations must not:

- silently replace a healthy cache with empty/partial data after source failure;
- convert unavailable fields into plausible values;
- hide rejected candidates or failure reasons;
- claim delivery success from collection success alone;
- introduce LLM-only judgment into the deterministic daily acceptance path without an explicit contract change.

## 11. Builder / Auditor separation

Treat implementation and acceptance as separate phases even when one agent performs both sequentially.

### Builder

May change code, tests, schemas, ontology, canonical data, workflows, and docs within the bounded Contract.

### Auditor

Independently verifies:

- the requested Goal exists;
- source/provenance boundaries were preserved;
- accepted/rejected semantics remain truthful;
- deterministic checks pass on the relevant revision;
- generated snapshots match their owning canonical inputs;
- no stronger completion claim is made than the evidence supports;
- task-created residue is removed.

Implementation intent is never acceptance evidence.

## 12. Fixed point

Stop when all are true:

- the requested Goal is satisfied;
- acceptance criteria are evidenced;
- the smallest relevant tests/audits pass, plus broader required gates when applicable;
- the canonical data/audit state is truthful and replayable;
- exact-head CI is verified when the change uses a PR gate;
- required production postconditions are verified when publication is in scope;
- the owning Issue/PR state is correct;
- temporary files, duplicate worklines, and superseded task artifacts are gone;
- remaining ideas are separate outcomes rather than necessary repairs.

## 13. Final report

Report verified state, not activity theater. Include as applicable:

- Issue/PR/commit URL;
- bounded change;
- tests/audits and exact result;
- canonical data or snapshot consequence;
- production verification receipt;
- cleanup result;
- exact blocker and next action when unfinished.

Never claim event correctness, CI success, merge, deployment, or production parity without inspecting the corresponding evidence.