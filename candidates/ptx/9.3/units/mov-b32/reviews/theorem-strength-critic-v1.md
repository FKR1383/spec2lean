# Independent Theorem-Strength Critique — mov-b32 obligations-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/mov-b32/theorems/obligations-v1.json` (obligation_set_id `ptx-9.3-mov-b32-obligations-v1`, status `READY_FOR_STRENGTH_REVIEW`, 480 lines, SHA-256 `23611715...` per run history), produced at THEOREM_GENERATION attempt 1 (run history, 2026-08-07T12:42:04).
- This critique is an independent semantic-critic review of theorem strength and non-vacuity. It does not approve the theorem-strength gate and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines), via the restricted specification tools.
- Approved semantics consulted: `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json` (interpretation_id `ptx-9.3-mov-b32-semantics-v2`, 76 claims; approved at Human Gate B per `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-approval-v1.json`).
- Approved language architecture consulted: `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md` (approved at Human Gate A per `reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json`; proof-obligation families PRF-1..PRF-7, validation obligations VAL-1..VAL-6, relational design D-25).
- Lean mapping consulted: `candidates/ptx/9.3/units/mov-b32/lean/MovB32-v1.lean` (387 lines, SHA-256 `c1ddad160a64c52e9f0ec8781d11236ed23f9dfd4e45595d287db9d74c7b8876`), re-checked independently in this critique.
- Prior reviews consulted: `candidates/ptx/9.3/units/mov-b32/reviews/lean-mapping-critic-v1.md` (findings F-1..F-6) and `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md` (findings F-1..F-5).
- Run metadata consulted: `runs/ptx-9.3-mov.b32-f910feea/run.json` (unit `mov.b32`, stage THEOREM_STRENGTH_CRITIQUE attempt 1, revision 18; gates A, B, C approved; theorem-strength gate pending).

## 2. Overall verdict

**ADEQUATE — ready for Human Theorem-Strength approval presentation (no substantive revision required). The theorem-strength gate is NOT approved by this review.**

The obligation set proposes seven theorem obligations (PTX-MOV-THM-001..007) that, as stated, are non-vacuous, appropriately strong, correctly named, faithful to the Gate-B-approved semantics, and traceable to existing `PTX-MOV-SEM2-*` claims and to declarations that exist in the compiling Lean candidate. The set correctly avoids the vacuity traps that this stage exists to catch: it refuses to propose the trivial functional single-valuedness of `execMovB32`; it states determinism over the Prop-valued relation `MovB32Step` (non-vacuous per design D-25); it reclassifies PRF-6 as a VAL-style definitional obligation rather than a vacuous semantic theorem; and it defers out-of-model frame claims (carry/status components) instead of asserting them (risk R-1). Each theorem statement was independently re-checked in this critique against the actual Lean definitions: all are true of the model (no false statement found), all have satisfiable hypotheses (no vacuity), none is weaker than the semantic claim it traces to at the level required, and none is stronger than the model or the evidence supports without a retained caveat.

Lean verification performed in this critique: `lean_check_file candidates/ptx/9.3/units/mov-b32/lean/MovB32-v1.lean` — success, exit 0, 0 errors, 0 warnings (matches the recorded SHA-256 `c1ddad16...`). Source scan confirms no `sorry`, `admit`, `axiom`, or `unsafe` in the Lean candidate, and the obligation JSON contains theorem sketches only (no proofs, by design for this stage).

Findings are limited to two MINOR annotations (F-1: THM-005's whole-state conclusion is stronger than the minimal PRF-3 wording and must carry the AMB-3 caveat at the statement level; F-2: the obligation set's four-part THM-002 and the Lean sketches need exact namespace-qualified statement pinning before proof generation) and three NOTE-level observations (F-3: THM-001 determinism is meaningful only on the domain where steps exist — the statement's shape is correct; F-4: THM-007's conditional `hsources` hypothesis is correctly shaped; F-5: the correspondence parts of THM-002 have asymmetric substance — (c) is near-definitional, (d) is the substantive partiality bridge). None change the semantic content and none require revision before the theorem-strength gate.

## 3. Inputs reviewed

Required inputs for a theorem-strength critique:

1. **Bounded source bundle** — `candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v2.json` (38 fragments `PTX-9.3-MOV-001..038`): present; load-bearing fragments re-verified verbatim against the official HTML in this critique (Section 7).
2. **Exact evidence fragment IDs** — `PTX-9.3-MOV-001..038`: present; the obligations cite only these IDs.
3. **Semantic interpretation candidate** — `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json`: present, read in full, Gate-B-approved (76 claims).
4. **Approved language architecture** — `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md`: present; PRF-1..PRF-7, VAL-1..VAL-6, D-25 verified present.
5. **Lean definitions** — `candidates/ptx/9.3/units/mov-b32/lean/MovB32-v1.lean`: present, read in full, re-compiled (0 errors, 0 warnings).
6. **Traceability from semantic claims to Lean definitions** — present via per-declaration comments; verified (Section 5 of the obligations and re-checked here).
7. **Theorem obligations** — `PTX-MOV-THM-001..007` plus `PTX-MOV-VAL-001..006` and deferred properties `PTX-MOV-DEF-001..007`: present, read in full.
8. **Theorem statements** — **present as Lean sketches only** (this is the artifact under review; the sketches are the theorem statements being strength-reviewed).
9. **Lean-checked proofs** — **MISSING by design**: no proofs exist yet; this stage reviews theorem *statements* for strength and non-vacuity before proof generation. Recorded for completeness; not a defect of this stage.

Additional inputs read: `reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json`, `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-approval-v1.json`, `reviews/ptx-mov-b32/gate-c/ptx-mov-b32-c-approval-v1.json` (referenced from run.json and the obligations file), `candidates/ptx/9.3/units/mov-b32/reviews/lean-mapping-critic-v1.md`, and `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md`.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | PTX-MOV-THM-005 (`precise_statement_in_words`/`conclusion`) | The conclusion `s' = s` (whole-state equality) is stronger than the minimal semantic family PRF-3 wording ("execution changes no value register"). It is true in the approved model (`updateDestination` returns `s` unchanged for the bit-bucket and never touches `predRegs`), and the caveat is recorded in `intent`/`strength_risks`, but the strength annotation (AMB-3 / general section 9.2 rule, mov.b32-specific applicability open) should be carried at the statement level so the theorem is not misread as mov.b32-specific source evidence |
| F-2 | MINOR | obligation set theorem statements (all sketches) + PTX-MOV-THM-002 four-part structure | The Lean sketches use unqualified identifiers (`MovB32Step`, `MachineState`, `execMovB32`, …) that actually live under `Spec2Lean.PTX`; and THM-002 bundles four distinct theorems (`exec_sound_executed`, `exec_sound_guardFalse`, `step_complete`, `step_partial_complete`) under one obligation ID. The proof phase must qualify names/open the namespace and confirm each of the four is emitted as its own theorem with the exact `Exists`/`not (Exists …)` shapes shown |
| F-3 | NOTE | PTX-MOV-THM-001 | Relational determinism is meaningful (inhabited, non-vacuous) only on the domain where a step exists; for `evalGuard = none` neither constructor applies and no step exists. The statement "at most one resulting state" is exactly the right shape — it neither claims totality nor vacuous uniqueness — and the proof strategy's disjointness argument is sound |
| F-4 | NOTE | PTX-MOV-THM-007 (`hsources` hypothesis) | The conditional hypothesis `b = true -> Exists va, evalSource s i.a = some va` is correctly shaped: when `b = false` it is vacuously satisfied and the reverse direction still requires proving that no executed outcome exists. The obligation already flags that an unconditional source-resolution hypothesis would be an unapproved strengthening |
| F-5 | NOTE | PTX-MOV-THM-002 | The four correspondence parts have asymmetric substance: part (c) (`step_complete`) is near-definitional because the relation's two constructors mirror the function's two success branches, while part (d) (`step_partial_complete`) is the substantive bridge connecting the `none` partiality case to step-absence. The set is not weakened by this asymmetry, but the theorem-strength reviewer should not over-weight (c) when assessing the correspondence |

## 5. Per-obligation strength and non-vacuity analysis

Each obligation below was independently re-checked against the actual Lean declarations in `MovB32-v1.lean` (lines cited) and the Gate-B-approved semantics claims. "True of the model" means the statement, if formalized as written, is provable from the definitions (verified by case analysis on the constructors/matches, not by machine proof — no proofs exist yet); "non-vacuous" means the hypotheses are satisfiable and the conclusion is not an element of the hypotheses.

