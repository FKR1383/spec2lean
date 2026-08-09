# Independent Lean-Mapping Critique — NotB32-v1 (not-b32)

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/not-b32/lean/NotB32-v1.lean` (SHA-256 `d73332a9ce0ce44b6b4d7981266d5c79c0adfd2a9a63d53353583a8ed2f46d8f`, 413 lines), the first Lean mapping candidate for the bounded `not.b32` unit.
- This critique is an independent semantic-critic review of the Lean mapping against the approved Gate-B semantics. It does not approve Gate C and does not edit or repair the reviewed artifact.
- Run metadata consulted: `runs/ptx-9.3-not.b32-5e83de43/run.json` (unit `not.b32`, stage LEAN_MAPPING_CRITIQUE attempt 1, revision 12; Gate A approved, Gate B approved, Gate C pending; prior LEAN_MAPPING_CRITIQUE attempt was interrupted before producing this artifact and is recorded as RETRY).
- This is the artifact required by the orchestrator for stage LEAN_MAPPING_CRITIQUE: `candidates/ptx/9.3/units/not-b32/reviews/lean-mapping-critic-v1.md`. It did not exist before this pass; a new immutable revision was created (no overwrite).

## 2. Overall verdict

**SUITABLE for Human Gate C presentation (no substantive revision required; Gate C not approved).**

The Lean mapping is faithful to the human-approved Gate-B semantic interpretation (`semantics-v1.json`, interpretation_id `ptx-9.3-not-b32-semantics-v1`) and to the Gate-A-approved architecture (`foundation-v2.md`). Every load-bearing semantic element of the approved interpretation has a direct, traceable Lean counterpart:

- **Core complement semantics `d = ~a;`** — `complementValue` implements bitwise complement over the 32-bit untyped `.b32` bit-value domain as `(2^32 - 1) - v` on the `Fin (2^32)` encoding (verified by executable examples: `~0 = 0xFFFFFFFF`, `~0xFFFFFFFF = 0`, `~5 = 0xFFFFFFFA = 4294967290`). Faithful to SOURCE_FACT PTX-NOT-SEM1-032 and DERIVED PTX-NOT-SEM1-033.
- **Operand order and roles** — `NotB32Instruction` carries `d : Destination` then `a : SourceOperand` (destination first), matching the official `not.type d, a;` syntax (PTX-NOT-SEM1-006/061; D-1/D-16). `evalSource` reads the source register; `updateDestination` writes only the destination register and preserves predicate registers (PTX-NOT-SEM1-036/038/039).
- **Register-only source** — `SourceOperand` has only the `reg` constructor; no immediate constructor is introduced, honoring bundle GAP-1 `do_not_infer` and open question PTX-NOT-SEM1-066 (PTX-NOT-SEM1-010/043). Correctly avoids asserting semantics not present in the approved interpretation.
- **Guard predication** — `Guard` = unguarded / `@p` / `@!p`; `evalGuard` implements the complete guard expression exactly as specified (no guard → true; `@p` → value of `p`; `@!p` → negation of value of `p`; missing predicate → none/partial) (PTX-NOT-SEM1-022/037/044; D-19/D-21).
- **Guard-false consequence** — `execNotB32` returns `ExecOutcome.guardFalse s` with the state unchanged and does not read source operands in that branch, implementing the approved DERIVED interpretation PTX-NOT-SEM1-035 (source-resolved via section 9.7.13.2 fragments PTX-9.3-NOT-031/032), never as a human assumption. The file's EPISTEMIC NOTE correctly preserves the Gate B lesson.
- **Read-before-write aliasing** — the source is read from the pre-instruction state before the destination update, so `not.b32 mask,mask;` (official example) is modeled correctly (PTX-NOT-SEM1-065; verified by example: r1 = 5, `d == a == r1` → r1 becomes `~5 = 4294967290`).
- **Partial execution, no invented errors** — missing source/predicate lookups yield `none` (PARTIAL), never an error, trap, or UB, matching PTX-NOT-SEM1-052/053/054 and design D-8 (no error constructor).
- **Minimal state** — `MachineState` = (value-register file, predicate-register file) only; no memory, sreg, carry-flag, or condition-code component (PTX-NOT-SEM1-060/039; D-5/D-14).
- **Bit bucket `_`** — `Destination.bitBucket` is modeled at the strength of the general section 9.2 rule (PTX-9.3-NOT-016; PTX-NOT-SEM1-011), with the scalar `not.b32`-specific applicability explicitly recorded as open question PTX-NOT-SEM1-067; the file does not overstate its strength.
- **No modifiers** — `NotTypeSpecifier.b32` only, with no modifier field, matching the no-modifier-position reading (PTX-NOT-SEM1-020).
- **Relational execution semantics** — `NotB32Step` is the relational counterpart of `execNotB32` (guard-false and executed cases), implementing design D-25 / PTX-NOT-SEM1-063 so that determinism (PRF-1) and frame/locality obligations (PRF-2..PRF-5) are non-vacuous.
- **Version/target metadata** — correctly treated as validation metadata (VAL-5/VAL-6), not as state behavior (PTX-NOT-SEM1-048/049/050/051).

**Lean verification performed:**
- `lean_check_file` on `candidates/ptx/9.3/units/not-b32/lean/NotB32-v1.lean`: **success, exitCode 0, 0 errors, 0 warnings**.
- `lean_run_eval` on the same file: **all 11 executable examples evaluate to exactly the expected results** (see Section 6).
- Grep for `sorry`, `admit`, `axiom`, `unsafe` in the reviewed file and its directory: **no matches** (no forbidden constructs).
- The file imports only `Spec2Lean.Basic` (a one-line placeholder with no axioms).

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/not-b32/lean/NotB32-v1.lean` — complete read (413/413 lines); every declaration, traceability comment, and executable example inspected; `lean_check_file` and `lean_run_eval` executed.
- `candidates/ptx/9.3/units/not-b32/semantics/semantics-v1.json` — complete read (337/337 lines); all 73 claims (PTX-NOT-SEM1-001..073), guard semantics, behavior, state reads/writes, preconditions, open questions, and future theorem obligation topics (PRF-1..PRF-7) checked against the Lean declarations.
- `candidates/ptx/9.3/units/not-b32/source-bundles/source-bundle-v1.json` — complete read (956/956 lines); all 33 fragments (PTX-9.3-NOT-001..033), coverage areas, and gaps (GAP-1..GAP-8) cross-checked.
- `candidates/ptx/9.3/units/not-b32/architecture/foundation-v2.md` — full read (298 lines); all architecture cross-references used by the Lean file (D-0c, D-1, D-5, D-8, D-11, D-12, D-13, D-14, D-16, D-18, D-19, D-21, D-25, VAL-5, VAL-6, PRF-1..PRF-7, OQ-1..OQ-8) confirmed present.
- `candidates/ptx/9.3/units/not-b32/reviews/semantics-critic-v1.md` — full read (151 lines); the Gate-B critique precedent (verdict SUITABLE; MINOR F-1 + notes F-2..F-4).
- `reviews/ptx-not-b32/gate-b/ptx-not-b32-b-approval-v1.json` — verified (decision `approved`, `humanConfirmationRecorded: true`, submittedAtUtc 2026-08-09T12:53:51.135Z; artifacts `semantics-v1.json` SHA-256 `477f9408...` and `semantics-critic-v1.md` SHA-256 `e09d5fe1...`).
- `reviews/ptx-not-b32/gate-a/ptx-not-b32-a-approval-v1.json` — referenced by the Lean file header; decision `approved` confirmed via run.json history (12:23:43.550Z) and the semantics artifact.
- `lean/Spec2Lean/Basic.lean` — read in full (1 line: `def hello := "world"`); no axioms, no `sorry`, no `unsafe`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools (see Section 6) for the two load-bearing `.b32`-domain anchors plus the not section and the false-guard clause.
- No theorem obligations, theorem statements, or proofs exist yet for this unit; the Lean mapping candidate intentionally contains no theorems (deferred to the theorem-design and proof stages). No proof critique was therefore possible or required at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | NOTE | `PredId` and `predRegs : PredId -> Option Bool` (Lean lines 120-122, 185-187) | Predicate-register value domain encoded as `Bool`; the exact encoding of the 1-bit predicate domain is an open question (PTX-NOT-SEM1-069, OQ-5) deferred to the Lean-mapping phase; the file documents this; Gate C reviewer should explicitly confirm the two-valued Bool encoding |
| F-2 | NOTE | `Destination.bitBucket` (Lean lines 148-151, 258-262, 361-362) | Bit-bucket destination is modeled at the strength of the general section 9.2 rule (PTX-NOT-SEM1-011) with scalar `not.b32`-specific applicability still open (PTX-NOT-SEM1-067); the Lean file documents the strength and does not overstate it; Gate C reviewer should reconfirm that modeling bit bucket (with the source still read when `d = _`) matches the approved semantics |
| F-3 | NOTE | File header lines 56-59; no theorem declarations | No theorem statements are included in this candidate; the architecture proof-obligation families PRF-1..PRF-7 are deferred to the theorem-design and proof stages by design; Gate C reviewer should ensure the theorem stage states the non-vacuous obligations (determinism, frame/locality, guard behavior, bit-complement fidelity) rather than weakening them |
| F-4 | NOTE | File header lines 52-55; no state fields for version/target | Version (PTX ISA 1.0) and target (all target architectures) metadata is recorded as validation obligations (VAL-5/VAL-6), not as state behavior; consistent with the approved semantics (PTX-NOT-SEM1-048/049/050/051) |

