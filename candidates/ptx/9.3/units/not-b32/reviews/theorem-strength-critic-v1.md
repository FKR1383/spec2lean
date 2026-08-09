# Independent Theorem-Strength Critique — not-b32 obligations-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/not-b32/theorems/obligations-v1.json` (obligation_set_id `ptx-9.3-not-b32-obligations-v1`, 491 lines, status `READY_FOR_STRENGTH_REVIEW`), the first theorem-obligation set for the bounded `not.b32` unit.
- This critique is an independent semantic-critic review of theorem strength and non-vacuity against the human-approved Gate-A architecture, Gate-B semantics, and Gate-C Lean mapping. It does not approve the theorem-strength gate and does not edit or repair the reviewed artifact.
- Run metadata consulted: `runs/ptx-9.3-not.b32-5e83de43/run.json` (unit `not.b32`, stage THEOREM_STRENGTH_CRITIQUE attempt 1, revision 16; Gates A/B/C approved, THEOREM_STRENGTH pending, FINAL pending).
- This is the artifact required by the orchestrator for stage THEOREM_STRENGTH_CRITIQUE: `candidates/ptx/9.3/units/not-b32/reviews/theorem-strength-critic-v1.md`. It did not exist before this pass; a new immutable revision was created (no overwrite).

## 2. Overall verdict

**ADEQUATE for human theorem-strength approval (Gate THEOREM_STRENGTH); the set is ready for presentation. The critic does not approve the gate.**

The 7 theorem obligations (PTX-NOT-THM-001..007) are each stated at appropriate strength, are non-vacuous, traceable to the Gate-B-approved semantics and to existing Lean declarations, and cover every required area of the approved PRF-1..PRF-7 family plus the documented VAL-style disposition of PRF-6. The 6 validation obligations are correctly distinguished from theorem obligations (architecture D-26). No theorem is vacuous, no statement is weakened below the semantic claim, no theorem name overstates its content, and no forbidden construct (`sorry`/`admit`/new axioms/`unsafe`) appears. One MINOR gate decision point (bit-bucket PRF-3 strength) and three NOTE-level confirmations are recorded below.

Independent verification performed for each obligation:

