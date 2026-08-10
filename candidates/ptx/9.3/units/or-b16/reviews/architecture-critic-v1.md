# Independent Architecture Critique — or-b16 (foundation-v1)

## 1. Reviewed artifact
- `candidates/ptx/9.3/units/or-b16/architecture/foundation-v1.md` (draft, 128 lines)
- Sources checked: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, `documents/sources/nvidia/ptx/9.3/source-manifest.json`
- Run state checked: `runs/ptx-9.3-or.b16-ab7bd730/run.json`

This critique does **not** approve Gate A.

## 2. Verdict
**SUCCESS** (no BLOCKER or MAJOR findings; two non-blocking findings remain)

## 3. Findings

| ID | Severity | Affected artifact | Location | Evidence refs | Required owner | Human review required |
|----|----------|------------------|----------|---------------|----------------|----------------------|
| ARCH-1 | MINOR | `candidates/ptx/9.3/units/or-b16/architecture/foundation-v1.md` | §3 (A-2), §4 (mapping), §87–104 (VO-1..SO-5), lines 35–37 / 54 / 94–95 | `foundation-v1.md` (A-2, A-3, VO-4/VO-5); PTX `logic-and-shift-instructions-or` lines 14298–14308; `constants` lines 2069–2073 | Spec Architect / Gate A | Yes |
| ARCH-2 | MINOR | `candidates/ptx/9.3/units/or-b16/architecture/foundation-v1.md` | §2 & §6/67, lines 67, 69–72 | SF-OR-12, `variables` line 3755, `register-state-space` lines 2622–2624 | Spec Architect / Gate A | Yes |

### ARCH-1 detail
- **Description:** The candidate makes `src1` register-only in the bounded architecture (A-2), while also allowing `src2` to be either register or immediate. This asymmetry is plausible as a bounded parsing choice, but the fact-to-design mapping presents it as a design consequence of the family facts (SF-OR-1/SF-OR-3), and the only textual support for immediate operands is the generic constants permission (`constants`) plus an `or.b32` example in the `b` position (SF-OR-6/SF-OR-7 equivalent). This leaves source-position asymmetry insufficiently justified in-source and could silently exclude valid concrete syntax if parser evidence later shows immediate in source1 is legal.
- **Consequence:** Risk of an unnecessarily narrow formal language without explicit and localized parser rationale; downstream translation/proofs may depend on assumptions not explicitly guarded as open design constraints.
- **Required revision:** Keep source1 restricted but document as a declared parser-bound restriction in a clearly labeled assumption; avoid mapping it as mandatory source-derived design consequence, or gather direct parser evidence for source-position freedom.

### ARCH-2 detail
- **Description:** The architecture separates predicate runtime (`PredFile`) from register file (`RegFile`), while source-state assumptions state only `.pred` may live in register space (SF-OR-12 + register-space statement). It is not explicit whether predicates in this unit are represented as dedicated boolean storage **independent of** register-typed values or as part of a uniform value domain, yet downstream predicates are read for guards and could also be used as non-guard operands in the language note “Allowed types include predicate registers.”
- **Consequence:** The current design may conflate two semantic models (split boolean pred storage + bit-pattern registers) without recording whether `or.b16` can legally consume predicate-typed operands in this bounded unit; later Lean mapping could over-constrain or mishandle predicate typed operands/decls.
- **Required revision:** Add an explicit bounded design decision (or evidence) on whether predicate typed operands are in-scope for this unit; if out-of-scope, state this as an explicit exclusion decision tied to `ASS-1`.

## 4. Readiness for Human Gate A
- No BLOCKER/MAJOR defects identified; still send to Human Gate A with the above MINOR issues called out for design cleanup.

## 5. Disposition
- BLOCKER: 0
- MAJOR: 0
- MINOR: 2
- NOTE: 0
- Pre-gate revision required: **No** (non-blocking findings only)
