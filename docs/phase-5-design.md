# Phase 5: Group Lean Translator

## Contract

Phase 5 consumes every accepted Phase-4 `semantics.json` belonging to one
Phase-2 translation group and produces exactly one complete Lean 4 source
file for that group. It never creates per-instruction fragments or `Unit.lean`
files.

Phase 5 contains no PTX-, mnemonic-, or language-specific category table. The
Phase-2 Planner derives group names and membership from the indexed
specification, and deterministic validation requires an exact, source-supported
partition of all requested units. Phase 5 only consumes that validated plan.

The pipeline finishes Phases 3 and 4 for all requested units before starting
Phase 5. It then runs one bounded OpenCode Translator session per non-empty
group, using `openai/gpt-5.6-sol` with medium reasoning. The session receives:

- a group scope containing all member units and semantic-artifact hashes;
- the complete Phase-4 artifacts keyed by unit ID; and
- one submission tool.

No specification database, Phase-3 evidence, other group source, shell, file,
web, task, or retry tool is available to the Translator.

## Output

For a plan containing a group named `IntegerOperations`, the stored artifact is:

```text
translations/<language>/<version>/<planRunId>/IntegerOperations/
  IntegerOperations.lean
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

The submission validator stores fully qualified declaration names. An exact
source name takes precedence; otherwise a namespace-relative name is expanded
only when it matches exactly one declaration in the submitted source. The same
rule applies to `supportsDeclarations`. Ambiguous names, duplicate aliases,
unknown claims, and missing mappings remain errors. This normalization changes
neither the Lean source nor the model's roles or claim associations.

Rejected submissions include a `repairContext` with the source's exact declaration
names and the allowed `(unitId, claimId)` pairs. Mapping-only corrections should
preserve the source and fix the mappings within the same bounded session.
Timeouts retain readable partial output in the session artifact and report the
original timeout error. The configured time limit still applies.

## Deterministic acceptance

The submission is rejected unless all of the following hold:

- the group contains exactly the Phase-2 units in the validated plan partition;
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
