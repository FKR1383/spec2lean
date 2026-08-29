# Pipeline Runner design

## Boundary

The runner orchestrates Phases 1–7 through their public Python APIs. It does not
implement planning, retrieval, semantic extraction, core representation choice,
group translation, checking, or repair logic itself. The unit/group schedule and
shared prerequisites come solely from the accepted Phase-2 plan.

The V1.1 execution boundary is:

```text
Phase 1 index
  -> Phase 2 bounded units, groups, and shared prerequisites
  -> Phase 3 evidence for every requested unit
  -> Phase 4 semantics for every requested unit
  -> one fresh frozen Phase-5 shared core, when required
  -> Phase-5 group translations bound to that core
  -> Phase-6 group checks
  -> bounded Phase-7 routing
```

Phase 3 and Phase 4 remain unit-scoped. The pipeline completes Phase 4 for all
requested units before selecting a core or starting any group Translator, so
representation selection sees the complete request-scoped set of shared
semantic requirements.

## Run identity and durable state

Every non-dry invocation owns
`runs/<language>/<version>/<pipeline-run-id>/run.json`. Writes are atomic and
occur after Phase 1, Phase 2, the shared-core decision, and every unit/group
transition. The schema-v2 run manifest records the typed request, Phase-1 digest
and disposition, referenced plan, shared-core disposition/reference, per-unit
stage dispositions, Phase-7 outcome, timestamps, and terminal error.

The shared-core state is one of:

- `NOT_REQUIRED` when the accepted plan has no shared prerequisites;
- `REUSED` with `{coreRunId, manifestHash, sourceHash, leanModule}`;
- `BUILT` with that same immutable reference; or
- `WOULD_BUILD` during a dry run or when required semantic inputs are not
  available for a read-only projection.

When a loaded current core is stale and no replacement is built, its validation
diagnostic codes are retained as `staleReasons`.

Human-readable progress is emitted to stderr before and after potentially long
phase calls, preserving stdout for the final JSON manifest. Keyboard interrupts
are persisted as `INTERRUPTED` and include the resumable run ID. Generated phase
artifacts remain owned by their original stores; the pipeline manifest
references them rather than copying or reinterpreting them.

## Freshness and reuse

Presence is never sufficient for reuse:

- Phase 1 must pass the deterministic validator, including official source
  hashes, parser/schema versions, SQLite integrity, and page-text validation.
- Phase 2 must use the current schema version, identical typed request, and
  current Phase-1 semantic digest. A resumed pre-V1.1 plan is replanned when
  Phase 2 is selected, or rejected when `--from` forbids replanning.
- Phase 3 must bind to the accepted plan, planned unit, specification identity,
  Phase-1 digest, and current evidence validation rules.
- Phase 4 must be a successful artifact deterministically reconstructed from
  the current Phase-3 bundle hash and the unit's current Phase-2 shared
  prerequisites. `INSUFFICIENT_EVIDENCE` enters the bounded database-first Open
  Question Handler; unresolved questions stop the run.
- The shared core must load through its integrity-checked current pointer and
  validate against the specification identity, source hash, deterministic
  content ID, representation schema, generator model/reasoning/policy, registry
  invariants, and all relevant Phase-4 dependency/claim fingerprints.
- A Phase-5 group translation must use the current translation schema, match all
  member semantic hashes, have a deterministic run ID for those inputs and its
  exact core reference, match translator metadata, and pass published-artifact
  validation against the same core registry. Historical schema-v2 group output
  remains directly inspectable/checkable but is not reusable by the pipeline.
- Phase 6 must refer to the current translation run and exactly match its
  semantic, Lean-source, and translation-manifest hashes. For a core-backed
  group it must also match the exact referenced core and its canonical source
  and manifest hashes.

