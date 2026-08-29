# Phase 6: Check

Phase 6 consumes the existing Phase-3 evidence bundle, successful Phase-4
semantic artifacts, Phase-5 Lean source, and Phase-5 declaration mappings for
one complete translated group. When the group references a frozen shared core,
it also consumes that exact core source and manifest snapshot. It tests and reports; it does not retrieve evidence,
rerun an earlier phase, edit Lean, generate theorems or proofs, or troubleshoot a
failure.

## Three checks

The Build Test invokes the `lean` executable selected by the repository's Lean
toolchain environment on the existing complete group Lean file. For a group
that imports a shared core, the checker copies the referenced dependency source
into an isolated temporary module tree, compiles it there, and then checks the
group against the resulting module. It never writes `.olean` or other build
products into the frozen shared-core snapshot. It records PASS/FAIL, exit
code, complete compiler diagnostics with parsed file/line/column locations when
available, the reported Lean version, and elapsed milliseconds. It never edits
the source or attempts a repair.

The Coverage Test follows the explicit forward mapping boundary:

```text
Phase-3 evidence <- Phase-4 (unitId, claimId) -> Phase-5 declaration -> Group.lean
```

Every Phase-4 claim is required to resolve to at least one declaration that is
either present in the group source and mapped in the translation manifest, or
present in the frozen core and registered for a shared semantic dependency used
by the group. A shared mapping is resolved through
`semantics.dependencies[].dependencyId` and `semanticClaimIds`, the group's
`sharedUses`, and the core's concept/declaration registry. Evidence IDs
cited by those claims are reported as covered or uncovered with them. Evidence
that Phase 4 did not attach to a claim is not independently classified as
translation-required: the current typed Phase-5 contract maps declarations to
claims, not to prose or anonymous semantic-component paths. A missing claim or
its cited evidence is a Coverage failure routed to the Translator.

The Traceability Test follows the reverse chain for every named local or
relevant shared Lean declaration:

```text
Lean declaration -> claim -> evidence -> Phase-1 document/node/span
```

It deterministically detects unmapped declarations, absent declarations,
missing or cyclic support mappings, nonexistent claims, required claim evidence
that is absent, nonexistent evidence, stale artifact hashes and boundaries,
evidence assigned to another unit, source-index digest drift, and broken Phase-1
document/node/span provenance. It also rejects a group/core dependency mismatch,
a missing registered core declaration, and a local redefinition of a declaration
owned by the frozen core. It uses the existing Phase-1 index only to verify
stored provenance identifiers and source identity; it does not retrieve new
evidence or perform a new semantic review.

The group source is built once. Group traceability is evaluated once across all
member artifacts, while coverage is calculated separately for each member unit.
Build and logical checks run independently in a two-worker thread pool. The
shared results are written into each member's check artifact. No OpenCode or
other model is used.

## Result and routing

Each run writes:

```text
checks/<language>/<version>/<plan-run-id>/<unit-slug>/
  check.json
  check.md
```

The typed JSON contract is `schemas/check-result.schema.json`. Re-running a
check replaces only that unit's two derived check reports; it does not modify
any Phase-1 through Phase-5 artifact.

Each newly produced result also records hashes of the exact Phase-4 semantics,
Lean source, and translation manifest it checked. When a shared core is present,
the result additionally records `sharedCoreSource` and `sharedCoreManifest`
hashes. Historical and non-core checks retain exactly the original three hash
keys. These hashes bind bounded
revision attempts to a concrete check result and prevent stale diagnostics from
being consumed repeatedly.

Routing is deterministic and report-only:

- Traceability failure adds `SEMANTIC_EXTRACTOR`.
- Coverage failure adds `TRANSLATOR`.
- Build failure adds `TROUBLESHOOTER`.
- All three passing produces only `COMPLETE`.

`routing.next` is always an array so simultaneous failures are preserved. Its
targets are ordered by earliest workflow phase first: Semantic Extractor,
Translator, then Troubleshooter. Phase 6 does not execute any destination.

## CLI

Run one translated unit:

```bash
./spec2lean check run --plan-run PLAN_RUN_ID --unit UNIT_ID
```

Inspect the stored result without rerunning a check:

```bash
./spec2lean check show --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean check coverage --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean check traceability --plan-run PLAN_RUN_ID --unit UNIT_ID
./spec2lean check recheck --plan-run PLAN_RUN_ID --unit UNIT_ID
```

`check run` exits zero only when all three checks pass. A completed check that
finds any failure exits one; missing or invalid infrastructure/input exits two.
Tests use deterministic synthetic artifacts and compiler processes and never
invoke OpenCode.
