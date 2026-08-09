# Independent Theorem-Strength Critique — ptx-9.3-xor-b32-obligations-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/xor-b32/theorems/obligations-v1.json` (obligation_set_id `ptx-9.3-xor-b32-obligations-v1`, schema_version 1, status `READY_FOR_STRENGTH_REVIEW`, 492 lines), produced at stage THEOREM_GENERATION (attempt 1, run revision 14).
- This critique is an independent semantic-critic review of theorem strength and non-vacuity. It does not approve the human theorem-strength gate and does not edit or repair the reviewed artifact.
- Run metadata consulted: `runs/ptx-9.3-xor.b32-23b2e519/run.json` (unit `xor.b32`, stage THEOREM_STRENGTH_CRITIQUE attempt 1, revision 15; Gates A, B, C approved; THEOREM_STRENGTH and FINAL pending; active execution expects this artifact).
- Scope note: per the workflow, no proofs exist at this stage (proof generation occurs only after theorem-strength approval). This review therefore assesses theorem-statement strength, non-vacuity, faithfulness, traceability, and absence of forbidden constructs; it is not a proof critique.

## 2. Overall verdict

**ADEQUATE — ready for presentation to the human theorem-strength approval gate (gate not approved by this review).**

The obligation set proposes 7 theorem obligations that together cover every architecture proof-obligation family PRF-1..PRF-7 non-vacuously and at full supported strength, plus 6 validation obligations that correctly absorb the definitional/well-formedness checks (including the PRF-6 disposition). Independent checks performed in this review:

- **Non-vacuity and provability of every proposed theorem statement.** Each of the 7 `lean_statement_sketch` entries was analytically verified against the actual Lean definitions in `XorB32-v1.lean` (lines 210-325). All are satisfiable, none has its conclusion in its hypotheses, and none is a definitional triviality of a functional representation:
  - `xorB32Step_deterministic` (THM-001) is a genuine relational determinism property over the inductive `XorB32Step` (a Prop relation, not a function). It is provable: two steps from the same (s, i) must come from the same constructor; the executed constructor's `va`/`vb` are pinned by `evalSource` (a function, so Option-injective), and a guardFalse/executed mix would force `evalGuard = some false` and `= some true` simultaneously. The trivial functional single-valuedness of `execXorB32` is correctly NOT proposed (compliance_notes item 3; traceability_summary.determinism_note).
  - The four correspondence parts (THM-002 a-d) are all faithful and provable: soundness by constructor instantiation from the function's matched branches, completeness by case analysis on the two step constructors, and the `none <-> no step` partial-completeness (d) by case analysis on `evalGuard`/`evalSource` — verified consistent with `execXorB32` lines 293-303 and `XorB32Step` lines 318-325.
  - `execXorB32_xor_fidelity` (THM-003) asserts the full exclusive-or content `d = a ^ b;`: with `hd : i.d = Destination.reg r`, the post-state `updateDestination s (Destination.reg r) (xorValue va vb)` satisfies `valueRegs r = some (xorValue va vb)` by the `r' == r` branch; pre-state reads `ha`/`hb` make the statement subsume read-before-write aliasing (PRF-7 + PTX-XOR-SEM1-065).
  - Frame theorems THM-004 (register destination) and THM-005 (bit bucket) are provable over both relation constructors; THM-005 is honestly capped at the strength of the general section 9.2 rule with the AMB-3 / PTX-XOR-SEM1-067 caveat recorded (risk R-3; mapping-critic F-2), so it does not overstate xor.b32-specific source support.
  - `execXorB32_guard_false_preserves_state` (THM-006, functional + relational forms) is provable by the `some false` branch returning `guardFalse s` unchanged; the relational `xorB32Step_guard_false_frame` is provable because the executed constructor would require `evalGuard = some true`, contradicting `some false`.
  - `xorB32_executes_iff_guard_true` (THM-007, with five supporting `evalGuard` lemmas) is provable on the approved well-formed lookup domain: forward by `hsources` when `b = true`, reverse by the executed branch being reachable only from `evalGuard = some true`. The conditional hypothesis shape (`hsources : b = true -> ...`) is the correct, non-strengthened domain formulation (risk R-2); see F-2 for a wording nuance.