Changing a relevant shared semantic dependency or linked claim changes its
`semanticInputHash` and invalidates the current core. A representation schema or
semantically relevant materializer policy/model change also invalidates it.
Unrelated unit semantics do not force a core rebuild. Existing core versions
are never overwritten or moved to `superseded/`. A pure missing-concept change
creates a validated append-only child; a changed semantic/policy fingerprint
starts a new lineage. Both publish under a new ID before the atomic current
pointer advances.

Incomplete or stale generated Phase-3/4 unit directories and Phase-5 group
directories are moved to the current run's `superseded/` tree before retry,
making interruption recovery inspectable and non-destructive. Historical
shared-core snapshots already have their own immutable `versions/` store.

## Shared-core selection and freeze

If the plan has shared prerequisites, the runner loads every requested unit's
successful Phase-4 artifact and tries the current core first. A valid snapshot
is reused without OpenCode or Lean work. Otherwise, when `translate` is within
the writable phase range, `ensure_shared_core` performs one controlled
materialization/extension and Lean build before returning a
`FrozenSharedCore`. If Phase 5 is before `--from`, absence of a fresh core is a
hard error; dry-run reports `WOULD_BUILD` without starting OpenCode.

The selected immutable object is held for the complete translation pass.
Applicable groups receive that exact snapshot and persist its four-field
reference; groups with no relevant `requiredBy` consumers remain non-core
groups. A later change to `current.json` cannot retarget an already published
group manifest.

Materialization itself is concurrency-safe. A per-language/version in-process
lock plus advisory `.core.lock` covers reload, freshness validation,
materialization, build, and atomic publication. Concurrent callers serialize;
after waiting, each reloads `current.json`, so all callers with the same inputs
reuse the single snapshot that won publication. Group translators cannot modify
that snapshot, and Phase 6 compiles a temporary staged copy rather than writing
build products beside it.

The integrated runner currently processes units and groups serially. The frozen
identity and store lock nevertheless guarantee the same core if public phase
APIs are invoked concurrently outside that loop.

## Open-question recovery

Open-question progress reports missing aspects, handler round, disposition, and
counts of canonical evidence and non-normative resolutions added. The maximum
number of rounds is controlled by `--max-question-rounds` (default 2). A trusted
runtime adapter may be configured with `SPEC2LEAN_RUNTIME_PROBE_COMMAND`;
arbitrary model-selected shell execution is never enabled.

Tentative handler additions become canonical Phase-3 evidence only after a
fresh extractor produces valid successful semantics. Transport failure or a
terminal unresolved question leaves Phase 3 unchanged.

## Group checking and routing

Phase 6 is invoked once for a stale group and returns one per-unit result. For a
core-backed group, Build verifies the reference, stages/compiles the frozen core
under its dotted module name in a temporary tree, and then builds the group.
Coverage and Traceability resolve shared claims through Phase-4 dependencies,
the group's `sharedUses`, and the core concept/declaration registry. Local
declarations retain their ordinary claim/evidence/source chain.

A passing result advances to the next scheduled unit. A failure is given to
Phase 7, which deterministically chooses the earliest owner: Traceability to the
Semantic Extractor, Coverage to the Translator, and Build to the
Troubleshooter. Phase 7 reruns all checks after every action. Its actionable
state hash includes check input hashes, so a changed shared-core binding is not
mistaken for the same state. The no-progress hash and configured dispatch limit
bound the complete chain.

Phase-7 build repair may modify only the group source and, for a mechanical
rename, its local declaration mappings. The exact `sharedCore` reference and
`sharedUses` must survive validation unchanged. Core extension remains a Phase-5
freshness/materialization operation, never a Troubleshooter action.

## Controls

`--resume [RUN_ID]` reopens a compatible manifest; without an ID it selects the
latest compatible typed request. `--dry-run` performs read-only inspection and
does not create a run or invoke OpenCode. `--from` permits artifact creation only
at or after a phase and therefore requires fresh earlier artifacts. `--until`
stops after a phase. Cyclic or incomplete Phase-2 schedules are rejected before
unit processing.
