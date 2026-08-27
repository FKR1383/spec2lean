# Phase 4: Semantic Extractor

The original extraction prompt and create-only build path are unchanged by the
repair loop. Traceability failures may use the separate bounded
`semantics revise` path, which receives the current semantic artifact, the exact
Phase-6 broken mappings, and the same Phase-3 evidence boundary.

Phase 4 consumes one accepted Phase-3 evidence bundle for one planned unit and
produces an evidence-linked semantic artifact. It does not access Phase 1,
retrieve evidence, browse the internet, generate Lean, prove properties, check
code, or troubleshoot later phases.

## Session and input boundary

Each selected unit receives exactly one bounded OpenCode session. Its prompt
contains deterministic unit metadata and the exact unit `evidence.json`. The
session has only one local tool, `submit_semantics`. Shell, filesystem, search,
internet, task/subagent, skills, editing, and language-server tools are denied.
There are no automatic retry sessions. Structural diagnostics from a rejected
tool call can be corrected only within the same session.

The exact configuration is pinned both in the isolated agent and on the command
line:

```text
model: openai/gpt-5.6-sol
reasoning/variant: medium
```

A model-catalog preflight fails before creating a run directory if that exact
ID is unavailable. No substitute model is selected. The model, reasoning,
single-session setting, zero automatic retries, evidence hash, command, session
ID, timestamps, and captured output are recorded in `extractor-run.json`.

## Submission and artifact schema

`submit_semantics` accepts either `SUCCESS` or `INSUFFICIENT_EVIDENCE`.
Successful submissions use typed optional components:

- unit kind and identity;
- syntax forms;
- named inputs, operand roles, and constraints;
- result and constraints;
- core operation with named inputs, result description, and explicit branches;
- edge cases;
- state effects separate from the pure operation;
- optional predication behavior;
- version, target, type, operand, or other restrictions;
- shared semantic dependencies;
- structured semantic claims.

The claim vocabulary is deliberately closed: `SOURCE_FACT`,
`DERIVED_INTERPRETATION`, `DESIGN_DEPENDENCY`, and `ASSUMPTION`.
`OPEN_QUESTION` is not supported. If evidence cannot establish required
semantics, the model must use `INSUFFICIENT_EVIDENCE` with concrete missing
aspects rather than storing an unresolved guess.

Deterministic code, not the model, adds language/version, plan and unit IDs,
the canonical SHA-256 hash of the Phase-3 bundle, model/reasoning, semantic run
ID, creation timestamp, phase, and schema version. The canonical public schema
is `schemas/semantic-artifact.schema.json`.

## Evidence linking and validation

Every source-bearing component cites Phase-3 `evidenceId` values. Dependencies
may have an empty evidence list only when they describe an explicit modeling
need rather than a source fact. Every `SOURCE_FACT` and
`DERIVED_INTERPRETATION` requires evidence. Design dependencies and assumptions
may be source-independent.

Before a session starts, Phase 4 checks that the unit is uniquely present in
the plan, its evidence bundle exists, the bundle matches the plan/unit,
language, version, and Phase-1 database digest, and every evidence record has
the right unit and source-document identity. The bundle is passed as an input;
Phase 1 is not opened.

Submission and stored-artifact validation rejects:

- unsupported fields and invalid enum values;
- unknown or duplicate evidence references;
- missing evidence on source facts or derived interpretations;
- duplicate claim IDs or duplicate classified claim statements;
- unresolved branch, edge-case, state-effect, restriction, or predication evidence;
- wrong instruction identity;
- missing instruction inputs, result, or core operation;
- a nominal instruction operation that cites only guard/state evidence rather
  than `OPERATION` or `ALGORITHM` evidence;
- any mismatch in deterministic metadata or evidence-bundle hash.

These checks establish structure, traceability, and functionality presence.
They deliberately do not judge whether an LLM interpretation is semantically
correct; that remains an extractor and human-review boundary.

## Artifacts and inspection

Successful and insufficient-evidence sessions write:

```text
semantics/<language>/<version>/<plan-run-id>/<unit-slug>-<unit-id-prefix>/
  semantics.json
  semantics.md
  extractor-run.json
```

`semantics.json` is canonical. `semantics.md` deterministically separates the
core operation, branches, inputs/output, each claim classification, state
effects, edge cases, restrictions, dependencies, and predication for review.
It contains no generated Lean.

Inspection is read-only and never starts OpenCode:

```bash
./spec2lean semantics show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean semantics claims --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean semantics operation --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean semantics evidence --claim CLAIM_ID
./spec2lean semantics stats --plan-run PLAN_RUN_ID
```

Normal tests use synthetic plans, evidence, and semantic submissions. Runner
coverage uses a fake process that calls the local submission server directly;
the test suite never starts a real OpenCode session.