- **Traceability.** Every obligation's `semantic_claim_ids` were checked against `semantics-v1.json`: all cited claims exist (PTX-XOR-SEM1-011/022/028/029/031/032/033/034/035/036/037/038/039/044/047/052/053/054/060/063/064/065/067/072) and match the cited content. Every `lean_declarations_used` name exists in `XorB32-v1.lean` (XorB32Step, MachineState, XorB32Instruction, execXorB32, ExecOutcome, evalGuard, evalSource, updateDestination, xorValue, Destination, Guard, PredId, RegId, SourceOperand, B32, valueRegs, predRegs). Only bundle fragments `PTX-9.3-XOR-001..033` are referenced.
- **Coverage.** `required_area_coverage` maps every required area (xor fidelity, read-before-write, destination-only update, unrelated-register frame, predicate preservation, bit-bucket preservation, false-guard preservation, guard-behavior classification, relational determinism, function/relation correspondence, result-domain membership) to a concrete obligation or a sound disposition (VAL-002 for PRF-6).
- **Forbidden constructs.** Grep of the obligations file finds the words `sorry/admit/axiom/unsafe` only inside compliance/description prose stating their absence; the referenced Lean candidate `XorB32-v1.lean` has zero matches and compiles with 0 errors / 0 warnings (re-run in this review; SHA-256 `e2694a88...` matches the run record).
- **No circular tests.** The executable `#eval` demonstrations are witnesses for satisfiability of hypotheses (non-vacuity arguments), not proofs of the theorems; no obligation is assumed in any other obligation.