### PTX-MOV-THM-001 — `movB32Step_deterministic` (relational determinism, PRF-1)
- **Statement shape:** `MovB32Step s i s1 -> MovB32Step s i s2 -> s1 = s2`.
- **Non-vacuity:** The relation is inhabited (`evalGuard = some true` + `evalSource = some va` gives the `executed` constructor; `evalGuard = some false` gives `guardFalse`). The conclusion is not in the hypotheses. The statement is not a definitional triviality: it is a `Prop`-valued inductive relation, and equality of the post-states requires case analysis over two constructors with disjoint premises. Verified: this is a genuine theorem with a short proof (case on both steps; both-`guardFalse` by reflexivity; both-`executed` by injectivity of `some` on the deterministic `evalSource`; mixed cases by the disjointness of `some false` vs `some true` on `evalGuard`).
- **Strength:** Correctly refuses to state the trivial functional single-valuedness of `execMovB32` (compliance_notes item 3, determinism_note); states the substantive relational property required by D-25. Does not claim existence of a step (that is THM-002's completeness). No unapproved totality precondition. **Adequate.**
- **Traceability:** SEM2-039 (determinism, DERIVED, GAP-2), SEM2-061 (D-25 relational), SEM2-043 (two-case outcome) — all exist and support the statement.

### PTX-MOV-THM-002 — `execMovB32_MovB32Step_correspondence` (PRF-1 family; mapping-critic F-4)
- **Statement shape:** (a)/(b) soundness of executed/guardFalse outcomes; (c) completeness of steps; (d) `execMovB32 s i = none <-> not (Exists s', MovB32Step s i s')`.
- **Non-vacuity:** Witnesses exist for every part (guardFalse example, executed example, partial-execution example). Each direction requires unfolding both the function and the relation.
- **Strength:** Part (d) is the substantive partiality bridge (risk R-2): I verified both directions by cases on `evalGuard` (`none`/`some false`/`some true`) and `evalSource` — the only ways to have no step are exactly the two `none` returns. This makes the approved partial-execution convention precise rather than hiding it. Parts (a)/(b) are genuine soundness statements. Part (c) is near-definitional (see F-5) but not vacuous. No unapproved preconditions; the four constructors of `ExecOutcome` are used exactly. **Adequate.**
- **Traceability:** SEM2-061, 043, 034, 035, 037, 038, 041 — all exist and support the parts.

### PTX-MOV-THM-003 — `execMovB32_copy_fidelity` (copy rule, PRF-7)
- **Statement shape:** `evalGuard = some true -> i.d = Destination.reg r -> evalSource s i.a = some va -> Exists s', execMovB32 s i = some (ExecOutcome.executed s') /\ s'.valueRegs r = some va`.
- **Non-vacuity:** Satisfiable hypotheses (e.g., `mov.b32 r1, imm 7`; aliasing self-copy). The conclusion pins the written value to the pre-state read value; it is not an element of the hypotheses.
- **Strength:** This is exactly the copy rule `d = a;` (SEM2-035/036) plus the read-before-write content (SEM2-062), because `va` is defined from the pre-instruction state `s` and `copyValue` is the identity. The `Exists` form is sufficient for the copy-fidelity content (the explicit post-state is really THM-002's correspondence content); it is not weakened below the semantic claim. The obligation's strength risk correctly flags the `copyValue = identity` dependency. No bit-bucket or missing-register overreach (those are THM-005 / partiality R-2). **Adequate.**
- **Traceability:** SEM2-035, 036, 030, 032, 062, 068 — all exist.

### PTX-MOV-THM-004 — `movB32Step_destination_only_frame` (PRF-2)
- **Statement shape:** `MovB32Step s i s' -> i.d = Destination.reg r -> (forall r', r' != r -> s'.valueRegs r' = s.valueRegs r') /\ (forall p, s'.predRegs p = s.predRegs p)`.
- **Non-vacuity:** Satisfiable hypotheses (destination-update example). The frame content (all other value registers and all predicate registers preserved) is not in the hypotheses.
- **Strength:** Covers both components of the bounded model, and both constructors (guardFalse case is trivially the frame; executed case is the content). Correctly restricted to the bounded model: no claim about components outside the model (deferred property DEF-001; risk R-1 negative-evidence caveat retained). Does not assert the value written to `r` itself (that is THM-003). **Adequate.**
- **Traceability:** SEM2-032, 033, 058, 041, 042 — all exist.

### PTX-MOV-THM-005 — `movB32Step_bit_bucket_preserves_state` (PRF-3)
- **Statement shape:** `MovB32Step s i s' -> i.d = Destination.bitBucket -> s' = s`.
- **Non-vacuity:** Satisfiable hypotheses (a `bitBucket`-destination instruction with `evalGuard = some true` and `evalSource = some va` yields the `executed` constructor with post-state `s`; a guard-false step also satisfies `s' = s`).
- **Strength:** True of the model (`updateDestination s Destination.bitBucket v = s` by definition; `predRegs` never touched). The whole-state equality `s' = s` is stronger than the minimal PRF-3 semantic wording ("execution changes no value register") — valid in the model, but the AMB-3 / general-rule strength caveat must be carried at the statement level (see F-1). Not presented as mov.b32-specific explicit source behavior. **Adequate with F-1 annotation.**
- **Traceability:** SEM2-015 (general section 9.2 rule), 047 (AMB-3 open question), 043 — all exist.

### PTX-MOV-THM-006 — `execMovB32_guard_false_preserves_state` + `movB32Step_guard_false_frame` (PRF-4)
- **Statement shape:** (a) `evalGuard = some false -> execMovB32 s i = some (ExecOutcome.guardFalse s)`; (b) `MovB32Step s i s' -> evalGuard = some false -> s' = s`.
- **Non-vacuity:** Satisfiable hypotheses (any state with the referenced predicate defined to false). The conclusion pins the exact outcome constructor and the unchanged carried state.
- **Strength:** Strong and faithful. The guard-false behavior is correctly presented as DERIVED_INTERPRETATION (SEM2-034/038/076) from the official section 9.7.13.2 clause, never as an affirmative per-instruction SOURCE_FACT (strength risk retained). The source-non-reading property is a mapping decision supported by MOV-037 and flagged. Part (a) is a full state-preservation statement because `guardFalse` carries exactly the input state and is the only producer of that outcome in `execMovB32`. **Adequate.**
- **Traceability:** SEM2-034, 038, 072, 073, 076, 043 — all exist.

### PTX-MOV-THM-007 — `movB32_executes_iff_guard_true` (PRF-5)
- **Statement shape:** `evalGuard s i.guard = some b -> (b = true -> Exists va, evalSource s i.a = some va) -> (Exists s', execMovB32 s i = some (ExecOutcome.executed s')) <-> b = true`, plus five per-constructor `evalGuard` lemmas.
- **Non-vacuity:** Both directions are non-trivial. Forward: with `b = true` and `hsources`, the executed branch is reached. Reverse: with `b = false`, the function returns `guardFalse`, so no executed outcome exists — this requires proving that the executed outcome is impossible, not just reading it off. States satisfying the hypotheses exist for both values of `b` (`@p` with `p` true/false).
- **Strength:** Correct classification statement; the conditional `hsources` hypothesis is exactly the well-formed-domain restriction (F-4). The supporting lemmas pin the per-constructor guard evaluation and correctly distinguish `@p` from `@!p` (opposite execution conditions). Does not overclaim as PRF-1 determinism (strength risk retained). **Adequate.**
- **Traceability:** SEM2-009, 027, 031, 037, 073 — all exist.

### Validation obligations PTX-MOV-VAL-001..006 and PRF-6 disposition
- The VAL obligations are definitional/static checks (instruction representation, B32 domain membership, no-proof-bypass scan, compilation, operand order, minimal state). The PRF-6 reclassification to VAL-002 is consistent with the approved semantics' recorded disposition and with semantic-critic v1 F-3: under the typed register-file representation, a result-domain-membership theorem would be vacuous, so the representation invariant is the correct level. **Adequate.**
- Deferred properties PTX-MOV-DEF-001..007 correctly quarantine: out-of-model frame claims (DEF-001/R-1), mov.b32-specific bit-bucket demonstration (DEF-002/AMB-3), immediate range/encoding (DEF-003/AMB-4), version/target gating (DEF-004), out-of-domain behavior (DEF-005/R-2), error/UB claims (DEF-006/GAP-3), and predicate-encoding (DEF-007/OQ-5). None is silently dropped or weakened into the theorem set.

## 6. Coverage verification

The `required_area_coverage` table maps every semantic area to an obligation:
copy rule `d = a;` (THM-003), read-before-write aliasing (THM-003), destination-only update (THM-004), unrelated-value-register frame (THM-004), predicate preservation (THM-004), bit-bucket state preservation (THM-005), false-guard state preservation (THM-006), guard-behavior classification (THM-007), relational determinism (THM-001), function/relation correspondence (THM-002), result-domain membership (VAL-002). Every PRF family of the approved architecture/semantics is covered; no PRF family is missing or silently downgraded except PRF-6, which is explicitly reclassified as VAL-style with the disposition recorded in the approved semantics. No obligation in the set depends on a human-approved formalization assumption (semantics-v2 has zero ASSUMPTION claims; `human_assumption_dependencies` is empty for every obligation).

## 7. Source-verification notes

Specification-tool calls used in this critique: restricted context reads at anchors `data-movement-and-conversion-instructions-mov` (line 14999) and `control-flow-instructions-at` (line 21826).

Verified results:
- Section 9.7.9.3 (anchor `data-movement-and-conversion-instructions-mov`, lines 14999-15049): syntax `mov.type d, a;` (15008) with `.b32` in the type set (15018); Description "Write register d with the value of a." (15025); Semantics first line `d = a;` (15039). Matches fragments PTX-9.3-MOV-003/004/006 and the obligations' `source_or_assumption_basis` for THM-003.
- Section 9.7.13.2 (anchor `control-flow-instructions-at`, lines 21826-21851): Description "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." (21838-21839); Semantics "If {!}p then instruction" (21841). Matches fragments PTX-9.3-MOV-035/036 and the obligations' `source_or_assumption_basis` for THM-006/THM-007.
- Lean candidate `MovB32-v1.lean` re-checked: exit 0, 0 errors, 0 warnings; all declarations referenced by the obligations (`MovB32Step`, `MachineState`, `MovB32Instruction`, `ExecOutcome`, `evalGuard`, `evalSource`, `updateDestination`, `copyValue`, `Destination`, `Guard`, `PredId`, `RegId`, `B32`, `SourceOperand`, `valueRegs`, `predRegs`) exist with the exact shapes the theorem sketches assume. No `sorry`/`admit`/`axiom`/`unsafe` tokens.
- No vacuous, circular, or trivially functional determinism statements found; no theorem name overstates its statement; no conclusion is stronger than the model permits without a retained caveat.

## 8. Required revisions (consolidated)

No substantive revisions are required before the theorem-strength gate. Optional refinements:

1. Carry the AMB-3 / general-rule strength annotation at the statement level of THM-005 (F-1), e.g., in the theorem comment, so the whole-state conclusion is not misread as mov.b32-specific source evidence.
2. Before proof generation, pin the exact namespace-qualified statement shapes for all seven obligations and emit the four parts of THM-002 as four separate named theorems (F-2).
3. Keep the THM-007 `hsources` hypothesis conditional; do not make it unconditional during proof generation (F-4; already flagged in the obligation).

## 9. Residual open questions

- Will the theorem-strength reviewer accept the whole-state conclusion `s' = s` of THM-005 at general-rule strength, with the AMB-3 caveat retained (F-1)?
- Will the proof phase emit THM-002 as four separate theorems with the exact sketch shapes, qualified under `Spec2Lean.PTX` (F-2)?
- Is the PRF-6 VAL-style disposition (VAL-002) confirmed at the theorem-strength gate, as recorded in the approved semantics?

## 10. Theorem-strength readiness assessment

Ready for presentation to Human Theorem-Strength approval. The obligation set is non-vacuous and appropriately strong: relational determinism over the Prop-valued `MovB32Step` (not the trivial function single-valuedness), the substantive function/relation correspondence including the partiality bridge, exact copy fidelity with read-before-write, a full bounded-model frame, guard-false state preservation presented at DERIVED strength (never as a per-instruction SOURCE_FACT), and the guard-behavior classification with correctly shaped domain hypotheses. Every obligation traces to existing Gate-B-approved SEM2 claims and to declarations in the compiling, no-`sorry`/`admit`/`axiom`/`unsafe` Lean candidate. The two MINOR findings (F-1, F-2) are annotation/statement-pinning refinements for the proof phase, not strength defects; the three NOTES (F-3..F-5) document the strength boundaries that the proof phase must preserve. This assessment is not an approval of the theorem-strength gate; approval is a human decision.

## 11. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/mov-b32/theorems/obligations-v1.json` or any other candidate. No theorem statements were rewritten, no semantics were changed, no source evidence was fabricated, no proofs were written, and no gate was approved. Nothing was promoted to `accepted/`.
