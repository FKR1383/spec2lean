# Changelog

All notable changes to Spec2Lean are documented here.

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

- Dual-source units now require paired HTML/PDF Phase-3 evidence and both
  citations on every factual or derived Phase-4 claim; the GUI displays both
  records through its existing claim evidence view.
- Phase-2 plans now use schema version 2 and contain `translationGroups`; older plans must be
  regenerated from the plan phase.
- Translation grouping is language-neutral and no longer relies on a hard-coded PTX mnemonic table.
- Build-only troubleshooting accepts file-level import repairs without falsely attributing them to
  a mapped Lean declaration.

### Validation

- 126 automated tests pass.
- A live PTX `add.u32` run completed all seven phases with BUILD, COVERAGE, and TRACEABILITY passing.