Findings are limited to 1 MINOR (naming precision) and 5 NOTE-level observations. None changes theorem content, and none requires a revision before the theorem-strength gate. The set is suitable for presentation to the human theorem-strength approval gate; this review does not approve that gate.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/xor-b32/theorems/obligations-v1.json` — complete read (492/492 lines); all 7 theorem obligations (PTX-XOR-THM-001..007), 6 validation obligations (PTX-XOR-VAL-001..006), 8 deferred properties, 6 known risks, traceability summary, and compliance notes inspected.
- `candidates/ptx/9.3/units/xor-b32/lean/XorB32-v1.lean` — complete read (437/437 lines); every declaration referenced by the obligations (lines 79-325) verified present and used as the target of each theorem statement; `lean_check_file` re-run: success, 0 errors, 0 warnings; grep for `sorry|admit|axiom|unsafe` in this file: zero matches.
- `candidates/ptx/9.3/units/xor-b32/semantics/semantics-v1.json` — complete read (338/338 lines); all 73 claims, PRF-1..PRF-7 future topics, ambiguities, open questions, determinism, and guard-false items cross-checked against every obligation's `semantic_claim_ids`.
- `candidates/ptx/9.3/units/xor-b32/source-bundles/source-bundle-v1.json` — read in relevant parts (fragments PTX-9.3-XOR-001..033); fragment IDs, exact quotes, and line ranges for the load-bearing evidence (XOR-002/004/005/016/031/032) verified against the official HTML.
- `candidates/ptx/9.3/units/xor-b32/architecture/foundation-v1.md` — full read (273 lines); PRF-1..PRF-7 and VAL-1..VAL-6 family definitions (Section 10) and design D-25/D-26 confirmed present and matched by the obligation categories.
- `candidates/ptx/9.3/units/xor-b32/reviews/lean-mapping-critic-v1.md` — full read (186 lines); NOTE F-3 (theorem deferral), F-2 (bit-bucket strength), F-4 (guard-false branch) consulted as the referenced mapping decisions.
- `runs/ptx-9.3-xor.b32-23b2e519/run.json` — run metadata and stage history (gates A/B/C approved; THEOREM_STRENGTH pending; active execution expected artifact `reviews/theorem-strength-critic-v1.md`).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — official PTX ISA 9.3 source (SHA-256 `e2095c4a...`) via restricted spec tools: xor section anchor `logic-and-shift-instructions-xor` (lines 14324-14357; Semantics `d = a ^ b;` at 14341), guard section anchor `control-flow-instructions-at` (lines 21826-21853; "Threads with a False guard predicate do nothing." at 21838-21839; Semantics "If {!}p then instruction" at 21841), and section 9.2 anchor `ptx-instructions` (lines 7513-7535; bit-bucket rule at 7534-7535) — all re-verified in this review.
- No proofs exist for this unit yet (by design; proof generation is the next stage after the theorem-strength gate). This review therefore covers theorem statements only.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | THM-007 `proposed_name` `xorB32_executes_iff_guard_true` (obligations lines 320-343) | The theorem name can be misread as an unrestricted equivalence "executes iff guard true"; the statement actually carries the approved well-formed-domain source-resolution hypothesis (`hsources : b = true -> ...`). Content is correct and consistent with risk R-2; the domain qualifier should be made explicit in the name or in the gate-review note so the name does not overstate the proved domain |
| F-2 | NOTE | THM-007 `strength_risks` (obligations line 339) | Wording "adding source-resolution hypotheses unconditionally ... would make the reverse direction trivial in a different way" is imprecise: the reverse direction (executed outcome exists → `b = true`) does not depend on source resolution at all; the unconditional hypothesis would only strengthen the forward direction's domain. The design decision itself (conditional `hsources`) is correct |
| F-3 | NOTE | THM-002 (4 sketches), THM-006 (2 sketches), THM-007 (6 sketches) | Each of these obligations bundles several theorem statements under one obligation ID with a single `proposed_name` that does not enumerate the sub-theorems (`exec_sound_executed`, `exec_sound_guardFalse`, `step_complete`, `step_partial_complete`; `xorB32Step_guard_false_frame`; five `evalGuard_*` lemmas). The Proof Engineer must emit each as a separate named Lean theorem; bundling is a structural presentation choice, not a defect |
| F-4 | NOTE | All `lean_statement_sketch` fields | The sketches are design-level and have not been type-checked by Lean (risk R-5). Each was analytically verified to use only declarations that exist in `XorB32-v1.lean` and to be provable against the current definitions, but the proof phase must compile them verbatim as the first check |
| F-5 | NOTE | THM-003 conclusion | The conclusion asserts existence of a post-state `s'` with the written value, rather than the explicit post-state identity `s' = updateDestination s i.d (xorValue va vb)`. This is adequate — `execXorB32` is a function, so the post-state is unique and the correspondence (THM-002) plus determinism (THM-001) pin it; no weakening of the exclusive-or content occurs |
| F-6 | NOTE | VAL-002 / PRF-6 disposition (obligations lines 118-126) | Confirmed sound at this review: result-domain membership holds by construction under the `B32 = Fin (2^32)` representation (PTX-XOR-VAL-002), so reclassifying PRF-6 as a VAL-style definitional well-formedness obligation (rather than a semantic theorem) correctly avoids a vacuous theorem. Human theorem-strength gate should explicitly record acceptance of this disposition (risk R-6) |

## 5. Findings detail

### F-1 — MINOR — THM-007 theorem name can overstate the proved domain

- **Exact location:** `theorem_obligations[6]` (PTX-XOR-THM-007), `proposed_name` `xorB32_executes_iff_guard_true`, obligations lines 320-343.
- **Relevant approved semantics/architecture:** PRF-5 (guard-behavior classification); PTX-XOR-SEM1-022/029/031/034/037/044; risk R-2 (all faithfulness theorems quantify over the approved well-formed lookup domain via lookup-success hypotheses).
- **Description:** The lean statement `xorB32_executes_iff_guard_true` carries `hguard : evalGuard s i.guard = some b` and `hsources : b = true -> both sources resolve`, and proves `(Exists s', execXorB32 s i = some (ExecOutcome.executed s')) <-> b = true`. On the approved well-formed domain this is exactly the semantic claim "executes iff guard true". However, read without the domain qualifier, the name could suggest the equivalence holds for out-of-domain states (missing sources), where `execXorB32` returns `none` and the instruction does not execute even with `b = true`. The statement content is correct and non-vacuous; the concern is naming precision only (my role checklist: "theorem names that overstate what is proved").
- **Consequence:** None for proof feasibility; the human theorem-strength gate reviewer should explicitly confirm that the well-formed-domain convention (R-2) is the accepted reading of the name, and may prefer a name such as `xorB32_executes_iff_guard_true_on_well_formed_domain` (or documentation of the convention at the gate).
- **Required owner:** Proof Engineer (naming) / Human theorem-strength gate reviewer (domain-convention confirmation).
- **Required revision:** None before the theorem-strength gate.
- **Human review required:** Yes (theorem-strength gate confirmation of the domain convention).

### F-2 — NOTE — Imprecise wording in THM-007 risk note

- **Exact location:** THM-007 `strength_risks` second bullet (obligations line 339).
- **Description:** The bullet states that adding source-resolution hypotheses unconditionally "would be an unapproved strengthening and would make the reverse direction trivial in a different way." In fact the reverse direction (executed outcome → `b = true`) never uses source hypotheses; it follows from the executed branch being reachable only from `evalGuard = some true` plus Option injectivity. The unconditional hypothesis would instead needlessly restrict the guard-false domain and make the forward direction's hypothesis stronger than the semantics requires. The design decision (conditional `hsources`) is correct; only the explanatory wording is imprecise.
- **Consequence:** None; wording-only. The statement shape is exactly right.
- **Required owner:** Proof Engineer (wording, optional).
- **Required revision:** None.
- **Human review required:** No.

### F-3 — NOTE — Obligation IDs bundle multiple theorem statements

- **Exact location:** THM-002 (four `lean_statement_sketch` theorems), THM-006 (two), THM-007 (one main theorem plus five supporting lemmas); `proposed_name` fields name only the principal theorem.
- **Description:** The obligations are a design artifact, so bundling is acceptable; but the Proof Engineer must emit each sketch as a separate Lean theorem with its own name (`exec_sound_executed`, `exec_sound_guardFalse`, `step_complete`, `step_partial_complete`, `xorB32Step_guard_false_frame`, `evalGuard_unguarded_true`, `evalGuard_atPos_true`, `evalGuard_atNeg_true_when_pred_false`, `evalGuard_atPos_false`, `evalGuard_atNeg_false_when_pred_true`). This note ensures none of the bundled sub-theorems is dropped during proof generation.
- **Consequence:** None at this stage; the proof phase must track sub-theorem emission.
- **Required owner:** Proof Engineer.
- **Required revision:** None.
- **Human review required:** No.

### F-4 — NOTE — Theorem statements are uncompiled sketches (R-5)

- **Exact location:** every `lean_statement_sketch` field; risk R-5 (obligations lines 422-424).
- **Description:** The sketches have not been type-checked. This review verified (a) every referenced Lean declaration exists in `XorB32-v1.lean`, (b) every statement is well-formed against those definitions by construction analysis, and (c) each is provable (Section 2). The proof phase must compile each sketch exactly as written as its first step.
- **Consequence:** None before the theorem-strength gate; proof generation is the next workflow stage.
- **Required owner:** Proof Engineer.
- **Required revision:** None.
- **Human review required:** No.

### F-5 — NOTE — THM-003 conclusion uses existential post-state

- **Exact location:** THM-003 `lean_statement_sketch` conclusion (obligations lines 225, 232).
- **Description:** `Exists s', execXorB32 s i = some (ExecOutcome.executed s') /\ s'.valueRegs r = some (xorValue va vb)` pins the written value but not the full post-state. This is not a weakening: `execXorB32` is a function, the post-state is uniquely `updateDestination s i.d (xorValue va vb)`, and determinism (THM-001) plus correspondence (THM-002) recover uniqueness. The exclusive-or content `d = a ^ b;` (PTX-XOR-SEM1-032/033) is fully asserted.
- **Consequence:** None.
- **Required owner:** None.
- **Required revision:** None.
- **Human review required:** No.