- **Provability soundness** — each `lean_statement_sketch` was checked by hand against the Lean declarations in `NotB32-v1.lean` (compiles 0 errors/0 warnings; SHA-256 `d73332a9...` matches the obligations' reference). All referenced declaration names, constructors, and field projections exist with the correct types.
- **Non-vacuity** — each obligation's `non_vacuity_argument` was checked against the executable examples actually present in the Lean file; the cited witnesses (executed aliasing example `r1=5 → ~5=4294967290`; guard-false `@p p=false` keeping `r1=5`; partial `none` example; bit-bucket no-write example) exist and behave as claimed.
- **Traceability** — every cited `PTX-NOT-SEM1-*` claim exists in `semantics-v1.json` (claims 001..073) with the cited classification and content; every cited fragment is in `PTX-9.3-NOT-001..033`; every cited Lean declaration exists in the mapping.
- **No circularity** — no obligation is justified by the theorem it states; evidence bases are semantic claims and official source fragments.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/not-b32/theorems/obligations-v1.json` — complete read (491/491 lines); all 7 theorem obligations, 6 validation obligations, 8 deferred properties, 6 risks, and the traceability summary inspected; every `lean_statement_sketch`, hypothesis list, conclusion, non-vacuity argument, and strength-risk item checked.
- `candidates/ptx/9.3/units/not-b32/lean/NotB32-v1.lean` — complete read (413/413 lines); `lean_check_file` re-run: success, exitCode 0, 0 errors, 0 warnings; all declarations referenced by the obligations confirmed present (`NotB32Step`, `execNotB32`, `ExecOutcome`, `evalGuard`, `evalSource`, `updateDestination`, `complementValue`, `Destination.reg/bitBucket`, `MachineState.valueRegs/predRegs`, `Guard`, `PredId`, `B32`, `Fin`, `b32DomainSize`, `b32Bits`, `NotTypeSpecifier`, `SourceOperand`).
- `candidates/ptx/9.3/units/not-b32/semantics/semantics-v1.json` — complete read (337/337 lines); all 73 claims and the `future_theorem_obligation_topics` PRF-1..PRF-7 cross-checked against the obligations' claim citations.
- `candidates/ptx/9.3/units/not-b32/source-bundles/source-bundle-v1.json` — fragment IDs and key fragments (`PTX-9.3-NOT-005` `d = ~a;`, `NOT-009` `not.b32 mask,mask;`, `NOT-016` bit-bucket rule, `NOT-031/032` false-guard clause) verified present with the cited content.
- `candidates/ptx/9.3/units/not-b32/architecture/foundation-v2.md` — PRF-1..PRF-7 and VAL-1..VAL-6 families, D-25/D-26, and A-10 (PRF-6 vacuity disposition) confirmed present.
- `candidates/ptx/9.3/units/not-b32/reviews/lean-mapping-critic-v1.md` — full read; its NOTE findings F-1..F-4 (Bool predicate encoding, bit-bucket general-rule strength, theorem deferral, version/target metadata) are correctly carried forward into the obligations (deferred properties DEF-002/004/007, risks R-1/R-3/R-6, THM-005 strength caveat).
- `reviews/ptx-not-b32/gate-c/ptx-not-b32-c-approval-v1.json` — verified (decision `approved`, humanConfirmationRecorded true, gateApprovalPerformed true, submittedAtUtc 2026-08-09T13:16:40.284Z; artifacts `NotB32-v1.lean` SHA-256 `d73332a9...` and `lean-mapping-critic-v1.md` SHA-256 `feba6e52...`).
- `reviews/ptx-not-b32/gate-b/ptx-not-b32-b-approval-v1.json` and `reviews/ptx-not-b32/gate-a/ptx-not-b32-a-approval-v1.json` — existence and decision `approved` confirmed (dates match the obligations' references).
- No proofs exist for this unit yet; none are expected at this stage. Proof critique is a later-stage concern.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | PTX-NOT-THM-005 (bit-bucket frame; obligations lines 270-292) | PRF-3 is stated at the strength of the general section 9.2 bit-bucket rule while scalar `not.b32`-specific applicability remains open (PTX-NOT-SEM1-067 / GAP-2 / AMB-3). The obligation honestly records the caveat, but the human theorem-strength gate must explicitly decide whether to keep THM-005 at candidate strength or defer it. |
| F-2 | NOTE | PTX-NOT-THM-007 (guard-behavior; obligations lines 319-343) | The `hsources` hypothesis (source resolves when guard true) is a necessary well-formed-domain restriction for the reverse direction of the biconditional; it is explicit and documented (risk R-2). It must remain explicit in the proof file and must not be silently dropped or hardened. |
| F-3 | NOTE | PTX-NOT-THM-003 (complement fidelity; obligations lines 220-244) | The existential conclusion is faithful to the semantic claim "the value written equals the bitwise complement of the value read". A direct (non-existential) post-state equality `s' = updateDestination s (Destination.reg r) (complementValue va)` is equally provable and may be adopted at the proof stage for a slightly stronger statement; not required for adequacy. |
| F-4 | NOTE | PTX-NOT-VAL-002 / PRF-6 disposition (obligations lines 118-126, risk R-6) | The reclassification of PRF-6 (result-domain membership) as a VAL-style definitional well-formedness obligation is confirmed appropriate: under the typed `B32` (`toFin : Fin b32DomainSize`) representation the membership claim holds definitionally, so a semantic theorem would be vacuous. This matches architecture A-10 and the mov.b32 lesson. |

No BLOCKER or MAJOR findings.

## 5. Findings detail

### F-1 — MINOR — PRF-3 bit-bucket theorem requires an explicit gate decision

- **Exact location:** `PTX-NOT-THM-005` (`notB32Step_bit_bucket_preserves_state`), obligations-v1.json lines 270-292; `strength_risks` item and `deferred_properties` `PTX-NOT-DEF-002` (lines 354-359).
- **Relevant approved semantics/architecture:** SOURCE_FACT PTX-NOT-SEM1-011 (general section 9.2 bit-bucket rule, `PTX-9.3-NOT-016`); OPEN_QUESTION PTX-NOT-SEM1-067 (OQ-2/GAP-2/AMB-3: scalar `not.b32`-specific bit-bucket applicability not evidenced); architecture PRF-3 ("if adopted"); mapping-critic F-2 (bit-bucket modeled at general-rule strength).
- **Description:** The theorem `if NotB32Step s i s' and i.d = Destination.bitBucket then s' = s` is provable in the model (both constructors: guardFalse gives `s' = s`; executed with bitBucket gives `s' = updateDestination s bitBucket _ = s`). It is non-vacuous (the Lean file's bit-bucket example shows no value register written). The obligation correctly states it only at the strength of the general rule and explicitly warns that it must not be presented as a `not.b32`-specific explicit NVIDIA statement (risk R-3). The remaining question is a gate decision, not an artifact defect: whether the theorem-strength gate accepts PRF-3 at candidate strength while GAP-2/AMB-3 is open, or defers it. The obligations give the reviewer the option (lines 287-289) and record the dependency (DEF-002).
- **Consequence:** No change is required in the obligation set before presentation. The human theorem-strength reviewer must record an explicit decision on THM-005's status (keep at general-rule strength vs. defer). If deferred, THM-005 is removed or re-scoped and DEF-002 is updated; if kept, the caveat must remain traceable through final acceptance.
- **Required owner:** Human theorem-strength gate reviewer (decision); Proof Engineer if THM-005 is kept (proof) or if deferral changes the set.
- **Required revision:** None before the gate; the decision is recorded by the human gate.
- **Human review required:** Yes.

### F-2 — NOTE — THM-007's `hsources` hypothesis is a necessary and explicit domain restriction

- **Exact location:** `PTX-NOT-THM-007` (`notB32_executes_iff_guard_true`), obligations-v1.json lines 319-343, hypothesis `hsources : b = true -> Exists va, evalSource s i.a = some va`; risk R-2 (lines 408-411).
- **Description:** In the model, if the guard is true but the source register is missing, `execNotB32` returns `none` (partial execution), so an executed outcome does not exist. The plain statement "executed outcome exists iff guard true" is therefore false without a source-resolution hypothesis in the reverse direction. The obligation correctly adds `hsources` as an explicit well-formed-domain hypothesis, documenting it in risk R-2 as the approved partial-execution convention (PTX-NOT-SEM1-052/053/054). This is not a hidden precondition and not a silent weakening: the hypothesis is necessary and the semantic claim PRF-5 ("executes iff complete guard expression true") is thereby faithfully encoded on the approved well-formed lookup domain.
- **Consequence:** The proof file must keep `hsources` explicit; it must not be dropped (would make the reverse direction unprovable/false) and must not be hardened into an unconditional source-resolution hypothesis (would be an unapproved strengthening and would make the reverse direction trivial in a different way, as the obligation's strength_risks already note).
- **Required owner:** Proof Engineer (proof stage); human theorem-strength reviewer (confirmation).
- **Required revision:** None.
- **Human review required:** Yes (confirmation during theorem-strength review).

### F-3 — NOTE — THM-003 existential conclusion is faithful; a direct post-state equality is an optional strengthening

- **Exact location:** `PTX-NOT-THM-003` (`execNotB32_complement_fidelity`), obligations-v1.json lines 220-244.
- **Description:** The conclusion `Exists s', execNotB32 s i = some (ExecOutcome.executed s') /\ s'.valueRegs r = some (complementValue va)` exactly expresses the approved DERIVED bit-complement semantics (PTX-NOT-SEM1-033) and the source fact `d = ~a;` (PTX-NOT-SEM1-032), including the read-before-write/aliasing content (PTX-NOT-SEM1-065) because `va` is read from the pre-instruction state `s`. The existential is not a weakening of the semantic claim. The proof strategy (lines 242-243) already constructs the post-state as `updateDestination s i.d (complementValue va)`, so a direct equality statement would be equally provable; adopting it at the proof stage is optional and harmless.
- **Consequence:** None. The theorem set is adequate as stated.
- **Required owner:** Proof Engineer (optional strengthening at proof stage).
- **Required revision:** None.
- **Human review required:** No.

### F-4 — NOTE — PRF-6 VAL-style disposition is confirmed appropriate

- **Exact location:** `PTX-NOT-VAL-002` (obligations-v1.json lines 118-126) and risk R-6 (lines 424-427).
- **Description:** The obligations adopt the recorded disposition (semantics PRF-6 topic; architecture A-10; architecture-critic v1 F-3; mov.b32 lesson) that result-domain membership is definitionally satisfied by the typed representation: every `B32` wraps a `Fin (2^32)` value and `complementValue` returns a `B32`, so a semantic theorem "the written value lies in the 32-bit domain" would be definitionally vacuous. Reclassifying PRF-6 as a VAL-style definitional well-formedness check (VAL-002) is the correct non-vacuity-preserving treatment and is consistent with D-26's distinction between validation and proof obligations. The risk R-6 explicitly asks the theorem-strength reviewer to confirm this disposition; the critic confirms it.
- **Consequence:** None. No vacuous PRF-6 theorem is proposed.
- **Required owner:** Human theorem-strength reviewer (confirmation).
- **Required revision:** None.
- **Human review required:** Yes (confirmation during theorem-strength review).

## 6. Theorem-strength and non-vacuity verification notes

Per-obligation analysis (statement → provability → non-vacuity → traceability):

- **PTX-NOT-THM-001 (`notB32Step_deterministic`)** — Relational determinism over `NotB32Step`. Sound: both-`guardFalse` gives `s1 = s = s2`; both-`executed` gives `evalSource = some va1 = some va2` (function) hence `va1 = va2` hence `s1 = s2`; mixed constructors force `evalGuard = some false` and `some true` simultaneously, impossible. Non-vacuous: both constructors are inhabited by executable examples (aliasing executed case; `@p p=false` guardFalse case). Correctly does NOT propose the trivial functional single-valuedness of `execNotB32` (compliance note 3; determinism_note). Names the PRF-1 family accurately.
- **PTX-NOT-THM-002 (`execNotB32_NotB32Step_correspondence`)** — Four-part soundness/completeness/partial-completeness bridge, including the precise `none ↔ no-step` equivalence that encodes the approved partiality convention (PTX-NOT-SEM1-052/053/054). Each part verified sound by case analysis on `execNotB32`/`NotB32Step` (see part (d) check: `none` arises exactly when `evalGuard = none` or (`some true` and `evalSource = none`), precisely when no constructor applies). Non-vacuous with witnesses for every part. Faithful to the Lean file's own deferred-correspondence note (lines 300-310). Adequate and appropriately strong.
- **PTX-NOT-THM-003 (`execNotB32_complement_fidelity`)** — Full-strength `d = ~a;` fidelity with pre-state source read; subsumes aliasing. Non-vacuous (complement examples). Sound. Adequate.
- **PTX-NOT-THM-004 (`notB32Step_destination_only_frame`)** — Frame property: other value registers and all predicate registers unchanged; covers both constructors (guardFalse case is trivial `s' = s`; executed case via `updateDestination`). Non-vacuous (r1/r2 update example). Carries the negative-evidence caveat for components outside the model (risk R-1) without overstating. Adequate.
- **PTX-NOT-THM-005 (`notB32Step_bit_bucket_preserves_state`)** — Provable and non-vacuous at general-rule strength; caveat correctly retained. Gate decision point (F-1).
- **PTX-NOT-THM-006 (`execNotB32_guard_false_preserves_state`)** — Functional and relational forms of the guard-false no-op; grounded in DERIVED_INTERPRETATION PTX-NOT-SEM1-035 (source-resolved via `PTX-9.3-NOT-031/032`), never presented as a human assumption (human_assumption_dependencies empty). Non-vacuous (`@p p=false` example). Adequate.
- **PTX-NOT-THM-007 (`notB32_executes_iff_guard_true`)** — Biconditional classification plus per-constructor `evalGuard` lemmas; all lemmas are definitional facts of `evalGuard`. Non-vacuous for both truth values of `b`. Explicit domain hypothesis (F-2). Adequate.

Coverage of required areas (obligations `required_area_coverage`): bit-complement fidelity (THM-003), read-before-write aliasing (THM-003), destination-only update (THM-004), unrelated value-register frame (THM-004), predicate-register preservation (THM-004), bit-bucket preservation (THM-005), false-guard preservation (THM-006), guard-behavior classification (THM-007), relational determinism (THM-001), function/relation correspondence (THM-002), result-domain membership (VAL-002 disposition). Complete for the bounded unit.

## 7. Required revisions (consolidated)

No substantive revisions are required before the theorem-strength gate. Required human decisions/confirmations:

1. Record an explicit decision on THM-005/PRF-3: keep at general-rule strength (with the caveat traceable through final acceptance) or defer until GAP-2/AMB-3 (PTX-NOT-SEM1-067) is resolved (F-1, MINOR).
2. Confirm the `hsources` well-formed-domain hypothesis in THM-007 is the intended strength (F-2, NOTE).
3. Confirm the PRF-6 VAL-style disposition (VAL-002) (F-4, NOTE).
4. Optional: allow a direct (non-existential) post-state equality for THM-003 at the proof stage (F-3, NOTE).

## 8. Residual open questions

- Will the human theorem-strength reviewer accept PRF-3 at general-rule strength while the scalar `not.b32` bit-bucket applicability question (GAP-2/AMB-3/PTX-NOT-SEM1-067) remains open (F-1)?
- Will the proof stage keep THM-007's `hsources` hypothesis explicit and exactly in the documented shape (F-2)?
- Will the proof stage adopt the optional direct post-state equality for THM-003, and will the theorem names remain as proposed (all names verified not to overstate)?

## 9. Gate readiness assessment

Ready for presentation to the human theorem-strength gate. The obligation set is complete for the approved PRF-1..PRF-7 families (with PRF-6 disposition), each obligation is stated at appropriate strength with sound, non-vacuous statements over existing Lean declarations, all traceability is valid (claim IDs, fragment IDs, and Lean declarations all exist and match), and no forbidden construct or hidden assumption appears. The set does not weaken semantics, does not invent behavior, does not propose vacuous theorems, and does not overstate theorem names. The one MINOR finding is a documented gate decision point (bit-bucket strength), and the three NOTE findings are confirmations for the human reviewer. This assessment is not a theorem-strength approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/not-b32/theorems/obligations-v1.json`. No theorem statements were rewritten, no semantics were altered, no source evidence was fabricated, no theorem was weakened to make it provable, and no forbidden constructs were introduced. No gates were approved and nothing was promoted to `accepted/`.
