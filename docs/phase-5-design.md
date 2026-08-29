# Phase 5: Shared Formalization Core and Group Lean Translator

## Contract

Phase 5 has two ordered responsibilities:

1. Materialize or reuse one canonical Lean 4 representation registry for the
   shared semantic concepts required by the current request.
2. Translate each Phase-2 group against that exact frozen registry, producing
   one complete Lean file per group.

The mechanism is specification-independent. There is no built-in catalog of
values, states, identifiers, instruction families, or preferred Lean types.
Different language/version/source-digest identities naturally have different
cores. Unit-specific behavior remains in its group file.

The authority boundary remains strict:

```text
Phase 2: which source-level concepts are shared?
Phase 4: what does each shared concept mean?
Phase 5: how should this specification represent it in Lean?
```

Phase 5 never rereads the specification or Phase-3 evidence. It consumes the
accepted plan and successful Phase-4 artifacts only.

## Shared requirement boundary

A schema-v3 plan records each normalized prerequisite as:

```json
{
  "dependencyId": "shared:...",
  "name": "Specification concept name",
  "kind": "open-concept-label",
  "reason": "Why the bounded request needs it",
  "sourceNodeIds": ["node:..."],
  "requiredBy": ["unit:A", "unit:B"]
}
```

`dependencyId` is stable across requests with the same language, version,
conceptual key, name, kind, and source anchors. `requiredBy` contains only
requested units and does not schedule the prerequisite as another unit.

For every relevant prerequisite, each named consumer's schema-v2 Phase-4
artifact must contain exactly one dependency with the same `dependencyId` and
concept name, a non-empty semantic description, and one or more unique
`semanticClaimIds` that exist in that unit's claims. The collected shared
requirement contains:

- the normalized dependency ID, name, kind, source nodes, and consumers (the
  planning-only `reason` is not a semantic input);
- every relevant unit's semantic dependency;
- the exact linked claims, qualified by unit ID;
- the current semantic run and canonical artifact hash; and
- a `semanticInputHash` over the source database digest, concept metadata,
  semantic dependencies, and linked claims.

Phase-4 claims remain the semantic source of truth. The representation registry
does not replace or reinterpret them.

If a required artifact, dependency, description, claim link, or registered core
concept is absent, processing stops with `MISSING_SHARED_ABSTRACTION`. The
structured condition records `dependencyId`, the semantic requirement,
relevant `{unitId, claimId}` references when available, and a diagnostic detail.
A group Translator may not handle that condition by inventing a local type or
alias.

## Controlled representation selection

When no fresh core satisfies the collected requirements, one restricted
Shared-Core Materializer session receives the requirements and any accepted
parent snapshot. It uses `openai/gpt-5.6-sol` with medium reasoning and exposes
only `get_context` and `submit_core` through its local MCP boundary. Shell,
filesystem, web, task/subagent, skill, editing, and language-server tools are
denied.

The materializer chooses one clear, composable representation for each supplied
semantic dependency. Its policy is to:

- keep the core minimal and exclude unit-specific behavior;
- use Phase-4 requirements, expected operations, composability, and readability
  rather than a global representation rule;
- register every public or supporting declaration that implements a concept;
- share common evaluation/execution infrastructure only when the supplied
  semantics justify it; and
- keep pure unit operations separate from execution/state machinery where that
  boundary is meaningful for the specification.

There is no globally forced `Nat`, `BitVec`, state structure, environment, or
execution model.

## Immutable artifact layout

Shared artifacts are stored outside plan/group directories:

```text
translations/<language>/<version>/shared/
  .core.lock
  current.json
  versions/<coreRunId>/
    core-manifest.json
    core-run.json
    modules/Spec2LeanShared/<Language>/<Version>/<content-token>/Core.lean
```

`Core.lean` has a generated dotted `leanModule` matching its path beneath
`modules/`. A version directory is immutable after publication. Publication
first constructs a complete temporary directory, atomically moves it to its
content-addressed destination, and then atomically replaces `current.json`.
If a destination already exists, its source and identity-addressed manifest
fields must match or publication fails as a content-address collision. Attempt
timestamps, lineage, and historical
Phase-4 provenance are not part of that representation identity and never
cause an existing immutable directory to be rewritten.

`current.json` contains only:

```json
{
  "schemaVersion": 1,
  "coreRunId": "shared-core-run:...",
  "manifestHash": "sha256:...",
  "sourceHash": "sha256:...",
  "leanModule": "Spec2LeanShared....Core"
}
```

