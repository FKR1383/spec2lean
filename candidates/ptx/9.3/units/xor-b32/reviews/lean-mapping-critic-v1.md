# Independent Lean-Mapping Critique — XorB32-v1 (xor.b32)

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/xor-b32/lean/XorB32-v1.lean` (SHA-256 `e2694a8894d49307ce1050f835478a7963361318d5510465e5ee166df528fa0a`, 437 lines), the first Lean mapping candidate for the bounded `xor.b32` unit.
- This critique is an independent semantic-critic review of the Lean mapping against the approved Gate-B semantics. It does not approve Gate C and does not edit or repair the reviewed artifact.
- Run metadata consulted: `runs/ptx-9.3-xor.b32-23b2e519/run.json` (unit `xor.b32`, stage LEAN_MAPPING_CRITIQUE attempt 1, revision 12; Gate A approved, Gate B approved, Gate C pending).
- This is the artifact required by the orchestrator for stage LEAN_MAPPING_CRITIQUE: `candidates/ptx/9.3/units/xor-b32/reviews/lean-mapping-critic-v1.md`. It did not exist before this pass (glob of `reviews/` showed only `architecture-critic-v1.md` and `semantics-critic-v1.md`); a new immutable revision was created (no overwrite).

## 2. Overall verdict

**SUITABLE for Human Gate C presentation (no substantive revision required; Gate C not approved).**

The Lean mapping is faithful to the human-approved Gate-B semantic interpretation (`semantics-v1.json`, interpretation_id `ptx-9.3-xor-b32-semantics-v1`) and to the Gate-A-approved architecture (`foundation-v1.md`). Every load-bearing semantic element of the approved interpretation has a direct, traceable Lean counterpart:

- **Core exclusive-or semantics `d = a ^ b;`** — `xorValue` implements bitwise exclusive-or over the 32-bit untyped `.b32` bit-value domain as `Nat.xor x.toFin.val y.toFin.val % 2^32` on the `Fin (2^32)` encoding. `Nat.xor` of two values in `[0, 2^32)` stays within `[0, 2^32)` (32-bit inputs have at most 32 bits, so their bitwise xor has at most 32 bits), so the modulo is a value no-op and only makes the `Fin` bound proof definitional; the in-file explanation is accurate. Verified by executable examples: `0^0=0`, `0xFFFFFFFF^0xFFFFFFFF=0`, `0xFFFFFFFF^0=4294967295`, `5^3=6`, `0xFFFF0000^0x00FF00FF=0xFF0000FF=4278190335`. Faithful to SOURCE_FACT PTX-XOR-SEM1-032 (`d = a ^ b;`) and DERIVED PTX-XOR-SEM1-033.
- **Operand order and roles** — `XorB32Instruction` carries `d : Destination`, then `a : SourceOperand`, then `b : SourceOperand` (destination first), matching the official `xor.type d, a, b;` syntax (PTX-XOR-SEM1-003/004/005/006/061; D-1/D-16). `execXorB32` reads `i.a` then `i.b` and updates `i.d` with `xorValue va vb`; no operand-role or operand-order confusion exists (xor is commutative, so the `a`/`b` roles are semantically immaterial to the result, and the read order matches the representation).
- **Bit width / untyped domain** — `b32Bits := 32`, `b32DomainSize := 2^32`, `B32` wraps `Fin b32DomainSize`; the wrapper has no arithmetic operators, so the only operation is the explicit `xorValue` (no hidden library semantics). Faithful to PTX-XOR-SEM1-013/015/018/062 and design D-11. No signed/unsigned confusion exists: the value domain is untyped bits.
- **No modifiers** — `XorTypeSpecifier` has only the `.b32` constructor and the instruction has no modifier field, matching the no-modifier-position reading (PTX-XOR-SEM1-004/005/020).
- **Register-only source** — `SourceOperand` has only the `reg` constructor; no immediate constructor is introduced, honoring bundle GAP-1 `do_not_infer` and open question PTX-XOR-SEM1-066 (PTX-XOR-SEM1-010/043). Correctly avoids asserting semantics not present in the approved interpretation.
- **Guard predication** — `Guard` = unguarded / `@p` (`atPos`) / `@!p` (`atNeg`); `evalGuard` implements the complete guard expression exactly as specified (no guard → true; `@p` → value of `p`; `@!p` → negation of value of `p`; missing predicate → `none`/partial) (PTX-XOR-SEM1-022/037/044; D-19/D-21).
- **Guard-false consequence** — `execXorB32` returns `ExecOutcome.guardFalse s` with the state unchanged when the complete guard expression evaluates false, implementing the approved DERIVED interpretation PTX-XOR-SEM1-035 (source-resolved via section 9.7.13.2 fragments PTX-9.3-XOR-031/032 and SOURCE_FACT PTX-XOR-SEM1-028), never as a human assumption. The file's EPISTEMIC NOTE correctly preserves the Gate B lesson. In the guard-false branch the source operands are not read, which is consistent with the official "do nothing" clause and is unobservable in this state model (reads do not change state; no error behavior is evidenced); see F-4.
- **Read-before-write aliasing** — the sources are read from the pre-instruction state before the destination update, so aliasing `d == a` and `d == a == b` are modeled correctly (PTX-XOR-SEM1-065; verified by examples: `d==a` with r1=5, r2=3 gives r1 becomes 6; `d==a==b` gives 5^5=0).
- **Partial execution, no invented errors** — missing source/predicate lookups yield `none` (PARTIAL), never an error, trap, or UB, matching PTX-XOR-SEM1-052/053/054 and design D-8 (no error constructor).
- **Minimal state and locality** — `MachineState` = (value-register file, predicate-register file) only; no memory, sreg, carry-flag, or condition-code component (PTX-XOR-SEM1-060/039; D-5/D-14). `updateDestination` writes only the destination register (or nothing for the bit bucket) and preserves every other register and predicate (PTX-XOR-SEM1-038/039).
- **Bit bucket `_`** — `Destination.bitBucket` is modeled at the strength of the general section 9.2 rule (PTX-9.3-XOR-016; PTX-XOR-SEM1-011), with the scalar `xor.b32`-specific applicability explicitly recorded as open question PTX-XOR-SEM1-067; the file does not overstate its strength.
- **Relational execution semantics** — `XorB32Step` is the relational counterpart of `execXorB32` (guard-false and executed cases), implementing design D-25 / PTX-XOR-SEM1-063 so that determinism (PRF-1) and frame/locality obligations (PRF-2..PRF-5) are non-vacuous.
- **Version/target metadata** — correctly treated as validation metadata (VAL-5/VAL-6), not as state behavior (PTX-XOR-SEM1-048/049/050/051).

**Lean verification performed:**
- `lean_check_file` on `candidates/ptx/9.3/units/xor-b32/lean/XorB32-v1.lean`: **success, exitCode 0, 0 errors, 0 warnings**; the tool-reported SHA-256 matches the run.json LEAN_FORMALIZATION record.
- `lean_run_eval` on the same file: **all 14 executable examples evaluate to exactly the expected results** (see Section 6).
- Grep for `sorry`, `admit`, `axiom`, `unsafe` (plus `by omega`, `by simp [`, `native_decide` shortcuts) in the reviewed file: **no matches** (no forbidden constructs, no unchecked shortcuts).
- The file imports only `Spec2Lean.Basic` (a one-line placeholder with no axioms).

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/xor-b32/lean/XorB32-v1.lean` — complete read (437/437 lines); every declaration, traceability comment, and executable example inspected; `lean_check_file` and `lean_run_eval` executed.
- `candidates/ptx/9.3/units/xor-b32/semantics/semantics-v1.json` — complete read (338/338 lines); all 73 claims (PTX-XOR-SEM1-001..073), guard semantics, behavior, state reads/writes, preconditions, open questions, and future theorem obligation topics (PRF-1..PRF-7) checked against the Lean declarations.
- `candidates/ptx/9.3/units/xor-b32/source-bundles/source-bundle-v1.json` — complete read (958/958 lines); all 33 fragments (PTX-9.3-XOR-001..033), coverage areas, and gaps (GAP-1..GAP-8) cross-checked.
- `candidates/ptx/9.3/units/xor-b32/architecture/foundation-v1.md` — full read (273 lines); all architecture cross-references used by the Lean file (D-0c, D-1, D-5, D-8, D-11, D-12, D-13, D-14, D-16, D-18, D-19, D-21, D-25, VAL-5, VAL-6, PRF-1..PRF-7, OQ-1..OQ-8) confirmed present.
- `candidates/ptx/9.3/units/xor-b32/reviews/semantics-critic-v1.md` — full read (176 lines); the Gate-B critique precedent (verdict SUITABLE; MINOR F-1/F-2/F-3 + notes F-4..F-6).
- `reviews/ptx-xor-b32/gate-b/ptx-xor-b32-b-approval-v1.json` — verified (decision `approved`, `humanConfirmationRecorded: true`, `gateApprovalPerformed: true`, submittedAtUtc 2026-08-09T16:50:42.881Z; artifacts `semantics-v1.json` SHA-256 `815eaf68...` and `semantics-critic-v1.md` SHA-256 `b4662718...`).
- `reviews/ptx-xor-b32/gate-a/ptx-xor-b32-a-approval-v1.json` — referenced by the Lean file header; decision `approved` confirmed via the run.json history (16:08:11) and the semantics artifact.
- `lean/Spec2Lean/Basic.lean` — read in full (1 line: `def hello := "world"`); no axioms, no `sorry`, no `unsafe`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools (see Section 6) for the xor section and the false-guard clause.
- No theorem obligations, theorem statements, or proofs exist yet for this unit; the Lean mapping candidate intentionally contains no theorems (deferred to the theorem-design and proof stages). No proof critique was therefore possible or required at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | NOTE | `PredId` and `predRegs : PredId -> Option Bool` (Lean lines 121-123, 186-188) | Predicate-register value domain encoded as `Bool`; the exact encoding of the 1-bit predicate domain is an open question (PTX-XOR-SEM1-069, OQ-5) deferred to the Lean-mapping phase; the file documents this; Gate C reviewer should explicitly confirm the two-valued Bool encoding |
| F-2 | NOTE | `Destination.bitBucket` (Lean lines 149-152, 261-265, 373-376) | Bit-bucket destination is modeled at the strength of the general section 9.2 rule (PTX-XOR-SEM1-011) with scalar `xor.b32`-specific applicability still open (PTX-XOR-SEM1-067); the Lean file documents the strength and does not overstate it; Gate C reviewer should reconfirm that modeling bit bucket matches the approved semantics |
| F-3 | NOTE | File header lines 57-60; no theorem declarations | No theorem statements are included in this candidate; the architecture proof-obligation families PRF-1..PRF-7 are deferred to the theorem-design and proof stages by design; Gate C reviewer should ensure the theorem stage states the non-vacuous obligations (determinism, frame/locality, guard behavior, exclusive-or fidelity) rather than weakening them |
| F-4 | NOTE | `execXorB32` guard-false branch (Lean lines 293-303); `XorB32Step.guardFalse` (lines 318-320) | In the guard-false branch the source operands are not read; consistent with the official "Threads with a False guard predicate do nothing." clause (PTX-9.3-XOR-031) and unobservable in this state model (reads do not change state and no error behavior is evidenced); Gate C reviewer should confirm this is the intended mapping rather than reading sources first |
| F-5 | NOTE | `candidates/ptx/9.3/units/xor-b32/lean/XorB32Probe.lean` (19 lines) | A leftover probe helper file in the same namespace (`Spec2Lean.PTX.XorB32`) defines `b32DomainSize` and `xorNat` with `#eval` probes; it compiles standalone but is not part of the mapping artifact and would conflict if imported together with `XorB32-v1.lean`; hygiene note only, no semantic impact |
| F-6 | NOTE | File header lines 52-56; no state fields for version/target | Version (PTX ISA 1.0) and target (all target architectures) metadata is recorded as validation obligations (VAL-5/VAL-6), not as state behavior; consistent with the approved semantics (PTX-XOR-SEM1-048/049/050/051) |

## 5. Findings detail

### F-1 — NOTE — Predicate-register value domain encoded as `Bool`

- **Exact location:** `structure PredId` (lines 121-123) and `predRegs : PredId -> Option Bool` (line 188) of `XorB32-v1.lean`.
- **Relevant approved semantics:** PTX-XOR-SEM1-023 (predicate registers are virtual, `.pred`-typed), PTX-XOR-SEM1-069 (OQ-5: "the exact Lean encoding of the 1-bit predicate register value domain ... is a Lean-mapping decision for a later phase"), architecture D-13 (two-valued boolean-like domain) and A-7.
- **Description:** The Lean mapping encodes predicate register values as `Option Bool` (`some true`/`some false`, with `none` for an undefined predicate). This is exactly the kind of Lean-mapping decision the approved semantics defers to this phase. The file documents the choice and cites PTX-XOR-SEM1-069. No semantic drift: the two-valued domain matches the architecture's boolean-like predicate design, and the `none` case implements the approved partial-execution convention (PTX-XOR-SEM1-052/053/054).
- **Consequence:** None, provided the Gate C reviewer explicitly confirms the `Bool` encoding as the approved Lean representation of the 1-bit predicate domain.
- **Required owner:** Human Gate C reviewer (encoding confirmation); Lean Formalizer for any future revision.
- **Required revision:** None before Gate C.
- **Human review required:** Yes (Gate C confirmation of the Lean encoding).

### F-2 — NOTE — Bit-bucket destination modeled at general-rule strength

- **Exact location:** `inductive Destination` with constructor `bitBucket` (lines 149-152), `updateDestination` bit-bucket branch returning the state unchanged (lines 261-265), and example lines 373-376.
- **Relevant approved semantics:** PTX-XOR-SEM1-011 (SOURCE_FACT: general section 9.2 bit-bucket rule), PTX-XOR-SEM1-067 (OQ-2/GAP-2: scalar `xor.b32`-specific applicability remains an open question), and the semantics' `state_writes` DERIVED entry for the bit bucket at general-rule strength.
- **Description:** The candidate models `_` as a valid destination at the strength of the general rule and explicitly documents that scalar `xor.b32`-specific applicability is an open question. This is faithful: the approved semantics itself models the bit-bucket state write as a DERIVED entry grounded in PTX-9.3-XOR-016. The Lean mapping continues to read the source operands when `d = _` (the instruction still executes and computes the exclusive-or; only the write is discarded), which is consistent with the approved "result is discarded" reading and with the semantics' source-read claim (PTX-XOR-SEM1-036). No overstatement occurs.
- **Consequence:** None, provided the Gate C reviewer reconfirms that including the bit-bucket form (at general-rule strength) matches the approved interpretation and that PRF-3 will be stated over this form only at that strength.
- **Required owner:** Human Gate C reviewer (strength confirmation); Lean Formalizer for any future revision.
- **Required revision:** None before Gate C.
- **Human review required:** Yes (Gate C strength confirmation).

### F-3 — NOTE — No theorem statements in this candidate (deferred by design)

- **Exact location:** File header lines 57-60 ("No theorem statements and no proofs are included in this candidate. The proof-obligation families PRF-1..PRF-7 ... are deferred to the theorem-design and proof stages."); the file contains no `theorem` declarations.
- **Relevant approved semantics/architecture:** architecture PRF-1..PRF-7 (Section 10) and semantics `future_theorem_obligation_topics` (PRF-1..PRF-7); the workflow's separation of Lean-mapping from theorem-design/proof stages.
- **Description:** The absence of theorem statements is the correct stage behavior: this critique reviews the mapping only. However, the non-vacuity of the future theorem obligations (determinism PRF-1, destination-only frame PRF-2, bit-bucket discard PRF-3, guard-false frame PRF-4, guard-behavior PRF-5, result-domain membership PRF-6, exclusive-or fidelity PRF-7) is a theorem-stage matter that must be re-verified when those statements are written. The relational `XorB32Step` (D-25) was deliberately provided so that determinism and frame obligations are not vacuous.
- **Consequence:** None at this stage; the Gate C reviewer should note that theorem-strength approval is a separate pending gate (THEOREM_STRENGTH) after theorem statements are drafted.
- **Required owner:** Proof Engineer (future theorem-design stage); Human theorem-strength gate reviewer.
- **Required revision:** None before Gate C.
- **Human review required:** Yes (theorem-strength gate, later stage).

### F-4 — NOTE — Guard-false branch does not read source operands

- **Exact location:** `execXorB32` lines 293-303 (the `some false => some (ExecOutcome.guardFalse s)` branch) and `XorB32Step.guardFalse` lines 318-320.
- **Relevant approved semantics:** PTX-XOR-SEM1-035 (DERIVED: when the complete guard expression evaluates false, "the instruction does not execute and no state component changes"), grounded in the official clause "Threads with a False guard predicate do nothing." (PTX-9.3-XOR-031) and Semantics "If {!}p then instruction" (PTX-9.3-XOR-032).
- **Description:** The mapping returns the guard-false outcome without reading the source registers, and the relational form requires only `evalGuard s i.guard = some false`. This is consistent with the approved "do nothing" reading: the official clause does not require source reads in the guard-false case, and in this state model register reads have no observable effect (no memory accesses, no side effects, no error behavior evidenced). The alternative (reading sources first and returning `none` when a source is missing even under a false guard) would be a stricter partial-execution convention that the approved semantics does not mandate. The file documents the choice ("Source operands are NOT read in this branch").
- **Consequence:** None, provided the Gate C reviewer confirms this is the intended mapping of the guard-false case (the relational form and executable function agree).
- **Required owner:** Human Gate C reviewer (confirmation); Lean Formalizer for any future revision.
- **Required revision:** None before Gate C.
- **Human review required:** Yes (Gate C confirmation).

### F-5 — NOTE — Leftover probe helper file in the lean directory

- **Exact location:** `candidates/ptx/9.3/units/xor-b32/lean/XorB32Probe.lean` (19 lines), namespace `Spec2Lean.PTX.XorB32`.
- **Relevant approved semantics:** None directly; the probe was used during formalization to check `Nat.xor` behavior.
- **Description:** The probe file defines `b32DomainSize` and `xorNat` in the same namespace as the mapping and contains `#eval` probes. It compiles standalone (verified) but is not part of the mapping artifact; if it were ever imported together with `XorB32-v1.lean`, the duplicate `b32DomainSize` declaration would conflict. It has no effect on the reviewed artifact and no semantic impact on the mapping.
- **Consequence:** None for Gate C; optional cleanup (e.g., moving or removing the probe, or giving it a distinct namespace) at a later revision.
- **Required owner:** Lean Formalizer (optional cleanup).
- **Required revision:** None before Gate C.
- **Human review required:** No.

### F-6 — NOTE — Version/target metadata not modeled as state behavior

- **Exact location:** File header lines 52-56; the `MachineState` structure has no version/target fields.
- **Relevant approved semantics:** PTX-XOR-SEM1-048/049 (SOURCE_FACT version/target notes), PTX-XOR-SEM1-050/051 (DERIVED version/target restrictions), architecture VAL-5/VAL-6 (version/target gating as validation obligations, not execution behavior).
- **Description:** The approved semantics classifies version/target as validation metadata, and the Lean mapping correctly excludes it from execution state. The header records the base form's version/target facts for traceability. This matches the semantics and avoids inventing state behavior not evidenced.
- **Consequence:** None.
- **Required owner:** None.
- **Required revision:** None.
- **Human review required:** No.

## 6. Source-verification notes

Specification-tool calls used in this critique: 2 restricted context reads against the official PTX ISA 9.3 HTML, plus candidate read/grep and Lean tool checks.

All load-bearing source claims behind the Lean mapping's domain choices were re-verified:

- **`xor` section 9.7.8.3 (claims PTX-XOR-SEM1-004/005/007/008/032/033).** Anchor `logic-and-shift-instructions-xor` (line 14324; section 14324-14357). Confirmed: Syntax `xor.type d, a, b;` / `.type = { .pred, .b16, .b32, .b64 };` (14332-14334); Description "Bitwise exclusive-OR (inequality)." (14329) and "Compute the bit-wise exclusive-or operation for the bits in `a` and `b`." (14338); Semantics `d = a ^ b;` (14341); Notes (14345-14346); PTX ISA Notes (14348); Target ISA Notes (14350); Examples `xor.b32  d,q,r;` / `xor.b16  d,x,0x0001;` (14353-14354). All match bundle fragments PTX-9.3-XOR-001..009 and the semantics claims.
- **`.b32` is a "Bits (untyped)" fundamental type (claim PTX-XOR-SEM1-013).** Anchor `fundamental-types-fundamental-type-specifiers` (line 3025; Table 8). Span 3053-3054: "Bits (untyped)" row lists `.b8, .b16, .b32, .b64, .b128`. Confirmed. This grounds `b32Bits := 32` and the `Fin (2^32)` domain of `B32`.
- **Scalar registers may have a 32-bit width (claim PTX-XOR-SEM1-015).** Anchor `register-state-space` (line 2613). Lines 2622-2624: "aside from predicate registers which are 1-bit, scalar registers have a width of 8-, 16-, 32-, 64-, or 128-bits". Confirmed. This grounds the 32-bit `.b32` register value domain.
- **False-guard no-op clause (claims PTX-XOR-SEM1-028/035).** Anchor `control-flow-instructions-at` (line 21826). Confirmed: Description "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." (21838-21839) and Semantics "If {!}p then instruction" (21841). Matches bundle fragments PTX-9.3-XOR-031/032.
- **Predication applicability and guard syntax (claims PTX-XOR-SEM1-021/022).** Bundle fragments PTX-9.3-XOR-013/018; previously re-verified in the architecture and semantic critiques; the Lean mapping's guard constructors (unguarded/atPos/atNeg) are a direct transcription of these claims.
- **Sibling immediate examples not used to infer xor's source forms (GAP-1; claim PTX-XOR-SEM1-066).** Bundle fragments PTX-9.3-XOR-011/012 record the `or.b32  mask mask,0x00010001` and `and.b32  sign,fpvalue,0x80000000;` examples with `do_not_infer: true`; the Lean file correctly introduces no immediate constructor.

Lean verification performed:

- `lean_check_file candidates/ptx/9.3/units/xor-b32/lean/XorB32-v1.lean` → `success: true`, `exitCode: 0`, `errorCount: 0`, `warningCount: 0`.
- `lean_run_eval` on the same file → 14 output lines, each matching the expected result:
  1. `0` (0 ^ 0),
  2. `0` (0xFFFFFFFF ^ 0xFFFFFFFF),
  3. `4294967295` (0xFFFFFFFF ^ 0),
  4. `6` (5 ^ 3),
  5. `4278190335` (0xFFFF0000 ^ 0x00FF00FF = 0xFF0000FF),
  6. `some true` (unguarded complete guard expression is true),
  7. `some true` (`@!p` with p = false),
  8. `some 100` (destination register updated to 100),
  9. `some 1` (bit bucket: no value register written),
  10. `some 5` (`@p` with p = false: guard-false, r1 stays 5),
  11. `some 6` (`@!p` with p = false: executes, r1 becomes 5 ^ 3 = 6),
  12. `some 6` (aliasing `d == a`: read-before-write, r1 becomes 5 ^ 3 = 6),
  13. `some 0` (self-inverse aliasing `d == a == b`: r1 becomes 5 ^ 5 = 0),
  14. `"partial-none"` (missing source register → partial execution, not an error).
- Grep for `sorry|admit|axiom|unsafe` and shortcut tactics in `XorB32-v1.lean`: **no matches**.
- `Spec2Lean.Basic` (the only import) is a 1-line placeholder with no axioms.

Traceability verification (Lean → semantics):

- All 48 `PTX-XOR-SEM1-xxx` claim-ID citations in the Lean file were checked against `semantics-v1.json`: every cited claim exists (001-073 range) and matches the cited content — including 003/004/005/006/010/011/013/015/018/020/022/023/028/032/033/034/035/036/037/038/039/043/044/048/049/050/051/052/053/054/060/061/062/063/064/065/066/067/068/069/072. No phantom claim IDs, no out-of-bundle semantic evidence, no add.u32/mov.b32 semantic import.
- Fragment citations (`PTX-9.3-XOR-009/011/012/016/031/032`) all exist in the bundle with the cited content.
- The file's namespace `Spec2Lean.PTX.XorB32` matches the run metadata's Lean module base name `XorB32`.

## 7. Required revisions (consolidated)

No substantive revisions are required before Gate C. Optional confirmations for the human Gate C reviewer:

1. Explicitly confirm the `Bool` encoding of the 1-bit predicate register value domain (F-1; PTX-XOR-SEM1-069/OQ-5).
2. Reconfirm the bit-bucket destination at general-rule strength (F-2; PTX-XOR-SEM1-067/OQ-2).
3. Note that theorem statements (PRF-1..PRF-7) are deferred to the theorem-design stage and that theorem-strength approval is a separate pending gate (F-3).
4. Confirm the guard-false branch behavior (sources not read; state unchanged) as the intended mapping (F-4).
5. Optional cleanup of the leftover probe file `XorB32Probe.lean` (F-5).
6. No action needed for F-6.

## 8. Residual open questions

- Will the Gate C reviewer accept `Fin (2^32)` as the approved Lean encoding of the 32-bit untyped `.b32` bit-value domain (design D-11, PTX-XOR-SEM1-062)? The mapping is consistent with the design's "exact Lean representation is a Lean-mapping decision" note.
- Will the Gate C reviewer accept the `Option`-based partial-execution representation (missing register/predicate → `none`, not error) as the approved encoding of PTX-XOR-SEM1-052/053/054 and design D-8?
- Will the theorem-design stage state PRF-1..PRF-7 at full strength over the relational `XorB32Step` (D-25) so that determinism and frame obligations remain non-vacuous (F-3)?
- Does the Gate C reviewer reconfirm that the bounded base unit (scalar `.b32` form only, register-only source, no immediate) matches the intended `xor.b32` unit (D-0c)?

## 9. Gate C readiness assessment

Ready for presentation to Human Gate C. The Lean mapping is source-faithful (all domain choices re-verified against the official HTML anchors, the xor section, and the false-guard clause), traceable (48 valid semantic claim citations; fragment citations valid), Lean-verified (0 errors, 0 warnings; 14/14 executable examples correct; no `sorry`/`admit`/axioms/`unsafe`), and consistent with the human-approved architecture scope (foundation-v1, Gate A approved) and the human-approved semantic interpretation (semantics-v1, Gate B approved). The mapping does not weaken semantics, does not invent behavior (no immediate source, no invented errors, bit bucket at documented general-rule strength), preserves the guard-false consequence as an approved DERIVED interpretation rather than a human assumption, and correctly implements read-before-write aliasing. The six NOTE findings are confirmations for the human reviewer, not defects. This assessment is not a Gate C approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/xor-b32/lean/XorB32-v1.lean`. No Lean definitions were rewritten, no semantics were altered, no source evidence was fabricated, and no theorem statements were weakened (none exist). No gates were approved and nothing was promoted to `accepted/`.