## 5. Findings detail

### F-1 — NOTE — Predicate-register value domain encoded as `Bool`

- **Exact location:** `structure PredId` (lines 120-122) and `predRegs : PredId -> Option Bool` (line 187) of `NotB32-v1.lean`.
- **Relevant approved semantics:** PTX-NOT-SEM1-023 (predicate registers are virtual, `.pred`-typed), PTX-NOT-SEM1-069 (OQ-5: "the exact Lean encoding of the 1-bit predicate register value domain ... is a Lean-mapping decision for a later phase"), architecture D-13 (two-valued boolean-like domain) and A-7.
- **Description:** The Lean mapping encodes predicate register values as `Option Bool` (`some true`/`some false`, with `none` for an undefined predicate). This is exactly the kind of Lean-mapping decision the approved semantics defers to this phase. The file documents the choice and cites PTX-NOT-SEM1-069. No semantic drift: the two-valued domain matches the architecture's boolean-like predicate design, and the `none` case implements the approved partial-execution convention (PTX-NOT-SEM1-052/053/054).
- **Consequence:** None, provided the Gate C reviewer explicitly confirms the `Bool` encoding as the approved Lean representation of the 1-bit predicate domain.
- **Required owner:** Human Gate C reviewer (encoding confirmation); Lean Formalizer for any future revision.
- **Required revision:** None before Gate C.
- **Human review required:** Yes (Gate C confirmation of the Lean encoding).

