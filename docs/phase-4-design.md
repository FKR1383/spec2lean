# Phase 4: Semantic Extractor and Open Question Handler

Phase 4 consumes one accepted Phase-3 evidence bundle for one planned unit and
produces an evidence-linked semantic artifact. The initial Semantic Extractor
is strictly evidence-bounded. If it returns `INSUFFICIENT_EVIDENCE`, a separate
Open Question Handler verifies each missing aspect against the canonical
Phase-1 database and, when necessary, records a clearly classified fallback.
The augmented evidence is then given to a fresh Semantic Extractor session.

Traceability failures still use the separate bounded `semantics revise` path,
which receives the current semantic artifact, the exact Phase-6 broken
mappings, and the same Phase-3 evidence boundary.

## Session and input boundary

Each extraction attempt receives exactly one bounded OpenCode session. Its prompt
contains deterministic unit metadata and the Phase-2 shared prerequisites relevant
to that unit, while the exact unit `evidence.json` is
projected by the bounded `get_evidence` tool into the fields Phase 4 needs:
evidence IDs, roles, tiers, source types, exact text, sections, rationales, and
compact source locations. Verbose HTML/PDF span and bounding-box provenance
remains in the canonical bundle for deterministic validation and the GUI. The bundle is not copied into the
`opencode run` command-line argument, avoiding platform per-argument size limits
without changing the source boundary. The session has only two local tools,
`get_evidence` and `submit_semantics`; submission is rejected until the bundle
has been read. Shell, filesystem, search, internet, task/subagent, skills,
editing, and language-server tools are denied.
There are no automatic retries of the same prompt. Structural diagnostics from
a rejected tool call can be corrected only within the same session. A fresh
extractor session is started only after the Open Question Handler has produced
a validated evidence augmentation.

Open-question additions remain tentative across recovery rounds. They are
committed to the Phase-3 bundle only after a restarted extractor returns valid
successful semantics; a transport error or terminal failure leaves Phase 3
unchanged. A truncated `get_evidence` response is classified as
`EVIDENCE_TRANSPORT_FAILURE` and never routed as a specification question.

The exact configuration is pinned both in the isolated agent and on the command
line:

```text
model: openai/gpt-5.6-sol
reasoning/variant: medium
```

A model-catalog preflight fails before creating a run directory if that exact
ID is unavailable. No substitute model is selected. The model, reasoning,
single-session setting, evidence hash, command, session
ID, timestamps, and captured output are recorded in `extractor-run.json`.

## Open-question recovery

An insufficient-evidence artifact is converted deterministically into stable
`question:*` IDs. A separate OpenCode session uses the same pinned model and
reasoning level and must give every question one disposition. It follows this
order:

1. Search the read-only Phase-1 database and read exact source nodes.
2. If the specification truly does not answer the question, use an attributed
   internet source, a configured runtime probe, or explicit LLM reasoning.
3. If no responsible answer is available, mark the question `UNRESOLVED` and
   stop the pipeline.

The handler cannot submit a fallback until its tool ledger proves that the
canonical database was searched for that specific question. Database material
is rebuilt by deterministic code into normal `evidence:*` records with full
Phase-1 provenance. It is never copied from free-form model output.

Internet, runtime, and LLM answers become `resolution:*` records with
`nonNormative: true` and source-specific provenance:

- internet: URL and excerpt;
- runtime: trusted adapter identity, request, exit status, stdout, and stderr;
- LLM reasoning: exact model and reasoning variant.

The runtime path is disabled unless `SPEC2LEAN_RUNTIME_PROBE_COMMAND` contains
a trusted adapter command. The adapter receives a JSON request on stdin; the
handler cannot supply an arbitrary command. Internet tools are available only
inside the handler session. A semantic claim that cites any supplemental
resolution must be classified as `ASSUMPTION`; deterministic validation rejects
it as a source fact or derived interpretation.

The default recovery bound is two rounds. Set it with
`--max-question-rounds N`; `0` restores immediate failure on insufficient
evidence. A partially resolved or unresolved handler submission blocks the
pipeline rather than silently generating semantics.

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
- shared semantic dependencies, optionally bound to exact Phase-2 `shared:*`
  IDs and local semantic claims;