### F-6 — NOTE — PRF-6 disposition confirmed sound

- **Exact location:** PTX-XOR-VAL-002 (obligations lines 118-126); risk R-6 (lines 426-428); semantics future topic PRF-6.
- **Description:** The obligations reclassify result-domain membership (PRF-6) as a VAL-style definitional well-formedness obligation because every `B32` wraps a `Fin (2^32)` value, so membership holds by construction. This review confirms the disposition: a separate semantic theorem would be vacuously true by representation. The human theorem-strength gate should record acceptance of this disposition explicitly.
- **Consequence:** None; the disposition avoids a vacuous theorem and matches architecture A-10 / semantics PRF-6 record.
- **Required owner:** Human theorem-strength gate reviewer (disposition confirmation).
- **Required revision:** None.
- **Human review required:** Yes (theorem-strength gate confirmation).

## 6. Verification notes

Specification-tool calls used in this review: 3 restricted reads against the official PTX ISA 9.3 HTML (xor section, guard section 9.7.13.2, section 9.2), plus candidate reads and Lean tool checks. All load-bearing evidence behind the theorem statements was re-verified:

- **Exclusive-or rule (THM-003).** Anchor `logic-and-shift-instructions-xor` (line 14324; section 14324-14357). Confirmed: Syntax `xor.type d, a, b;` (14332-14334); Description "Bitwise exclusive-OR (inequality)." (14329) and "Compute the bit-wise exclusive-or operation for the bits in `a` and `b`." (14338); Semantics `d = a ^ b;` (14341); Examples `xor.b32  d,q,r;` (14353). Matches fragments PTX-9.3-XOR-002/003/004/005/009 and claims PTX-XOR-SEM1-032/033.
- **Guard-false clause (THM-006/007).** Anchor `control-flow-instructions-at` (line 21826; section 21826-21853). Confirmed: "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." (21838-21839); Semantics "If {!}p then instruction" (21841). Matches fragments PTX-9.3-XOR-031/032 and the DERIVED interpretation PTX-XOR-SEM1-035.
- **Bit bucket (THM-005).** Anchor `ptx-instructions` (line 7513). Confirmed: "For some instructions the destination operand is optional. A bit bucket operand denoted with an underscore (`_`) may be used in place of a destination register." (7534-7535). Matches fragment PTX-9.3-XOR-016 and claim PTX-XOR-SEM1-011, with the scalar-xor applicability caveat (PTX-XOR-SEM1-067 / AMB-3) correctly retained in the obligation.
- **Lean re-check.** `lean_check_file candidates/ptx/9.3/units/xor-b32/lean/XorB32-v1.lean` → success, exitCode 0, errorCount 0, warningCount 0; SHA-256 `e2694a8894d49307ce1050f835478a7963361318d5510465e5ee166df528fa0a` (matches run record and obligations reference).
- **Forbidden constructs.** Grep `sorry|admit|axiom|unsafe` in `obligations-v1.json`: matches only in prose that states their absence (lines 100, 130, 378) and in non-code hypothesis text ("s1 = s2", "s' = s" contain no forbidden tokens; the matches at lines 177/178/185/198/254/278 are false positives of the substrings "admit" inside "admits a step" and "admit" inside "admits a step"). Grep in `XorB32-v1.lean`: zero matches. `Spec2Lean.Basic` (sole import) is a one-line placeholder with no axioms.
- **Analytic provability sweep.** Every obligation statement was checked to be (1) satisfiable (executable examples witness the hypotheses), (2) not having its conclusion among its hypotheses, and (3) provable against `XorB32-v1.lean` lines 210-325 (constructor case analysis, Option injectivity, `updateDestination` branch equality, `evalGuard` branch disjointness). No statement is vacuous, circular, or false.