### F-2 — NOTE — Bit-bucket destination modeled at general-rule strength

- **Exact location:** `inductive Destination` with constructor `bitBucket` (lines 148-151), `updateDestination` bit-bucket branch returning the state unchanged (lines 258-262), and example lines 359-362.
- **Relevant approved semantics:** PTX-NOT-SEM1-011 (SOURCE_FACT: general section 9.2 bit-bucket rule), PTX-NOT-SEM1-067 (OQ-2/GAP-2: scalar `not.b32`-specific applicability remains an open question), and the semantics' `state_writes` DERIVED entry for the bit bucket at general-rule strength.
- **Description:** The candidate models `_` as a valid destination at the strength of the general rule and explicitly documents that scalar `not.b32`-specific applicability is an open question. This is faithful: the approved semantics itself models the bit-bucket state write as a DERIVED entry grounded in PTX-9.3-NOT-016. The Lean mapping also continues to read the source operand when `d = _` (the instruction still executes and computes the complement; only the write is discarded), which is consistent with the approved "result is discarded" reading and with the semantics' source-read claim (PTX-NOT-SEM1-036). No overstatement occurs.
- **Consequence:** None, provided the Gate C reviewer reconfirms that including the bit-bucket form (at general-rule strength, with source read) matches the approved interpretation and that PRF-3 will be stated over this form only at that strength.
- **Required owner:** Human Gate C reviewer (strength confirmation); Lean Formalizer for any future revision.
- **Required revision:** None before Gate C.
- **Human review required:** Yes (Gate C strength confirmation).

### F-3 — NOTE — No theorem statements in this candidate (deferred by design)