- structured semantic claims.

The claim vocabulary is deliberately closed: `SOURCE_FACT`,
`DERIVED_INTERPRETATION`, `DESIGN_DEPENDENCY`, and `ASSUMPTION`.
`OPEN_QUESTION` is not a claim kind. If the current evidence cannot establish
required semantics, the extractor must use `INSUFFICIENT_EVIDENCE` with
concrete missing aspects; the handler, rather than the extractor, owns their
resolution.

Deterministic code, not the model, adds language/version, plan and unit IDs,
the canonical SHA-256 hash of the Phase-3 bundle, model/reasoning, semantic run
ID, creation timestamp, phase, and schema version. The canonical public schema
is `schemas/semantic-artifact.schema.json`.

## Evidence linking and validation

Every source-bearing component cites Phase-3 `evidence:*` or `resolution:*`
IDs. Dependencies
may have an empty evidence list only when they describe an explicit modeling
need rather than a source fact. Every `SOURCE_FACT` and
`DERIVED_INTERPRETATION` requires evidence. Design dependencies and assumptions
may be source-independent.

Phase 4 reuses the existing `dependencies` component rather than creating a
second shared-semantics collection. For every Phase-2 shared prerequisite whose
`requiredBy` contains the current unit, the successful artifact must include
exactly one dependency with the same `dependencyId` and concept name. Its
`semanticClaimIds` identify one or more claims in this artifact that describe
what the concept requires. Claim IDs remain unit-local; downstream manifests
qualify them with the unit ID. Deterministic validation rejects missing,
unknown, duplicate, or misnamed shared dependencies and missing or unknown
claim links.

An extractor may still report a genuine modeling dependency that the Planner
did not identify. Such a dependency remains explicitly unbound by omitting
`dependencyId`; this does not claim that a shared implementation already
exists. Phase 4 describes meaning only and never chooses the Lean
representation.

If the Phase-3 bundle contains both official HTML and PDF evidence, every
`SOURCE_FACT` and `DERIVED_INTERPRETATION` must cite supporting evidence from
both renditions. This is checked per claim, so a PDF item elsewhere in the
bundle cannot satisfy an unrelated claim. The rule is inactive for legitimate
single-rendition bundles.

Before a session starts, Phase 4 checks that the unit is uniquely present in
the plan, its evidence bundle exists, the bundle matches the plan/unit,
language, version, and Phase-1 database digest, and every evidence record has
the right unit and source-document identity. The bundle is passed as an input;
the extractor does not open Phase 1. Only the separate handler opens it.

Submission and stored-artifact validation rejects:

- unsupported fields and invalid enum values;
- unknown or duplicate evidence references;
- missing evidence on source facts or derived interpretations;
- a factual or derived claim missing its HTML or PDF citation in a dual-source bundle;
- any non-`ASSUMPTION` claim that cites a non-normative resolution;
- a non-normative resolution used by a semantic component but not mapped to an
  `ASSUMPTION` claim;
- duplicate claim IDs or duplicate classified claim statements;
- missing, unknown, duplicate, or incorrectly named Phase-2 shared dependencies;
- missing, malformed, duplicate, or unknown dependency-to-claim links;
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

The current successful or insufficient-evidence extraction writes:

```text
semantics/<language>/<version>/<plan-run-id>/<unit-slug>-<unit-id-prefix>/
  semantics.json
  semantics.md
  extractor-run.json
```

Each handler round is retained for audit:

```text
  open-question-attempts/attempt-N/
    extractor/
      semantics.json
      semantics.md
      extractor-run.json
    handler/
      handler-run.json
      open-questions.json
      open-questions.md
      before-evidence.json
      after-evidence.json
```

`handler-run.json` records the database/tool ledger and any runtime probes.
`open-questions.json` records each question, disposition, answer, references,
and provenance. The Phase-3 `evidence.json` is atomically replaced by the
validated augmented bundle, and its retriever metadata records the
augmentation and resulting bundle hash.

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
./spec2lean semantics questions --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean semantics stats --plan-run PLAN_RUN_ID
```

Normal tests use synthetic plans, evidence, and semantic submissions. Runner
coverage uses a fake process that calls the local submission server directly;
the test suite never starts a real OpenCode session.
