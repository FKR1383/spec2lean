# Phase 5: Group Lean Translator

## Contract

Phase 5 consumes every accepted Phase-4 `semantics.json` belonging to one
deterministic instruction group and produces exactly one complete Lean 4 source
file for that group. It never creates per-instruction fragments or `Unit.lean`
files.

For PTX, the deterministic groups are `Arithmetic`, `BitManip`,
`Communication`, `Comparison`, `Conversion`, `Logic`, `Memory`, and `Move`.
Instructions outside the known table use `Other`, so a new mnemonic cannot
silently disappear. Other source languages currently use `Other`.

The pipeline finishes Phases 3 and 4 for all requested units before starting
Phase 5. It then runs one bounded OpenCode Translator session per non-empty
group, using `openai/gpt-5.6-sol` with medium reasoning. The session receives:

- a group scope containing all member units and semantic-artifact hashes;
- the complete Phase-4 artifacts keyed by unit ID; and
- one submission tool.

No specification database, Phase-3 evidence, other group source, shell, file,
web, task, or retry tool is available to the Translator.

## Output

For a plan containing an arithmetic group, the stored artifact is:

```text
translations/<language>/<version>/<planRunId>/Arithmetic/
  Arithmetic.lean
  translation-manifest.json
  translator-run.json
  revisions/
```

The source must be a complete group module. Shared value, state, carry, and
predicate types are declared once and reused by all member instructions. Each
instruction has a distinct `OPERATION` mapping and, when state effects or
predication exist, a distinct `EXECUTION` mapping.

`translation-manifest.json` schema version 2 records the group name and unit
IDs, every semantic run/hash, the one Lean filename, and every named Lean
declaration. Semantic mappings use `claimRefs` entries containing both
`unitId` and `claimId`; claim IDs are only required to be unique inside their
own semantic artifact. A declaration shared by several instructions can cite
several unit/claim pairs.

## Deterministic acceptance

The submission is rejected unless all of the following hold:

- the group contains exactly the Phase-2 units selected by the grouping table;
- every supplied semantic artifact is successful, current, and belongs to the
  plan and member unit;
- the source is non-empty and contains no `sorry`, `admit`, axioms, constants,
  `unsafe`, or `partial` declarations;
- every named top-level Lean declaration has exactly one mapping and every
  mapping names a declaration present in the source;
- every direct or recursively supported mapping resolves to existing
  `(unitId, claimId)` pairs without cycles;
- each instruction has its required operation/execution responsibilities; and
- the manifest and run metadata equal deterministic reconstruction from all
  current semantic artifacts.

A group artifact is reusable only if all member semantic artifacts still have
the recorded hashes. A change to one member invalidates and replaces the whole
group translation atomically.

## Revision boundary

Coverage or revised-semantics routing returns the complete current group source,
all current member semantics, and the triggering unit's diagnostics to one
bounded revision session. The revision must resubmit the complete source and
complete cross-unit mappings. Existing unaffected members must remain present.
The previous group files are preserved under `revisions/<revisionRunId>/` and
the new group is rechecked as a whole.