- **Exact location:** File header lines 56-59 ("No theorem statements and no proofs are included in this candidate. The proof-obligation families PRF-1..PRF-7 ... are deferred to the theorem-design and proof stages."); the file contains no `theorem` declarations.
- **Relevant approved semantics/architecture:** architecture PRF-1..PRF-7 (Section 10) and semantics `future_theorem_obligation_topics` (PRF-1..PRF-7); semantics status `gate_b_status: NOT READY` (since superseded by Gate B approval) and the workflow's separation of Lean-mapping from theorem-design/proof stages.
- **Description:** The absence of theorem statements is the correct stage behavior: this critique reviews the mapping only. However, the non-vacuity of the future theorem obligations (determinism PRF-1, destination-only frame PRF-2, bit-bucket discard PRF-3, guard-false frame PRF-4, guard-behavior PRF-5, result-domain membership PRF-6, bit-complement fidelity PRF-7) is a theorem-stage matter that must be re-verified when those statements are written. The relational `NotB32Step` (D-25) was deliberately provided so that determinism and frame obligations are not vacuous.
- **Consequence:** None at this stage; the Gate C reviewer should note that theorem-strength approval is a separate pending gate (THEOREM_STRENGTH) after theorem statements are drafted.
- **Required owner:** Proof Engineer (future theorem-design stage); Human theorem-strength gate reviewer.
- **Required revision:** None before Gate C.
- **Human review required:** Yes (theorem-strength gate, later stage).

### F-4 — NOTE — Version/target metadata not modeled as state behavior

- **Exact location:** File header lines 52-55; the `MachineState` structure has no version/target fields.
- **Relevant approved semantics:** PTX-NOT-SEM1-048/049 (SOURCE_FACT version/target notes), PTX-NOT-SEM1-050/051 (DERIVED version/target restrictions), architecture VAL-5/VAL-6 (version/target gating as validation obligations, not execution behavior).
- **Description:** The approved semantics classifies version/target as validation metadata, and the Lean mapping correctly excludes it from execution state. The header records the base form's version/target facts for traceability. This matches the semantics and avoids inventing state behavior not evidenced.
- **Consequence:** None.
- **Required owner:** None.
- **Required revision:** None.
- **Human review required:** No.

## 6. Source-verification notes

Specification-tool calls used in this critique: 3 restricted context reads and 1 restricted span read against the official PTX ISA 9.3 HTML, plus candidate read/grep and Lean tool checks.

All load-bearing source claims behind the Lean mapping's domain choices were re-verified:

- **`.b32` is a "Bits (untyped)" fundamental type (claim PTX-NOT-SEM1-013).** Anchor `fundamental-types-fundamental-type-specifiers` (line 3025; Table 8). Span 3053-3054: "Bits (untyped)" row lists `.b8, .b16, .b32, .b64, .b128`. Confirmed. This grounds `b32Bits := 32` and the `Fin (2^32)` domain of `B32`.
- **Scalar registers may have a 32-bit width (claim PTX-NOT-SEM1-015).** Anchor `register-state-space` (line 2613). Lines 2622-2624: "aside from predicate registers which are 1-bit, scalar registers have a width of 8-, 16-, 32-, 64-, or 128-bits". Confirmed. This grounds the 32-bit `.b32` register value domain.
- **not section syntax and semantics (claims PTX-NOT-SEM1-004/007/008/032).** Anchor `logic-and-shift-instructions-not` (line 14358). Confirmed: syntax `not.type d, a;` with `.type = { .pred, .b16, .b32, .b64 };` (14366-14368), Description "Invert the bits in `a`." (14372), Semantics `d = ~a;` (14375), Notes (14379-14380), PTX ISA Notes (14382), Target ISA Notes (14384), Examples `not.b32  mask,mask;` / `not.pred  p,q;` (14387-14388). All match the bundle fragments PTX-9.3-NOT-001..009 and the semantics claims.
- **False-guard no-op clause (claims PTX-NOT-SEM1-028/035).** Anchor `control-flow-instructions-at` (line 21826). Confirmed: Description "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." (21838-21839) and Semantics "If {!}p then instruction" (21841). Matches bundle fragments PTX-9.3-NOT-031/032.
- **Predication applicability and guard syntax (claims PTX-NOT-SEM1-021/022).** Bundle fragments PTX-9.3-NOT-013/018; previously re-verified in the architecture and semantic critiques; the Lean mapping's guard constructors (unguarded/atPos/atNeg) are a direct transcription of these claims.
- **Sibling immediate examples not used to infer not's source forms (GAP-1; claim PTX-NOT-SEM1-066).** Bundle fragments PTX-9.3-NOT-011/012 record the `or.b32  mask mask,0x00010001` and `xor.b16  d,x,0x0001;` examples with `do_not_infer: true`; the Lean file correctly introduces no immediate constructor.

Lean verification performed:

- `lean_check_file candidates/ptx/9.3/units/not-b32/lean/NotB32-v1.lean` → `success: true`, `exitCode: 0`, `errorCount: 0`, `warningCount: 0`.
- `lean_run_eval` on the same file → 11 output lines, each matching the expected result:
  1. `4294967295` (complement of 0 = 0xFFFFFFFF),
  2. `0` (complement of 0xFFFFFFFF),
  3. `4294967290` (complement of 5 = 0xFFFFFFFA),
  4. `some true` (unguarded complete guard expression is true),
  5. `some true` (`@!p` with p = false),
  6. `some 100` (destination register updated to 100),
  7. `some 1` (bit bucket: no value register written),
  8. `some 5` (`@p` with p = false: guard-false, r1 stays 5),
  9. `some 4294967290` (`@!p` with p = false: executes, r1 becomes ~5),
  10. `some 4294967290` (aliasing `d == a == r1`: read-before-write, r1 becomes ~5),
  11. `"partial-none"` (missing source register → partial execution, not an error).
- Grep for `sorry|admit|axiom|unsafe` under `candidates/ptx/9.3/units/not-b32/lean/`: **no matches** (the only `axiom`/`unsafe` strings elsewhere in the repository are prose in other units' proof files, e.g. `MovB32Proofs.lean`/`AddU32Proofs.lean` comments, not in this candidate).
- `Spec2Lean.Basic` (the only import) is a 1-line placeholder with no axioms.

Traceability verification (Lean → semantics):

- All 48 `PTX-NOT-SEM1-xxx` claim-ID citations in the Lean file were checked against `semantics-v1.json`: every cited claim exists (001-073 range) and matches the cited content. No phantom claim IDs, no out-of-bundle semantic evidence, no add.u32/mov.b32 semantic import.
- Fragment citations (`PTX-9.3-NOT-009/011/012/016/031/032`) all exist in the bundle with the cited content.
- The file's namespace `Spec2Lean.PTX.NotB32` matches the run metadata's Lean module base name `NotB32`.

## 7. Required revisions (consolidated)

No substantive revisions are required before Gate C. Optional confirmations for the human Gate C reviewer:

1. Explicitly confirm the `Bool` encoding of the 1-bit predicate register value domain (F-1; PTX-NOT-SEM1-069/OQ-5).
2. Reconfirm the bit-bucket destination at general-rule strength, including that the source is still read when `d = _` (F-2; PTX-NOT-SEM1-067/OQ-2).
3. Note that theorem statements (PRF-1..PRF-7) are deferred to the theorem-design stage and that theorem-strength approval is a separate pending gate (F-3).
4. No action needed for F-4.

## 8. Residual open questions

- Will the Gate C reviewer accept `Fin (2^32)` as the approved Lean encoding of the 32-bit untyped `.b32` bit-value domain (design D-11, PTX-NOT-SEM1-062)? The mapping is consistent with the design's "exact Lean representation is a Lean-mapping decision" note.
- Will the Gate C reviewer accept the `Option`-based partial-execution representation (missing register/predicate → `none`, not error) as the approved encoding of PTX-NOT-SEM1-052/053/054 and design D-8?
- Will the theorem-design stage state PRF-1..PRF-7 at full strength over the relational `NotB32Step` (D-25) so that determinism and frame obligations remain non-vacuous (F-3)?
- Does the Gate C reviewer reconfirm that the bounded base unit (scalar `.b32` form only, register-only source, no immediate) matches the intended `not.b32` unit (D-0c)?

## 9. Gate C readiness assessment

Ready for presentation to Human Gate C. The Lean mapping is source-faithful (all domain choices re-verified against the official HTML anchors, the not section, and the false-guard clause), traceable (48 valid semantic claim citations; fragment citations valid), Lean-verified (0 errors, 0 warnings; 11/11 executable examples correct; no `sorry`/`admit`/axioms/`unsafe`), and consistent with the human-approved architecture scope (foundation-v2, Gate A approved) and the human-approved semantic interpretation (semantics-v1, Gate B approved). The mapping does not weaken semantics, does not invent behavior (no immediate source, no invented errors, bit bucket at documented general-rule strength), and preserves the guard-false consequence as an approved DERIVED interpretation rather than a human assumption. The four NOTE findings are confirmations for the human reviewer, not defects. This assessment is not a Gate C approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/not-b32/lean/NotB32-v1.lean`. No Lean definitions were rewritten, no semantics were altered, no source evidence was fabricated, and no theorem statements were weakened (none exist). No gates were approved and nothing was promoted to `accepted/`.
