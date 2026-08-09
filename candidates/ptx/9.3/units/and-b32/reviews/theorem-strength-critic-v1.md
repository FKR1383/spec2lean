# Independent Theorem-Strength Critique — and-b32 obligations-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/and-b32/theorems/obligations-v1.json` (obligation_set_id `ptx-9.3-and-b32-obligations-v1`, status `READY_FOR_STRENGTH_REVIEW`, 495 lines), produced by the THEOREM_GENERATION stage of run `ptx-9.3-and.b32-d33dfec2`.
- This critique is an independent semantic-critic review of theorem strength and non-vacuity for the proposed obligation set. It does not approve the human theorem-strength gate and does not edit or repair the reviewed artifact.
- Lean mapping reviewed against: `candidates/ptx/9.3/units/and-b32/lean/AndB32-v1.lean` (namespace `Spec2Lean.PTX.AndB32`, SHA-256 `bcbe497526596b5da9d96417ec565118c49d2d1374f01ab8e531b2159bc24465`), Gate-C-approved (record `reviews/ptx-and-b32/gate-c/ptx-and-b32-c-approval-v1.json`, decision approved, submittedAtUtc 2026-08-09T18:54:05.210Z).
- Semantic interpretation reviewed against: `candidates/ptx/9.3/units/and-b32/semantics/semantics-v2.json` (interpretation_id `ptx-9.3-and-b32-semantics-v2`, SHA-256 `45e0fe93f02a3261976962026eb7b5b2e1a5343c10d4a388f500f6f30a24ca0e`; 74 claims: 23 SOURCE_FACT, 32 DERIVED_INTERPRETATION, 7 DESIGN_DEPENDENCY, 0 ASSUMPTION, 12 OPEN_QUESTION), Gate-B-approved.
- Architecture reference: `candidates/ptx/9.3/units/and-b32/architecture/foundation-v1.md` (SHA-256 `9798324a87bbb883a64f879e96d63e3f5cd9253c1b8b63547812c36254918187`), Gate-A-approved; proof-obligation families PRF-1..PRF-7 and validation obligations VAL-1..VAL-6 defined in architecture Section 10; design D-25 (execution relation, not merely a function) and D-26 (validation vs. theorem obligations).
- Source bundle: `candidates/ptx/9.3/units/and-b32/source-bundles/source-bundle-v2.json` (SHA-256 `57e86be0f823fa70e7559ca21cba30bf7f4b434a87c33cb39b134ce13f27ea53`).
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`).
- Prior critiques consulted as context: `candidates/ptx/9.3/units/and-b32/reviews/lean-mapping-critic-v1.md` (verdict SUITABLE for Gate C; F-1..F-6 NOTE), `candidates/ptx/9.3/units/and-b32/reviews/semantics-critic-v1.md` (verdict READY FOR GATE B), `candidates/ptx/9.3/units/and-b32/reviews/architecture-critic-v1.md`.
- Run metadata: `runs/ptx-9.3-and.b32-d33dfec2/run.json` (stage THEOREM_STRENGTH_CRITIQUE; revision 19; Gate THEOREM_STRENGTH pending; expected artifact `candidates/ptx/9.3/units/and-b32/reviews/theorem-strength-critic-v1.md`).

## 2. Overall verdict

**READY FOR PRESENTATION TO HUMAN THEOREM-STRENGTH APPROVAL (no blockers; no major defects; the obligation set is adequately strong, non-vacuous, and faithful to the approved semantics and Lean mapping; findings are NOTE-level transparency/decision items).**

The proposed obligation set is disciplined and faithful:

- **7 theorem obligations (PTX-AND-THM-001..007)** cover exactly the approved proof-obligation families PRF-1..PRF-7, with unit-specific Lean names under `Spec2Lean.PTX.AndB32`, and 6 validation obligations (PTX-AND-VAL-001..006) plus 8 deferred properties (PTX-AND-DEF-001..008) recording the open-question dependencies honestly.
- **Non-vacuity is genuine**: determinism (THM-001) is stated over the relational inductive `AndB32Step` (a Prop relation, not a function), so it is not a definitional triviality; the trivial single-valuedness of the total function `execAndB32` is explicitly NOT proposed (compliance_notes item 3; traceability_summary.determinism_note). Every other obligation's hypotheses are satisfiable (demonstrated by the 17 executable examples), and no conclusion is an element of its hypotheses.
- **Strength is adequate**: the central and-fidelity obligation (THM-003) pins the written value to `andValue va vb` of the pre-instruction source reads, covering both register-source-b and immediate-source-b uniformly through `evalSourceB`, and subsumes the read-before-write aliasing behavior (PTX-AND-SEM2-060). The function/relation correspondence (THM-002) provides the substantive four-part soundness/completeness/partiality bridge the Lean file itself deferred (AndB32-v1.lean lines 335-347). Frame (THM-004/005), guard-false (THM-006), and guard-behavior (THM-007) obligations are all meaningfully strong.
- **Faithfulness**: every obligation traces to real semantic claims (all `semantic_claim_ids` resolve in semantics-v2.json) and to real Lean declarations (all `lean_declarations_used` exist in AndB32-v1.lean). No phantom references, no invented semantics, no unapproved preconditions (the only conditional hypothesis, THM-007 `hsources`, is the approved well-formed-lookup-domain condition required by the partiality convention, not a new semantic assumption).
- **No forbidden constructs**: the obligations artifact contains no `sorry`, `admit`, new axioms, `unsafe`, or placeholder proofs; the Lean candidate was independently re-verified clean (0 errors, 0 warnings) at this stage.

The findings below are all NOTE-level transparency/decision items for the human theorem-strength gate. None requires a change before the set is presented for human approval; the human gate should explicitly confirm three decisions (PRF-6 VAL-style disposition; THM-005 bit-bucket candidate strength; THM-007 domain-conditioned naming/statement).

## 3. Inputs reviewed and verification performed

- `candidates/ptx/9.3/units/and-b32/theorems/obligations-v1.json` — complete read (495/495 lines); all 7 theorem obligations, 6 validation obligations, 8 deferred properties, 6 known risks, and the traceability summary reviewed.
- `candidates/ptx/9.3/units/and-b32/lean/AndB32-v1.lean` — complete read (505/505 lines); every declaration referenced by the obligations located and checked.
- Independent Lean verification at this stage:
  - `lean_check_file` on AndB32-v1.lean: success, exitCode 0, errorCount 0, warningCount 0.
  - `lean_run_eval` on AndB32-v1.lean: all 17 outputs match the documented expected values (0, 4294967295, 0, 1, 16711680, some 2147483648, some 16711680, some true, some true, some 100, some 1, some 5, some 1, some 1, some 1, some 5, "partial-none").
  - grep for `sorry|admit|axiom|unsafe` under the and-b32 candidate tree: matches occur only in prose documents stating that these are absent (obligations-v1.json compliance text, lean-mapping-critic-v1.md); no match inside `AndB32-v1.lean`.
- `candidates/ptx/9.3/units/and-b32/semantics/semantics-v2.json` — complete read; all claim IDs cited by the obligations (PTX-AND-SEM2-008/022/029/030/032/033/034/035/036/037/038/043/048/049/050/054/056/057/058/060/061/062/063/068/071/074) verified to exist with the expected classifications.
- `candidates/ptx/9.3/units/and-b32/architecture/foundation-v1.md` — complete read; PRF-1..PRF-7 and VAL-1..VAL-6 families, D-25 (relational representation), D-26 (validation vs. theorem), and A-10 (PRF-6 vacuity risk) cross-checked.
- `candidates/ptx/9.3/units/and-b32/source-bundles/source-bundle-v2.json` — evidence fragment IDs cross-checked.
- `runs/ptx-9.3-and.b32-d33dfec2/run.json` — complete read; stage, gates, history, and expected artifact path checked.
- Gate records: `reviews/ptx-and-b32/gate-a/ptx-and-b32-a-approval-v1.json`, `reviews/ptx-and-b32/gate-b/ptx-and-b32-b-approval-v1.json`, `reviews/ptx-and-b32/gate-c/ptx-and-b32-c-approval-v1.json` — confirmed to exist with decision approved.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via the restricted specification tool:
  - anchor `logic-and-shift-instructions-and` (line 14256): syntax `and.type d, a, b;` (14264), `.type = { .pred, .b16, .b32, .b64 };` (14266), description (14270), Semantics `d = a &amp; b;` (14273), Notes (14277-14278), PTX ISA Note (14280), Target ISA Note (14282), examples (14285-14286) — all verbatim.
  - anchor `control-flow-instructions-at` (line 21826): Description "Threads with a False guard predicate do nothing." (21838-21839), Semantics "If {!}p then instruction" (21841) — the source-resolved guard-false basis (PTX-AND-SEM2-063/071/074) verified.
  - anchors `predicated-execution` (7537), `fundamental-types` (3015), `register-state-space` (2613), `variables` (3741), `restricted-use-of-sub-word-sizes` (3070), `format-and-semantics-of-instruction-descriptions` (7505) — verified as previously recorded.

## 4. Obligation-by-obligation strength and non-vacuity verification

The critic independently re-derived each theorem statement against the actual Lean definitions and checked that the statement is true of the model, adequately strong, and non-vacuous.

### PTX-AND-THM-001 `andB32Step_deterministic` (PRF-1)
- Statement: `AndB32Step s i s1 -> AndB32Step s i s2 -> s1 = s2`, over the inductive Prop relation.
- Truth check: case analysis on the two constructors. Both guardFalse: s1 = s2 = s. Both executed: injectivity of `some` forces va1 = va2 and vb1 = vb2, hence equal post-states. Mixed: `some false` vs `some true` on the same `evalGuard` term, contradiction. True.
- Non-vacuity: hypotheses satisfiable (executed example and guard-false example); conclusion is not an element of the hypotheses; excludes a hypothetical relation admitting two distinct results. Meaningful relational determinism, not functional triviality.
- Strength: correct scope (uniqueness when a step exists; existence is THM-002). No totality precondition added. ✓

### PTX-AND-THM-002 `execAndB32_AndB32Step_correspondence` (PRF-1 family; Lean file deferred item)
- Parts (a)-(d): soundness for executed and guardFalse outcomes, completeness of every step by a function outcome, and the partiality equivalence `none <-> no step`.
- Truth check: (a) executed outcome arises only from the `some true` + both-sources-resolve branch, which is exactly the `executed` constructor; (b) guardFalse outcome arises only from the `some false` branch, exactly the `guardFalse` constructor; (c) each constructor's premises force the corresponding function outcome (verified both directions); (d) `execAndB32 = none` iff evalGuard = none or a source is none, which is exactly the absence of both constructors' premises. True.
- Non-vacuity: witnesses exist for every part among the executable examples; conclusions not in hypotheses.
- Strength: the four-part correspondence is the substantive bridge the Lean file deferred; part (d) makes the partiality convention precise without asserting totality. ✓

### PTX-AND-THM-003 `execAndB32_and_fidelity` (PRF-7)
- Statement: guard true + register destination r + both sources resolve (via `evalSourceA`/`evalSourceB`) -> `Exists s', execAndB32 s i = some (ExecOutcome.executed s') /\ s'.valueRegs r = some (andValue va vb)`.
- Truth check: with hguard/ha/hb the function returns `some (ExecOutcome.executed (updateDestination s i.d (andValue va vb)))`; with hd the destination update sets `valueRegs r = some (andValue va vb)`. True.
- Non-vacuity: hypotheses satisfiable (register-source, immediate-source-b, aliasing, self-aliasing examples); the conclusion pins the written value to the pre-state bitwise-and and distinguishes and semantics from copy/truncation/read-after-write. Not an element of the hypotheses.
- Strength: covers both `SourceB.reg` and `SourceB.imm` uniformly through `evalSourceB`; preserves read-before-write by fixing va/vb from the pre-instruction state; does not assert position-a immediates (open question PTX-AND-SEM2-061). Adequately strong. ✓