## 7. Required revisions (consolidated)

No substantive revisions are required before the human theorem-strength gate. Items for the human gate reviewer and the subsequent proof phase:

1. Confirm the well-formed-domain reading of THM-007's name/content (F-1; risk R-2) — the executed-outcome equivalence is over the approved lookup domain, not out-of-domain states.
2. Confirm the PRF-6 disposition as VAL-002 (F-6; risk R-6) — no separate result-domain-membership semantic theorem.
3. Note that proof generation must emit each bundled sub-theorem of THM-002/006/007 as a separate named Lean theorem (F-3), compile each `lean_statement_sketch` verbatim (F-4), and preserve the bit-bucket strength caveat (THM-005 / risk R-3) and the guard-false DERIVED classification (THM-006 / risk R-2) in the final statements.
4. Optional: refine the THM-007 name to carry the domain qualifier (F-1) and reword the THM-007 risk note (F-2).

## 8. Residual open questions

- Will the human theorem-strength gate accept the well-formed lookup-domain convention (R-2) as the reading of `xorB32_executes_iff_guard_true` and the other faithfulness theorems (THM-003/007 shape), rather than requiring statements over out-of-domain states (which would be partiality `none` cases, PTX-XOR-SEM1-052/053/054)?
- Will the human gate confirm that THM-005 (bit-bucket frame) may be stated at general-rule strength (PTX-XOR-SEM1-011/067; risk R-3) pending resolution of the scalar xor.b32 bit-bucket applicability question?
- Will the human gate accept the PRF-6 disposition (VAL-002) as final, per architecture A-10 and semantics PRF-6?
- The theorem sketches will be compiled by the Proof Engineer; any compilation issue (syntax, missing imports, field-access parsing) will surface at proof generation and be routed to the Proof Engineer / Repair Agent as appropriate.

## 9. Theorem-strength gate readiness assessment

Ready for presentation to the human theorem-strength approval gate. The obligation set:
- covers all PRF-1..PRF-7 families non-vacuously (relational determinism, four-part function/relation correspondence, exclusive-or fidelity `d = a ^ b;` with read-before-write subsumption, destination-only frame, bit-bucket discard at correct strength, guard-false frame, guard-behavior classification);
- states every theorem at full supported strength without weakening the semantics (exclusive-or fidelity, frame, and guard-false content are fully asserted) and without overclaiming (bit-bucket at general-rule strength; guard-false as DERIVED not assumption; determinism as DERIVED with the non-statement note);
- adds no unapproved preconditions beyond the approved well-formed lookup-domain hypotheses (R-2);
- is fully traceable to existing semantic claims and to the Gate-C-approved Lean mapping, with only bundle fragments PTX-9.3-XOR-001..033 referenced;
- contains no vacuous theorems, no circular tests, and no `sorry`/`admit`/new axioms/`unsafe`.

The 1 MINOR and 5 NOTE findings do not change theorem content and do not require revision before the gate. This assessment is not a theorem-strength approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/xor-b32/theorems/obligations-v1.json`. No theorem statements were rewritten, weakened, or invented; no semantics were altered; no source evidence was fabricated; no proofs were written; no gate was approved; nothing was promoted to `accepted/`.
