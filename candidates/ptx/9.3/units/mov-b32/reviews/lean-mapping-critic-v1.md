# Independent Lean-Mapping Critique — mov-b32 MovB32-v1.lean

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/mov-b32/lean/MovB32-v1.lean` (387 lines, SHA-256 `c1ddad160a64c52e9f0ec8781d11236ed23f9dfd4e45595d287db9d74c7b8876`, 17206 bytes), the Lean formalization candidate for the bounded `mov.b32` unit, produced at LEAN_FORMALIZATION (run history, 2026-08-07T12:25:29).
- This critique is an independent semantic-critic review of the Lean mapping. It does not approve Gate C and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines), via the restricted specification tools.
- Source bundle consulted: `candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v2.json` (bundle_id `ptx-9.3-mov-b32-source-bundle-v2`, 38 fragments `PTX-9.3-MOV-001..038`).
- Approved semantics consulted: `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json` (interpretation_id `ptx-9.3-mov-b32-semantics-v2`, 76 claims; approved at Human Gate B per `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-approval-v1.json`, decision `approved`, submittedAtUtc `2026-08-07T12:17:30.903Z`, recorded artifact SHA-256 `904e10e14e06547c90e1efab4d84401c87fdbd9640c758c60bf17efb2a0bbcb8`).
- Approved language architecture consulted: `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md` (human-approved at Gate A per `reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json`, decision `approved`).
- Prior reviews consulted: `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md` (findings F-1..F-5) and `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v1.md`.
- Run metadata consulted: `runs/ptx-9.3-mov.b32-f910feea/run.json` (unit `mov.b32`, stage LEAN_MAPPING_CRITIQUE attempt 1, revision 15, Gate A approved, Gate B approved, Gate C pending).

## 2. Overall verdict

**SUITABLE for Human Gate C presentation (no substantive revision required).**

The Lean mapping faithfully realizes the Gate-B-approved bounded semantics (`semantics-v2.json`) within the Gate-A-approved architecture scope. Every semantic definition in the candidate is traceable by explicit comment to exact semantic claim IDs (`PTX-MOV-SEM2-*`) that exist in the approved interpretation, and every load-bearing source fact used by the mapping was independently re-verified verbatim against the official PTX ISA 9.3 HTML. Key semantic commitments match the approved interpretation:

- operand order `d, a` (destination first) with a single source (SEM2-010/059);
- `.b32` as a 32-bit untyped bit-value domain of size 2^32 (SEM2-016/021/060; D-11);
- source read from the pre-instruction state, immediate as constant value (SEM2-026/030);
- guard semantics unguarded/`@p`/`@!p` with negation (SEM2-009/027/031; D-19);
- guard-false → instruction does not execute, state unchanged (SEM2-034/038, DERIVED; section 9.7.13.2 source-resolved, not an assumption);
- explicit copy rule `copyValue` = `d = a;` (SEM2-035/036), no arithmetic/truncation;
- only the destination value register is written on execution; no extra state effects (SEM2-032/033);
- aliasing/read-before-write: source read before destination update (SEM2-062);
- no error constructor; missing register/predicate lookup is PARTIAL execution `none` (SEM2-041/042/043; D-8);
- minimal state = (value-register file, predicate-register file) (SEM2-058; D-5/D-14);
- relational execution form `MovB32Step` per D-25/SEM2-061, with the function/relation correspondence explicitly deferred to the theorem stage (PRF-1 family).

Lean verification performed independently in this critique: `lean_check_file` exit 0, 0 errors, 0 warnings; `lean_get_diagnostics` 0 errors/0 warnings/0 information; `lean_run_eval` produced exactly the 9 expected outputs (`3735928559`, `some true` x2, `some 100`, `some 1`, `some 5`, `some 7`, `some 5`, `"partial-none"`) matching the copy rule, unguarded and negated-guard evaluation, destination-only update, bit-bucket discard, guard-false unchanged state, aliasing self-copy, and partial execution. A source scan confirms no `sorry`, `admit`, `axiom`, `unsafe`, `partial`, or `opaque` declarations (grep hits are comments/strings only), and the only import (`Spec2Lean.Basic`) defines `hello := "world"` — it is a placeholder that introduces no axioms or hidden trust.

Findings are limited to one MINOR observation (the bit-bucket destination constructor is materialized although its scalar `mov.b32` applicability is an OPEN_QUESTION in the approved semantics; the mapping annotates this honestly at general-rule strength) and five NOTE-level observations (guard-false branch does not read source operands — a source-supported mapping decision; no theorem statements or proofs exist in this candidate, so vacuity/strength checks are deferred by design; the relation/function correspondence is unproven by design; the semantics SHA-256 is not cited in the Lean header, only the path and interpretation ID; the `Spec2Lean.Basic` import is unused). None of these change the semantic content, and none require revision before Gate C presentation. Compilation success was confirmed but is explicitly not treated as proof of source faithfulness: the mapping was checked claim-by-claim against the approved semantics and the official evidence. The artifact is ready to be presented to Human Gate C; Gate C is not approved by this review.

## 3. Inputs reviewed

Required inputs for a Lean-mapping critique:

1. **Bounded source bundle** — `candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v2.json` (38 fragments `PTX-9.3-MOV-001..038`): present and read.
2. **Exact evidence fragment IDs** — `PTX-9.3-MOV-001..038`: present; load-bearing fragments re-verified verbatim against the official HTML (see Section 7).
3. **Semantic interpretation candidate** — `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json`: present, read in full (374 lines), Gate-B-approved.
4. **Approved language architecture** — `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md`: present, cross-references D-1/D-5/D-8/D-11/D-14/D-16/D-18/D-19/D-21/D-25 and PRF-1..PRF-7 verified present in the architecture text.
5. **Lean definitions** — `candidates/ptx/9.3/units/mov-b32/lean/MovB32-v1.lean`: present, read in full (387 lines), compiled and evaluated.
6. **Traceability from semantic claims to Lean definitions** — present via per-declaration comments citing `PTX-MOV-SEM2-*` IDs; independently checked (Section 5).
7. **Theorem obligations** — `PRF-1..PRF-7` are recorded as future theorem topics in the approved semantics (`future_theorem_obligation_topics`) and in architecture Section 10; the Lean candidate defers them to the theorem-design/proof stages.
8. **Theorem statements** — **MISSING by design**: the candidate contains no theorem statements; the Lean header explicitly defers PRF-1..PRF-7. This is consistent with the approved workflow (theorem design is a separate later stage). Recorded for completeness; not a defect of this stage.
9. **Lean-checked proofs** — **MISSING by design**: no proofs exist yet; therefore vacuity, theorem-weakening, and proof-strength checks are not applicable at this stage and will be performed at the theorem/proof stages. Recorded for completeness; not a defect of this stage.

Additional inputs read: `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-approval-v1.json` (Gate B approved), `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md`, `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v1.md`, `runs/ptx-9.3-mov.b32-f910feea/run.json`, and `lean/Spec2Lean/Basic.lean` (import target).

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | `Destination.bitBucket` (Lean lines 137-140), `updateDestination` (240-244), eval example (335-338) | The bit-bucket destination is materialized as a constructor and its behavior modeled (no register write), although the approved semantics records its applicability to scalar `mov.b32` as an OPEN_QUESTION (SEM2-047/AMB-3, bundle GAP-6) and supports it only at general section 9.2 rule strength. The mapping annotates this honestly in comments, but the constructor makes the instruction domain broader than the source-resolved base core |
| F-2 | NOTE | `execMovB32` guard-false branch (Lean lines 271-278, comment 258-261) | The mapping decides that when the complete guard expression is false, source operands are NOT read, so a missing source register does not produce partial execution (`none`); it returns `guardFalse s`. Supported by the official do-nothing clause (MOV-035/036) and the `@!p div.f32` division-by-zero example (MOV-037), but the approved semantics wording is general ("does not execute and no state component changes") and does not spell out operand non-reading |
| F-3 | NOTE | entire candidate (no theorem statements) | The candidate contains no theorem statements and no proofs; PRF-1..PRF-7 are deferred to the theorem-design/proof stages. Vacuity, weakened-statement, and proof-strength checks cannot be performed at this stage. Consistent with the approved workflow |
| F-4 | NOTE | `MovB32Step` (Lean lines 293-299) vs `execMovB32` (271-278) | The relational form and the executable function are both present, but their correspondence is unproven and explicitly deferred (PRF-1 family). The relation omits the `none` partial case (it relates only complete executions), which is a mapping decision consistent with D-25 |
| F-5 | NOTE | Lean header (lines 11-21) | The header cites the Gate B record path and interpretation path/ID but not the approved semantics' recorded SHA-256 (`904e10e1...`). Traceability is by path + interpretation_id, which resolves correctly; adding the hash would strengthen the header |
| F-6 | NOTE | `import Spec2Lean.Basic` (line 61) | The only import resolves to a placeholder module defining `hello := "world"`; it contributes nothing to this file. Harmless and consistent with project conventions, but unused |

## 5. Traceability verification (semantic claims → Lean definitions)

Each Lean declaration was checked against the approved semantics; all cited claim IDs exist in `semantics-v2.json` and the mapping content matches the claim statements:

| Lean declaration (lines) | Cited claims (in file) | Verified against semantics-v2 |
|---|---|---|
| `b32Bits := 32` (71) | SEM2-016/018 | `.b32` Bits (untyped) 32-bit; 32-bit scalar register width — OK |
| `b32DomainSize := 2^b32Bits` (76) | D-11; SEM2-060 | fixed-width 32-bit bit-value domain — OK |
| `structure B32` (88) | SEM2-016/021/060; D-11 | 32-bit untyped domain `Fin 2^32`; no arithmetic ops — OK |
| `structure RegId` (102) | SEM2-018/049; D-12 | name-based register identity; not fully addressable — OK |
| `structure PredId` (113) | SEM2-027/069; D-13 | virtual `.pred` register; 1-bit domain encoding deferred (OQ-5) — OK |
| `inductive SourceOperand` (124) | SEM2-013/026 | register or immediate source only (bounded scope) — OK |
| `inductive Destination` (137) | SEM2-047; D-18; AMB-3 | register or bit bucket at candidate strength — OK (see F-1) |
| `inductive Guard` (149) | SEM2-009/027/031; D-19/D-21 | unguarded / `@p` / `@!p` — OK |
| `inductive MovTypeSpecifier` (161) | SEM2-007/022 | only `.b32`; no modifier position — OK |
| `structure MachineState` (174) | SEM2-058; D-5/D-14 | (value-reg file, pred-reg file) minimal state — OK |
| `structure MovB32Instruction` (183) | SEM2-010/059; D-1/D-16 | guard, then d, then a in order — OK |
| `evalSource` (197) | SEM2-026/030 | pre-instruction source read; imm → value — OK |
| `evalGuard` (209) | SEM2-009/027/031; D-19 | unguarded true; `@p` value; `@!p` negation; missing → `none` — OK |
| `copyValue v := v` (225) | SEM2-035/036 | explicit copy rule `d = a;` — OK |
| `updateDestination` (240) | SEM2-032/033/047 | writes only destination register; bit bucket → no write — OK |
| `inductive ExecOutcome` (251) | D-8; SEM2-043 | executed / guardFalse; no error constructor — OK |
| `execMovB32` (271) | SEM2-034/035/036/037/038/041/042/062 | guard eval first; false → unchanged state; true → read-copy-write; `none` = partial — OK |
| `inductive MovB32Step` (293) | D-25; SEM2-061 | relational form; guardFalse and executed constructors — OK |

All cited claim IDs (SEM2-001..076 subset used) resolve to existing claims in the approved interpretation. No citation refers to `add.u32`, `PTX-MOV-SEM1-*` (superseded), or any other unit's evidence. The epistemic note in the Lean header (lines 23-31) correctly states that guard-false is implemented as the approved DERIVED interpretation (SEM2-034/038) and must never be presented as a human assumption or imported from add.u32.

## 6. Semantic-drift and correctness checks

- **Operand order/roles:** `MovB32Instruction` fields are `type, guard, d, a`; destination precedes source, matching `mov.type d, a;` (MOV-003) and section 9.2 role conventions (MOV-018; SEM2-010). No swap found.
- **Bit width / signedness:** `B32` wraps `Fin 2^32` (32 bits, 2^32 values); no signed/unsigned interpretation is imposed, consistent with `.b32` "Bits (untyped)" (SEM2-016/021). No signed/unsigned confusion.
- **Modifiers:** no modifier field exists; the scalar mov syntax has no modifier position (SEM2-022). OK.
- **Guard/predication:** unguarded → `some true` (unconditional, SEM2-009); `@p` → predicate value; `@!p` → negation; missing predicate register → `none` (partial). Guard-false returns the *same* state object (`guardFalse s`, `MovB32Step.guardFalse s i s`), so no state component changes — matches SEM2-034/038 and PRF-4's frame statement.
- **State reads:** source operand read (SEM2-030) and guard predicate read (SEM2-031) are both present; no missing reads.
- **State writes:** only the destination value register is written (SEM2-032/033); no carry flag, status register, or condition-code component exists in the model, and the Lean comment (230-235) correctly attaches the GAP-3 negative-evidence caveat rather than asserting an affirmative NVIDIA enumeration. No extra state effects.
- **Aliasing:** `evalSource s i.a` is evaluated before `updateDestination s i.d (copyValue va)`, so `d == a` yields a self-copy; eval example confirms `r1` stays `5`. Matches SEM2-062.
- **Error/UB:** no error constructor; `none` is partial execution only (SEM2-041/042/043). The mapping does not invent traps or undefined behavior.
- **Determinism:** `execMovB32` is a pure total function returning `Option ExecOutcome`; `MovB32Step` has disjoint constructor premises (guard `some false` vs `some true`), so the relation is functional where defined — structurally consistent with the derived determinism claim SEM2-039 (formal proof deferred to PRF-1).
- **Version/target:** not modeled as execution behavior; the header defers version/target gating to validation obligations (VAL-5/VAL-6), matching the semantics' version_and_target section and SEM2-044/045/046.
- **Example helpers:** `mkB32` (mod 2^32), `mkState` (first-binding-wins), and the `ex*` identifiers are explicitly marked "not semantic definitions"; they add no behavior beyond the semantics. `#eval` outputs match the formalizer's claimed values and the semantics' expectations.
- **No hidden trust:** no `sorry`/`admit`/`axiom`/`unsafe`/`partial`/`opaque`; the only import is a placeholder. No new axioms introduced.