Loading a snapshot verifies the run ID, specification language/version/source
digest, safe module path, source hash, module/path correspondence, and pointer
contents. Consumers bind to the full reference rather than to the mutable word
“current.” If the pointer is missing, malformed, or stale after an interrupted
publication, the locked materializer scans valid immutable versions and
atomically reactivates a fresh snapshot (or a valid append-only parent) before
considering another model call.

## Core manifest and representation registry

`core-manifest.json` uses schema version 1 and has this complete field shape:

```json
{
  "schemaVersion": 1,
  "phase": "SHARED_CORE",
  "language": "...",
  "version": "...",
  "sourceDatabaseDigest": "...",
  "coreRunId": "shared-core-run:...",
  "parentCoreRunId": null,
  "representationSchemaVersion": 1,
  "generator": {
    "provider": "opencode",
    "model": "openai/gpt-5.6-sol",
    "reasoning": "medium",
    "policyVersion": 1,
    "invoked": true
  },
  "target": {"language": "Lean", "version": "4"},
  "leanFile": "modules/.../Core.lean",
  "leanModule": "Spec2LeanShared....Core",
  "createdAt": "...",
  "sourceHash": "sha256:...",
  "concepts": [
    {
      "dependencyId": "shared:...",
      "name": "...",
      "kind": "...",
      "sourceNodeIds": ["node:..."],
      "requiredBy": ["unit:..."],
      "semanticInputHash": "sha256:...",
      "leanDeclarations": ["Spec2Lean....Value"],
      "claimRefs": [{"unitId": "unit:...", "claimId": "claim:..."}]
    }
  ],
  "declarations": [
    {
      "declaration": "Spec2Lean....Value",
      "role": "PRIMARY_TYPE",
      "dependencyIds": ["shared:..."],
      "claimRefs": [{"unitId": "unit:...", "claimId": "claim:..."}]
    }
  ],
  "semanticArtifacts": [
    {
      "planRunId": "plan:...",
      "unitId": "unit:...",
      "runId": "semantic-run:...",
      "artifactHash": "sha256:..."
    }
  ]
}
```

An `IMPLEMENTATION_HELPER` may omit artificial direct claim references only
when `supportsDeclarations` resolves, without a cycle, to a mapped semantic
declaration. All other core declarations cite valid claims owned by their
`dependencyIds`. Every named declaration in the source is mapped, every
concept/declaration ownership edge agrees in both registry directions, and
introduced Lean types use the `PRIMARY_TYPE` role.

The canonical manifest hash is stored in pointers and group references, not
inside the self-hashed manifest.

## Validation, extension, and freshness

Before publication, deterministic code rejects forbidden constructs (`sorry`,
`admit`, axioms/constants, `unsafe`, and `partial`), invalid or missing
declarations, unknown dependency/claim ownership, unresolved support mappings,
noncanonical registry entries, and inconsistent identity metadata. It compiles
the candidate with the installed Lean toolchain in a temporary directory. Only
a passing core is published.

A current snapshot is reusable only when full validation against the current
plan and relevant Phase-4 requirements returns no diagnostics. In particular,
freshness binds:

- language, version, and Phase-1 semantic digest;
- the source content hash and deterministic `coreRunId`;
- representation schema version;
- materializer model, reasoning, and generator policy version;
- each required concept's name, open kind, source nodes, current consumers,
  linked claims, and `semanticInputHash` (recorded consumers/claim references
  may be a monotonic superset from accepted parent versions); and
- the source/registry traceability invariants.

The semantic input hash changes when a relevant dependency or linked claim
changes, while unrelated unit semantics do not force a core rebuild. File
existence alone is never freshness evidence.

Extension is deliberate and append-only only for a pure missing-concept case.
When validation reports only `MISSING_SHARED_CONCEPT`, the old snapshot becomes
`parentCoreRunId`; the submitted source must begin with the entire parent source
byte-for-byte, every accepted declaration mapping must remain identical, and no
registered declaration may be removed from a concept. The missing definitions
and registry entries are appended once, validated, compiled, and published
under a new content identity.

A changed semantic fingerprint, representation schema, generator policy, or
other stale invariant starts a new lineage with `parentCoreRunId: null`. This
lets representation selection respond to changed meaning instead of freezing a
now-incompatible design. The former snapshot is still immutable and remains
valid for already bound group manifests; only `current.json` advances.