### PTX-AND-THM-004 `andB32Step_destination_only_frame` (PRF-2)
- Statement: `AndB32Step s i s'` + register destination r -> all other value registers and all predicate registers unchanged.
- Truth check: guardFalse gives s' = s; executed gives `updateDestination` which only rewrites `valueRegs r`. True.
- Non-vacuity: satisfiable (destination-update example with r2 and predicates untouched); frame content is not in the hypotheses.
- Strength: correctly limited to the bounded model with the R-1 negative-evidence caveat retained; does not overclaim about components outside the model. ✓

### PTX-AND-THM-005 `andB32Step_bit_bucket_preserves_state` (PRF-3)
- Statement: `AndB32Step s i s'` + `i.d = Destination.bitBucket` -> s' = s.
- Truth check: guardFalse gives s' = s; executed with bitBucket gives `updateDestination s Destination.bitBucket v = s`. True.
- Non-vacuity: satisfiable (bit-bucket example keeps r1 at 1; a guard-false bit-bucket step also satisfies s' = s).
- Strength: retained at candidate strength (AMB-3 / PTX-AND-SEM2-062), with the caveat that it must not be presented as and.b32-specific explicit NVIDIA behavior. See F-3: the human gate should explicitly decide keep-as-proposed vs. defer until OQ-2 is resolved.

### PTX-AND-THM-006 `execAndB32_guard_false_preserves_state` + `andB32Step_guard_false_frame` (PRF-4)
- Statement: (a) `evalGuard = some false` -> `execAndB32 s i = some (ExecOutcome.guardFalse s)`; (b) relational `s' = s` under a guard-false step.
- Truth check: (a) the `some false` branch returns exactly `some (ExecOutcome.guardFalse s)`; (b) the `guardFalse` constructor carries s' = s and the `executed` constructor requires `some true`, contradicting the hypothesis. True.
- Non-vacuity: satisfiable (@p with p = false keeps r1 at 5).
- Strength: full state-preservation because `guardFalse` carries the whole MachineState; correctly framed as DERIVED_INTERPRETATION (PTX-AND-SEM2-063, source-resolved via CTX-08), never as an affirmative per-instruction SOURCE_FACT. ✓

### PTX-AND-THM-007 `andB32_executes_iff_guard_true` + supporting evalGuard lemmas (PRF-5)
- Statement: `evalGuard = some b` + (b = true -> both sources resolve) -> `(Exists s', execAndB32 = some (ExecOutcome.executed s')) <-> b = true`; plus five per-constructor evalGuard lemmas.
- Truth check: forward — an executed outcome can only arise from the `some true` branch, so b = true; reverse — b = true with hsources gives `some true` and both sources, so the executed branch is reached. The `hsources` hypothesis is essential: without it, b = true with a missing source would return none and the iff would fail; the conditional shape is exactly the well-formed lookup domain of the partiality convention. Supporting lemmas unfold `evalGuard` directly. All true.
- Non-vacuity: both directions are substantive (b = true with sources, b = false); the biconditional is false if the outcome classification were wrong.
- Strength: uniform coverage of no-guard/@p/@!p through `evalGuard`; complements THM-006 with the reverse direction (no execution under a false complete guard). See F-2 on naming precision.

## 5. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | NOTE | obligations-v1.json THM-003, conclusion (lines 226, 233) | The fidelity conclusion uses `Exists s'` rather than pinning s' = updateDestination s i.d (andValue va vb). The value-write content is preserved (s'.valueRegs r = some (andValue va vb)), so this is not a weakening of the fidelity claim; the exact post-state is recoverable via THM-002/determinism. NOTE for proof-stage clarity |
| F-2 | NOTE | obligations-v1.json THM-007, proposed_name (line 323) and statement (lines 327, 333) | The proposed name `andB32_executes_iff_guard_true` is accurate to the semantic claim (PRF-5) but the formal statement is conditional on the well-formed-domain source-resolution hypothesis `hsources` (b = true -> sources resolve), required by the partiality convention. The intent/precise statement document this; the human gate should accept the domain-conditioned statement (and may prefer a name making the domain explicit, e.g., "on the well-formed lookup domain") |
| F-3 | NOTE | obligations-v1.json THM-005 (lines 273-295); deferred property PTX-AND-DEF-002 | The bit-bucket theorem is proposed at candidate strength while scalar and.b32-specific bit-bucket applicability remains OPEN_QUESTION (PTX-AND-SEM2-062/AMB-3). The caveat is retained and the alternative (removal/weakening pending OQ-2 resolution) is documented. The human theorem-strength gate should explicitly decide keep-as-proposed vs. defer THM-005 |
| F-4 | NOTE | obligations-v1.json VAL-002 (lines 119-127); risk R-6 (lines 428-430) | PRF-6 (result-domain membership) is disposed as a VAL-style definitional well-formedness obligation rather than a semantic proof obligation, following architecture A-10 and the mov.b32 lesson. The disposition is honest and correctly documented; the human theorem-strength gate should explicitly confirm it |
| F-5 | NOTE | obligations-v1.json THM-002 part (c) (lines 200-201, 217) | `step_complete` is stated as an existence formulation (`Exists o, ...`). It is adequate and provable (the proof must exhibit the specific outcome matching the step constructor), but a direct equality formulation (o = the specific constructor applied to s') would be stronger and equally provable. No change required |
| F-6 | NOTE | obligations-v1.json compliance_notes / traceability_summary (lines 99-106, 432-494) | The set explicitly records that no vacuous, circular, or trivially functional determinism claims are proposed, and that the trivial single-valuedness of execAndB32 is not proposed. The critic independently confirms these statements are accurate |

## 6. Findings detail

### F-1 — NOTE — Fidelity conclusion stated with `Exists s'`

- **Exact location:** obligations-v1.json, THM-003, `lean_statement_sketch` (line 226) and `conclusion` (line 233).
- **Relevant Lean definitions:** `execAndB32` (AndB32-v1.lean lines 323-333), `updateDestination` (lines 291-295), `andValue` (lines 275-278).
- **Description:** The conclusion is `Exists s' : MachineState, execAndB32 s i = some (ExecOutcome.executed s') /\ s'.valueRegs r = some (andValue va vb)`. An alternative direct form would be `execAndB32 s i = some (ExecOutcome.executed (updateDestination s i.d (andValue va vb)))` with `s'.valueRegs r = ...` derived. The `Exists` form retains the full value-write content and is the standard way to state a post-state property without requiring the proof to expose the exact record update in the theorem statement; the exact state is deterministically recoverable (THM-001) and correspondable (THM-002). Not a weakening of the semantic fidelity claim.
- **Consequence:** None for strength or faithfulness. Proof-stage clarity note only.
- **Required owner:** Proof Engineer (informational).
- **Required revision:** None.
- **Human review required:** No.

### F-2 — NOTE — THM-007 name vs. domain-conditioned statement

- **Exact location:** obligations-v1.json, THM-007, `proposed_name` `andB32_executes_iff_guard_true` (line 323); `lean_statement_sketch` (line 327) with hypothesis `hsources : b = true -> Exists va, Exists vb, evalSourceA s i.a = some va /\ evalSourceB s i.b = some vb`.
- **Relevant Lean definitions:** `evalGuard` (lines 251-257), `execAndB32` (lines 323-333), `Guard` (lines 186-190).
- **Description:** The formal statement is an iff only on the well-formed lookup domain: when b = true, both sources must resolve. Without `hsources`, the reverse direction would fail for b = true with a missing source (partial execution returns none, no executed outcome). This is exactly the approved partiality convention (PTX-AND-SEM2-048/049/050, risk R-2) and is not an unapproved precondition. The name, however, reads as an unconditional claim; the intent and precise-statement text make the domain explicit.
- **Consequence:** None for correctness. The human gate should accept the domain-conditioned statement and may choose a name that makes the domain explicit.
- **Required owner:** Proof Engineer / Lean Formalizer (optional naming precision).
- **Required revision:** None required.
- **Human review required:** Confirm at the human theorem-strength gate.

### F-3 — NOTE — THM-005 proposed at candidate strength

- **Exact location:** obligations-v1.json, THM-005 (lines 273-295); deferred property PTX-AND-DEF-002 (lines 357-362); risk R-3 (lines 416-418).
- **Relevant semantic claims:** PTX-AND-SEM2-022 (destination register; bit bucket open), PTX-AND-SEM2-062 (OQ-2: scalar and.b32 bit-bucket applicability open); architecture SF-A13 (general 9.2 bit-bucket rule); mapping-critic F-3 (bit bucket modeled at candidate strength).
- **Description:** The theorem `andB32Step_bit_bucket_preserves_state` is true of the Gate-C-approved Lean model (which materializes `Destination.bitBucket` at candidate strength), but the underlying scalar and.b32-specific applicability remains an open question. The obligations document retains the strength caveat explicitly and documents the alternative of removing/weakening the obligation until OQ-2 is resolved.
- **Consequence:** If the human gate prefers strict source-faithfulness, THM-005 may be deferred pending OQ-2; if the gate accepts the candidate-strength modeling approved at Gate C, THM-005 is provable as stated. Either way the set remains consistent.
- **Required owner:** Proof Engineer / Lean Formalizer (decision item).
- **Required revision:** None required before presentation.
- **Human review required:** Yes — explicit decision at the human theorem-strength gate.

### F-4 — NOTE — PRF-6 disposition as VAL-style (PTX-AND-VAL-002)

- **Exact location:** obligations-v1.json, PTX-AND-VAL-002 (lines 119-127); risk R-6 (lines 428-430); traceability_summary.required_area_coverage (line 491).
- **Relevant references:** architecture A-10 (PRF-6 vacuity risk; mov.b32/not.b32 lesson); semantics-v2 future_theorem_obligation_topics PRF-6 (line 326).
- **Description:** Result-domain membership (`0 <= value < 2^32` for every B32) is adopted as a representation-invariant VAL-style obligation rather than a semantic theorem, because under the typed `B32 = Fin (2^32)` representation it would otherwise be definitionally vacuous. The disposition is honest, correctly documented, and matches the approved architecture guidance.
- **Consequence:** None. The human gate should explicitly confirm the disposition so it is recorded as human-approved.
- **Required owner:** Proof Engineer (decision item).
- **Required revision:** None.
- **Human review required:** Yes — explicit confirmation at the human theorem-strength gate.

### F-5 — NOTE — THM-002 part (c) existence formulation

- **Exact location:** obligations-v1.json, THM-002, `step_complete` sketch (lines 200-201) and proof strategy (line 217).
- **Relevant Lean definitions:** `AndB32Step` (lines 348-355), `execAndB32` (lines 323-333), `ExecOutcome` (lines 302-304).
- **Description:** `step_complete` concludes `Exists o, execAndB32 s i = some o /\ (o = executed s' \/ o = guardFalse s')`. The proof must exhibit the specific outcome: for an executed step, o = `ExecOutcome.executed s'`; for a guardFalse step, o = `ExecOutcome.guardFalse s'`. This is provable. A direct equality would be stronger but is not required for the correspondence to be complete.
- **Consequence:** None. Adequate strength for the correspondence bridge.
- **Required owner:** Proof Engineer (informational).
- **Required revision:** None.
- **Human review required:** No.

### F-6 — NOTE — Vacuous/trivial-claim discipline verified

- **Exact location:** obligations-v1.json, compliance_notes item 3 (line 102), traceability_summary.determinism_note (line 493).
- **Relevant Lean definitions:** `AndB32Step` (lines 348-355) — an inductive Prop relation, not a function.
- **Description:** The set explicitly refuses to propose the trivial functional single-valuedness of `execAndB32` and instead proposes the substantive relational determinism (THM-001) and the function/relation correspondence (THM-002). The critic independently verified this discipline is honored and that no obligation is vacuous (all hypothesis sets satisfiable; no conclusion in the hypotheses; no circularity — non-vacuity arguments cite executable demonstrations, not the theorems themselves).
- **Consequence:** None.
- **Required owner:** None.
- **Required revision:** None.
- **Human review required:** No.

## 7. Required revisions (consolidated)

No substantive revision is required before the obligation set is presented for human theorem-strength approval. All findings are NOTE-level transparency/decision items.

Decision items for the human theorem-strength gate (explicit confirmation requested, not performed by this critic):
1. Confirm the PRF-6 VAL-style disposition (PTX-AND-VAL-002; F-4).
2. Decide keep-as-proposed vs. defer THM-005 (bit-bucket at candidate strength) pending OQ-2 resolution (F-3).
3. Accept the domain-conditioned THM-007 statement (and optionally refine the name to make the well-formed-domain condition explicit) (F-2).

Optional proof-stage refinements (not blocking):
1. Consider a direct-equality form for THM-002 part (c) (F-5).
2. Consider pinning the exact post-state in THM-003's conclusion (F-1).

## 8. Residual open questions

- Whether the human theorem-strength gate approves the PRF-6 VAL-style disposition (F-4; R-6).
- Whether the human theorem-strength gate keeps THM-005 as proposed or defers it until the scalar and.b32 bit-bucket applicability (OQ-2 / PTX-AND-SEM2-062) is resolved (F-3; R-3).
- Whether the exact post-state should be pinned in THM-003 (F-1) and THM-002(c) (F-5) — proof-stage style choices.
- The open questions carried by the deferred properties remain open: position-a immediates (PTX-AND-SEM2-061, DEF-003), whole-PTX frame claims (DEF-001), version/target gating theorems (DEF-004), out-of-domain behavior (DEF-005), error/UB absence (DEF-006), predicate encoding (DEF-007), operand-typing formulation (DEF-008). None blocks theorem-strength approval; each is honestly deferred.

## 9. Human theorem-strength gate readiness assessment

Ready for presentation to Human Theorem-Strength Approval. The obligation set `ptx-9.3-and-b32-obligations-v1` proposes 7 adequately strong, non-vacuous, faithful theorem obligations (THM-001..007) covering PRF-1..PRF-7, 6 validation obligations (VAL-001..006, including the PRF-6 disposition), and 8 honestly deferred properties. Every theorem statement was independently verified true of the Gate-C-approved Lean model; every semantic claim and Lean declaration reference resolves; no `sorry`/`admit`/axioms/`unsafe` are present; no vacuous, circular, or trivially functional determinism claims are proposed; no unapproved new preconditions are introduced (the THM-007 `hsources` hypothesis is the approved well-formed-domain condition of the partiality convention). Findings F-1..F-6 are all NOTE-level transparency/decision items. This assessment is not a human theorem-strength approval; approval is a human decision, and the three decision items (F-2, F-3, F-4) are flagged for explicit human confirmation.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/and-b32/theorems/obligations-v1.json` or any other artifact. No Lean code or theorem statements were written, no proofs were generated, no gate was approved, and nothing was promoted to `accepted/`. The required output artifact for this stage (`theorem-strength-critic-v1.md`) was created as a new immutable revision; no existing revision was overwritten.