## 7. Source-verification notes

Specification-tool calls used in this critique: restricted context reads at anchors `control-flow-instructions-at` (line 21826), `data-movement-and-conversion-instructions-mov` (line 14999), `instructions` (line 8718), `predicated-execution` (line 7537), `fundamental-types` (line 3015), and a literal search for `Bits (untyped)` (1 match at line 3053, Table 8).

Verified results:

- Section 9.7.13.2 (anchor `control-flow-instructions-at`, lines 21826-21853): Description "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." (21838-21839); Semantics "If {!}p then instruction" (21841); Examples `@!p div.f32 ratio,x,y // avoid division by zero` and `@q bra L23;` (21848-21851). Matches fragments PTX-9.3-MOV-035/036/037 and supports the Lean guard-false and non-reading decisions (F-2).
- Section 9.7.9.3 (anchor `data-movement-and-conversion-instructions-mov`, lines 14999-15044): syntax `mov.type d, a;` with `.type = { .pred, .b16, .b32, .b64, ... }` (15008-15021); Description "Write register d with the value of a." (15025); Semantics first line `d = a;` (15039). Matches fragments PTX-9.3-MOV-001..006.
- Section 9.7 (anchor `instructions`, line 8718): "All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax." (8722-8723). Matches fragment PTX-9.3-MOV-016.
- Section 9.3 (anchor `predicated-execution`, line 7537): guard predicate syntax `@{!}p`, unconditional execution without a guard (7547-7550). Matches fragment PTX-9.3-MOV-021.
- Section 5.2.1 (anchor `fundamental-types`, line 3015): fundamental type specifies basic type and size; Table 8 at line 3025; "Bits (untyped)" row with `.b8, .b16, .b32, ...` at line 3053. Matches fragments PTX-9.3-MOV-023/024.
- No `sorry`/`admit`/`axiom`/`unsafe` tokens in the Lean candidate (grep verified; the single grep hit in `AddU32Proofs.lean` is a documentation comment, and the candidate's own matches are comments/strings).

## 8. Required revisions (consolidated)

No substantive revisions are required before Gate C. Optional refinements:

1. Decide and record (Gate C reviewer) whether to keep `Destination.bitBucket` in the mapping now or defer it until the scalar applicability question (SEM2-047/AMB-3, GAP-6) is resolved (F-1). The current annotation is honest; no code change is mandatory.
2. Optionally add the approved semantics SHA-256 (`904e10e1...`) to the Lean header for hash-level traceability (F-5).
3. Optionally note in the header that guard-false does not read source operands, citing MOV-037 (F-2) — currently only stated in the body comment at lines 258-261.

## 9. Residual open questions

- Will the Gate C reviewer accept the materialized bit-bucket destination constructor at general-rule strength (F-1, SEM2-047/AMB-3)?
- Will the Gate C reviewer accept the guard-false source-non-reading decision, which is source-supported (MOV-037) but not spelled out in the semantics wording (F-2)?
- Are PRF-1..PRF-7 (including the PRF-6 VAL-style reclassification disposition) confirmed at the theorem-design stage, as recorded in the approved semantics' `future_theorem_obligation_topics`?
- Will the theorem stage prove the correspondence between `MovB32Step` and `execMovB32` and the frame/guard/determinism properties (F-4)?

## 10. Gate C readiness assessment

Ready for presentation to Human Gate C. The Lean mapping is faithful to the Gate-B-approved semantics and the Gate-A-approved architecture: operand order, bit width, untyped value domain, guard semantics (including the source-resolved DERIVED guard-false no-op), explicit copy rule, read-before-write aliasing, destination-only write locality, partial-execution (no-error) representation, minimal state, and the relational execution form all match the approved claims with per-declaration traceability. Lean compilation succeeds with 0 errors/0 warnings and all executable examples evaluate as expected; compilation was verified but is not treated as evidence of source faithfulness — the claim-by-claim mapping and direct official-HTML re-verification are the basis of this assessment. No `sorry`/`admit`/`axiom`/`unsafe`/`partial`/`opaque` and no hidden trust via imports. Theorem statements and proofs do not exist yet, which is by design for this stage and will be assessed at the theorem-design stage. The MINOR/NOTE findings (F-1..F-6) do not block Gate C presentation. This assessment is not a Gate C approval; approval is a human decision.

## 11. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/mov-b32/lean/MovB32-v1.lean` or any other candidate. No Lean definitions were rewritten, no semantic claims were altered, no source evidence was fabricated, and no gate was approved. Nothing was promoted to `accepted/`.