## Concurrency and freeze

Materialization is serialized per language/version shared store with both an
in-process thread lock and an advisory file lock. The lock covers reloading the
current pointer, freshness validation, the bounded materializer call, Lean
validation, and publication. A concurrent caller that waited for another
publisher reloads the new snapshot and reuses it instead of starting a second
materializer. Thus equivalent concurrent requests publish one version.

The integrated pipeline selects the validated `FrozenSharedCore` once after all
requested Phase-4 artifacts are ready and passes that same object/reference to
every group with relevant `requiredBy` consumers; unrelated groups receive no
core. The current pipeline schedules groups serially, but the immutable
reference and lock also make separately invoked/concurrent consumers safe: they
cannot race to edit a core, and later pointer changes do not change an already
bound group.

## Group translation contract

For a group named `IntegerOperations`, Phase 5 stores:

```text
translations/<language>/<version>/<planRunId>/IntegerOperations/
  IntegerOperations.lean
  translation-manifest.json
  translator-run.json
  revisions/
```

One bounded Translator session receives all successful Phase-4 artifacts for
the group plus the relevant registry view and full source of the selected core.
It has only the structured `submit_translation` tool. It must import the exact
`leanModule`, reuse registered declarations, keep unit behavior local, and
submit one complete group file.

The schema-v3 group manifest records `sharedCore` as either `null` or:

```json
{
  "coreRunId": "shared-core-run:...",
  "manifestHash": "sha256:...",
  "sourceHash": "sha256:...",
  "leanModule": "Spec2LeanShared....Core"
}
```

For a core-backed group, top-level `sharedUses` contains one entry for every
shared dependency required by a group member:

```json
{
  "dependencyId": "shared:...",
  "leanDeclarations": ["Spec2Lean....Value"],
  "claimRefs": [{"unitId": "unit:...", "claimId": "claim:..."}]
}
```

The declaration list is the non-empty subset of registered names actually used
by the group. Claim references are reconstructed from current Phase-4
`semanticClaimIds`, not supplied as a second semantic authority. Groups without
relevant planned shared prerequisites use `sharedCore: null` and
`sharedUses: []`.

Deterministic translation validation additionally requires:

- the exact Phase-2 group boundary and current semantic artifact hashes;
- the exact frozen core reference and import;
- every required shared dependency to have a valid, actually referenced use;
- no local redefinition, alias-around substitute, or local claim ownership for
  a core-owned shared dependency;
- every local declaration to be mapped to current `(unitId, claimId)` pairs or
  a resolvable implementation-helper support chain;
- all required per-unit operation/execution responsibilities; and
- no forbidden Lean construct or unmapped named declaration.

The deterministic translation run ID includes both all member semantic hashes
and the core reference. A semantic or core change therefore invalidates the
complete group artifact.

## Phase 6 and Phase 7 compatibility

Phase 6 loads the exact referenced snapshot and verifies all four reference
fields. For Build it copies the dependency source to an isolated temporary
module tree, compiles it there, and then compiles the group; no `.olean` is
written into the immutable snapshot. Coverage and Traceability resolve imported
claims through Phase-4 dependencies, `sharedUses`, core concepts, and core
declaration mappings. Core source and manifest hashes are added to check input
hashes only for core-backed groups.

The checker still accepts historical schema-v2 group manifests as well as the
current schema-v3 manifest. A non-core/legacy build follows the original
single-file command and retains exactly the original three input-hash keys;
pipeline freshness, however, requires the current Phase-5 schema.

Phase 7 loads the same referenced snapshot for translation revisions and build
repair. A build repair may correct a group's import or use of a registered
declaration, but it must preserve `sharedCore`, `sharedUses`, declaration roles,
and resolved claim responsibilities. It never edits, extends, or republishes a
core. A revised Phase-4 dependency that makes the snapshot stale is owned by a
subsequent Phase-5 freshness/materialization pass, not by the Troubleshooter.

## Tests

Generic synthetic tests cover requirement collection, representation registry
round trips, traceability, fresh reuse without external work, semantic-change
invalidation, append-only extension, concurrent single publication, rejection
of parent rewrites, exclusion of unit-specific behavior, declarations shared by
multiple dependencies, and Lean compilation. Translation and Phase-6 tests
cover local redefinition rejection, imported coverage/traceability, temporary
dependency compilation, and conditional core hashes.
