# Changelog

All notable changes to Spec2Lean are documented here.

## 1.1.0 - 2026-08-29

### Added

- Generic, request-scoped `sharedPrerequisites` in Phase 2, with stable `shared:*` identities,
  open specification-derived concept kinds, exact source-node support, and bounded `requiredBy`
  consumers. Phase 2 remains independent of Lean representation choices.
- Phase-4 links from each relevant shared prerequisite to its authoritative semantic dependency and
  unit-local claims through `dependencyId` and `semanticClaimIds`.
- A Phase-5 Shared-Core Materializer that chooses one minimal, specification-specific Lean
  representation for each required shared concept and records it in a source-traceable
  representation registry.
- Immutable, content-addressed shared-core versions with atomic publication, an integrity-checked
  current pointer, append-only missing-concept extension, fresh lineages for changed semantics or
  policy, and process/thread locking.
- Structured `MISSING_SHARED_ABSTRACTION` failures when required Phase-4 shared semantics or a
  registered core representation are absent.

### Changed

- Phase-2 plans use schema version 3, Phase-4 semantic artifacts use schema version 2, and Phase-5
  group translation manifests use schema version 3. Older artifacts must be regenerated at their
  owning phase before reuse.
- Group translators receive one exact frozen core snapshot, import its generated Lean module, list
  the registered declarations they use in `sharedUses`, and cannot redefine or locally substitute
  for a shared concept.
- The Pipeline Runner validates or materializes the shared core once after all Phase-4 artifacts are
  ready, then binds every applicable group translation to the same core identity and hashes.
- Phase-6 builds shared dependencies in a temporary module tree, resolves coverage and traceability
  through the core registry, and adds core source/manifest hashes only to core-backed check results.
- Phase-7 compiler repair may fix a group's import or use of a core declaration but must preserve
  the exact `sharedCore` reference and `sharedUses`; it cannot edit or redesign the frozen core.

### Validation

- Generic synthetic tests cover stable shared dependency identity, canonical declaration reuse,
  controlled extension, stale-core invalidation, fresh-core reuse, concurrent publication, frozen
  registry enforcement, shared traceability, and multi-module Lean compilation.

## 1.0.0 - 2026-08-28

### Added

- End-to-end seven-phase specification-to-Lean pipeline with resumable progress reporting.
- Bounded Open Question Handler with database-first resolution and explicit provenance for
  internet, runtime, and LLM-derived assumptions.
- Specification-derived translation groups selected by the Phase-2 Planner and validated as an
  exact, source-supported partition of requested units.
- One complete Lean source file per planned instruction group, with declaration-to-claim mappings.
- Deterministic build, semantic coverage, and traceability checks with bounded Phase-7 routing.
- Read-only CLI inspection for plans, evidence, semantics, open questions, translations, checks,
  and troubleshooting artifacts.

### Changed

- Large Phase-3 bundles are now fetched through the bounded semantics MCP tool instead of being
  copied into an operating-system command-line argument. The tool omits verbose GUI provenance,
  detects transport truncation, and keeps question-handler additions tentative until extraction succeeds.
- Dual-source units now require paired HTML/PDF Phase-3 evidence and both
  citations on every factual or derived Phase-4 claim; the GUI displays both
  records through its existing claim evidence view.
- Phase-2 plans now use schema version 2 and contain `translationGroups`; older plans must be
  regenerated from the plan phase.
- Translation grouping is language-neutral and no longer relies on a hard-coded PTX mnemonic table.
- Build-only troubleshooting accepts file-level import repairs without falsely attributing them to
  a mapped Lean declaration.

### Validation

- 128 automated tests pass.
- A live PTX `add.u32` run completed all seven phases with BUILD, COVERAGE, and TRACEABILITY passing.
