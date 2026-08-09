# Final Independent Semantic / Proof / Traceability Critique — and.b32 (run ptx-9.3-and.b32-d33dfec2)

## 1. Status

- Stage: FINAL_CRITIQUE (aggregation review), stage attempt 1, run revision 22.
- Run metadata: `runs/ptx-9.3-and.b32-d33dfec2/run.json` — unit `and.b32`, spec 9.3, artifact root `candidates/ptx/9.3/units/and-b32`, gates A/B/C/THEOREM_STRENGTH all `approved`, gate FINAL `pending`.
- This critique is an independent final aggregation review by the semantic critic. It does not approve the final human gate and does not edit or repair any artifact.
- Required artifact: `candidates/ptx/9.3/units/and-b32/reviews/final-critic-v1.md` (created as a new immutable revision; no prior revision existed at this path).

## 2. Inputs reviewed (latest revisions only)

Prior critiques (aggregation sources, all read in full):
- `candidates/ptx/9.3/units/and-b32/reviews/architecture-critic-v1.md` — verdict READY FOR HUMAN GATE A; findings F-1..F-5 MINOR/NOTE; no blockers.
- `candidates/ptx/9.3/units/and-b32/reviews/semantics-critic-v1.md` — verdict READY FOR PRESENTATION TO HUMAN GATE B; findings F-1..F-5 MINOR/NOTE; no blockers.
- `candidates/ptx/9.3/units/and-b32/reviews/lean-mapping-critic-v1.md` — verdict SUITABLE for Human Gate C presentation; findings F-1..F-6 NOTE; no blockers/majors.
- `candidates/ptx/9.3/units/and-b32/reviews/theorem-strength-critic-v1.md` — verdict READY FOR PRESENTATION TO HUMAN THEOREM-STRENGTH APPROVAL; findings F-1..F-6 NOTE; no blockers/majors.

Human gate/approval records (all confirmed to exist, all `decision: approved`, all `humanConfirmationRecorded: true`):
- `reviews/ptx-and-b32/gate-a/ptx-and-b32-a-approval-v1.json` (Gate A, 2026-08-09T17:45:04.222Z).
- `reviews/ptx-and-b32/gate-b/ptx-and-b32-b-approval-v1.json` (Gate B, 2026-08-09T18:44:55.281Z; references semantics SHA-256 `45e0fe93...24ca0e`).
- `reviews/ptx-and-b32/gate-c/ptx-and-b32-c-approval-v1.json` (Gate C, 2026-08-09T18:54:05.210Z; references AndB32-v1.lean SHA-256 `bcbe4975...4465`).
- `reviews/ptx-and-b32/theorem-strength/ptx-and-b32-theorem-strength-approval-v1.json` (THEOREM_STRENGTH, 2026-08-09T19:03:20.789Z; references obligations-v1.json SHA-256 `30f4f93b...f35b1`).

Approved semantic artifact:
- `candidates/ptx/9.3/units/and-b32/semantics/semantics-v2.json` (interpretation_id `ptx-9.3-and-b32-semantics-v2`, SHA-256 `45e0fe93f02a3261976962026eb7b5b2e1a5343c10d4a388f500f6f30a24ca0e`; 74 claims: 23 SOURCE_FACT, 32 DERIVED_INTERPRETATION, 7 DESIGN_DEPENDENCY, 0 ASSUMPTION, 12 OPEN_QUESTION; blocking_issue_count 0).

Theorem obligations:
- `candidates/ptx/9.3/units/and-b32/theorems/obligations-v1.json` (obligation_set_id `ptx-9.3-and-b32-obligations-v1`, SHA-256 `30f4f93bd9b31bec3ef3880663cc8ee43cf1c117ef68c6e3bd2758b6d70f35b1`; 7 theorem obligations PTX-AND-THM-001..007, 6 validation obligations, 8 deferred properties).

Installed Lean package artifacts (verified independently in this critique):
- `lean/Spec2Lean/PTX/AndB32.lean` (SHA-256 `bcbe497526596b5da9d96417ec565118c49d2d1374f01ab8e531b2159bc24465`; identical to Gate-C-approved candidate `candidates/ptx/9.3/units/and-b32/lean/AndB32-v1.lean`; matches `runs/.../lean-package.json`).
- `lean/Spec2Lean/PTX/AndB32Proofs.lean` (SHA-256 `cbf0347bcaaa1a68697f26e4290f7179587122651b0d22b807a469b9e3871c78`; identical to candidate `candidates/ptx/9.3/units/and-b32/lean/AndB32Proofs-v1.lean`; matches `runs/.../lean-proof-package.json`).
- `lean/Spec2Lean/Basic.lean` (trivial module; only import of the semantics file).
- `lean/lakefile.toml` (defines `lean_lib` `Spec2Lean`, the default target, so both installed modules are part of the root Lean package).

Evidence bundle (read for traceability): `candidates/ptx/9.3/units/and-b32/source-bundles/source-bundle-v2.json` (bundle_id `source-bundle-v2`, SHA-256 `57e86be0f823fa70e7559ca21cba30bf7f4b434a87c33cb39b134ce13f27ea53`).

## 3. Independent verification performed in this critique

Lean tool verification (this stage):
- `lean_check_file` on `lean/Spec2Lean/PTX/AndB32.lean`: success, exitCode 0, errorCount 0, warningCount 0.
- `lean_check_file` on `lean/Spec2Lean/PTX/AndB32Proofs.lean`: success, exitCode 0, errorCount 0, warningCount 0.
- `lean_check_file` on `candidates/ptx/9.3/units/and-b32/lean/AndB32Proofs-v1.lean`: success, exitCode 0, errorCount 0, warningCount 0 (SHA-256 matches the installed proof file, confirming the proof candidate is the installed artifact).
- `lean_run_eval` on `lean/Spec2Lean/PTX/AndB32.lean`: 17 outputs, all matching the documented expected values (0, 4294967295, 0, 1, 16711680, some 2147483648, some 16711680, some true, some true, some 100, some 1, some 5, some 1, some 1, some 1, some 5, "partial-none").
- Source scan for forbidden constructs: the only `sorry|admit|axiom|unsafe` match in either installed Lean file is a prose header comment stating that these are not used; no code occurrence exists. No `set_option` diagnostics suppression, no `partial`/`opaque` code declarations, no `#eval` inside the proof artifact.

Theorem-declaration verification:
- All 16 approved theorem declarations from obligations-v1.json are present verbatim (statement-for-statement) in `AndB32Proofs.lean`:
  - THM-001 `andB32Step_deterministic`; THM-002 `exec_sound_executed`, `exec_sound_guardFalse`, `step_complete`, `step_partial_complete`; THM-003 `execAndB32_and_fidelity`; THM-004 `andB32Step_destination_only_frame`; THM-005 `andB32Step_bit_bucket_preserves_state`; THM-006 `execAndB32_guard_false_preserves_state`, `andB32Step_guard_false_frame`; THM-007 `andB32_executes_iff_guard_true` plus the five evalGuard lemmas (`evalGuard_unguarded_true`, `evalGuard_atPos_true`, `evalGuard_atNeg_true_when_pred_false`, `evalGuard_atPos_false`, `evalGuard_atNeg_false_when_pred_true`).
- Each theorem statement in the proof file matches the corresponding `lean_statement_sketch` in obligations-v1.json; no statement was weakened, strengthened, or altered (including the `Exists` form of THM-003 and the domain-conditioned `hsources` hypothesis of THM-007, both as approved).

Official-source spot verification (restricted spec tools; only the state-affecting claims were re-visited per final-review discipline):
- Section 9.7.8.1 `and` (anchor `logic-and-shift-instructions-and`, line 14256): syntax `and.type d, a, b;`, type set `{ .pred, .b16, .b32, .b64 }`, "Bitwise AND.", "Compute the bit-wise and operation for the bits in a and b.", Semantics `d = a & b;`, Notes, PTX ISA Note 1.0, Target ISA Note all architectures, examples `and.b32  x,q,r;` and `and.b32  sign,fpvalue,0x80000000;` — all verbatim as recorded.
- Section 9.7.13.2 `@` (anchor `control-flow-instructions-at`, line 21826): Description "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." and Semantics "If {!}p then instruction" — the previously blocking (BLK-1) state-affecting guard-false evidence is present verbatim, exactly as used by semantics-v2 (PTX-AND-SEM2-063/071/074), the Lean guard model, and THM-006/THM-007.

## 4. Aggregated review summary

| Artifact | Prior verdict | Blockers | Majors | Minors/Notes | Human gate |
|---|---|---|---|---|---|
| architecture/foundation-v1.md | READY FOR GATE A | 0 | 0 | 1 MINOR / 4 NOTE | A approved |
| semantics/semantics-v2.json | READY FOR GATE B | 0 | 0 | 1 MINOR / 4 NOTE | B approved |
| lean/AndB32-v1.lean (installed AndB32.lean) | SUITABLE FOR GATE C | 0 | 0 | 0 MINOR / 6 NOTE | C approved |
| theorems/obligations-v1.json | READY FOR THEOREM-STRENGTH | 0 | 0 | 0 MINOR / 6 NOTE | THEOREM_STRENGTH approved |
| lean/AndB32Proofs-v1.lean (installed AndB32Proofs.lean) | (proof stage completed) | 0 | 0 | see F-1..F-5 below | FINAL pending |

Traceability chain verified end-to-end: official HTML (9.7.8.1 + 9.7.13.2 + 9.3 + 9.7) -> source-bundle-v2.json fragment IDs -> semantics-v2.json claims (74) -> AndB32.lean declarations (comment-cited claim IDs) -> obligations-v1.json (semantic_claim_ids and lean_declarations_used all resolve) -> AndB32Proofs.lean (16 declarations match the approved sketches). No phantom claim IDs, no cross-unit semantic authority, no invented evidence.

## 5. Findings

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | NOTE | AndB32Proofs.lean THM-007 `andB32_executes_iff_guard_true`; obligations-v1.json lines 323-333 | Carried from theorem-strength-critic F-2: the name reads as an unconditional claim while the statement is domain-conditioned on the well-formed-source hypothesis `hsources` (required by the approved partiality convention). The human theorem-strength gate approved the domain-conditioned statement; the name is a precision preference only and does not overstate the proved content. |
| F-2 | NOTE | AndB32Proofs.lean THM-005 `andB32Step_bit_bucket_preserves_state`; obligations-v1.json PTX-AND-THM-005 / DEF-002 | Carried from theorem-strength-critic F-3 and mapping-critic F-3: the bit-bucket theorem is proved at candidate strength (general section 9.2 rule; scalar and.b32-specific applicability remains OPEN_QUESTION PTX-AND-SEM2-062). Keep-as-proposed was accepted by the theorem-strength gate; the caveat must remain attached and must not be presented as and.b32-specific NVIDIA behavior. |
| F-3 | NOTE | obligations-v1.json PTX-AND-VAL-002; AndB32.lean `B32`/`Fin (2^32)` | Carried from theorem-strength-critic F-4: PRF-6 (result-domain membership) is disposed as a VAL-style definitional well-formedness obligation rather than a semantic theorem, per architecture A-10; the disposition was confirmed by the theorem-strength gate. |
| F-4 | NOTE | semantics-v2.json open questions; obligations-v1.json deferred properties PTX-AND-DEF-001..008 | Carried open questions (position-a immediate PTX-AND-SEM2-061, bit-bucket applicability 062, error/UB absence 048/049/050, operand-typing 067, predicate encoding 065, result-width prose 069, version/target gating) are all honestly deferred and non-blocking; they affect static well-formedness or are absence records and do not change the state transition of any legal bounded instruction. |
| F-5 | NOTE | lean/Spec2Lean/PTX/AndB32.lean and AndB32Proofs.lean; lean/lakefile.toml | Root Lean package verification in this environment was performed via `lake env lean` (lean_check_file/lean_run_eval) on both installed modules with 0 errors/0 warnings and successful import resolution (Spec2Lean.Basic / Spec2Lean.PTX.AndB32); a full `lake build` was not executed directly in this stage because the environment exposes no shell. Both modules are inside the `Spec2Lean` lean_lib default target, so no package-registration gap was found. |
| F-6 | NOTE | run.json execution records (semantics-v2 390 vs 389 lines; foundation 276 vs 275) | Carried from earlier critics (architecture F-4, semantics F-2): cosmetic line-count off-by-one entries in run metadata; no semantic impact. |

BLOCKER: 0. MAJOR: 0. MINOR: 0. NOTE: 6.

## 6. Required final-review statements

- **BLOCKER/MAJOR/MINOR/NOTE counts:** 0 / 0 / 0 / 6 (all findings NOTE-level transparency items; none requires a revision before final human approval).
- **Source-faithfulness status:** FAITHFUL. The executed semantics (`d = a & b;` over a 32-bit untyped bit-value domain; operand order d, a, b; register-only source a; register-or-immediate source b; no modifiers; guard model unguarded/@p/@!p with source-resolved guard-false no-op) is traceable to the official PTX ISA 9.3 HTML sections 9.7.8.1, 9.7, 9.3, 9.7.13.2 via bundle-internal fragment IDs; the state-affecting guard-false clause was re-verified verbatim in this critique. Zero ASSUMPTION-classified semantic claims; no invented error/UB behavior; no semantic claims copied from other units.
- **Unresolved state-affecting gaps:** NONE blocking. The only previously state-affecting gap (BLK-1, guard-false state effect) was resolved at source level by source-bundle-v2 (CTX-08) and re-verified here. Remaining open questions are static-well-formedness or absence-record items and do not affect the state transition of any legal bounded instruction. Two documented modeling decisions with state effect carry at candidate strength and remain visible: guard-false branch does not read source operands (mapping-critic F-1, consistent with "do nothing") and bit-bucket no-write destination (OQ-2/AMB-3, general 9.2 rule strength).
- **Theorem weakening status:** NO WEAKENING. All 16 proof-file theorem declarations match the theorem-strength-approved statement sketches exactly; determinism is stated over the relational `AndB32Step` (non-vacuous), fidelity pins the written value to `andValue va vb` of pre-instruction source reads, frame/guard/bit-bucket obligations are stated at the approved strength; no vacuous, circular, or trivially functional determinism claims exist.
- **Proof bypass status:** NONE. No `sorry`, `admit`, new `axiom`, `unsafe`, `set_option` suppression, `partial`/`opaque` code, or placeholder proofs in either installed Lean file; the proofs are machine-checked tactic proofs.
- **Lean compilation status:** COMPILES. `lean/Spec2Lean/PTX/AndB32.lean` and `lean/Spec2Lean/PTX/AndB32Proofs.lean` each check with 0 errors, 0 warnings via `lake env lean`; the semantics module's 17 executable examples evaluate to the expected values; candidate proof file SHA matches the installed proof file SHA.
- **Readiness for explicit human final approval:** READY FOR PRESENTATION TO HUMAN FINAL APPROVAL. All four prior human gates (A, B, C, THEOREM_STRENGTH) are approved; the artifact chain is internally consistent and traceable; no blocker or major defect exists at any level. This critique does not grant final acceptance; final acceptance is a human decision (Gate FINAL).

## 7. Residual open questions (non-blocking, carried)

- Position-a immediate permissibility (OQ-1 / PTX-AND-SEM2-061) — affects static well-formedness only; the Lean conservatively omits the constructor.
- Scalar and.b32-specific bit-bucket demonstration (OQ-2 / PTX-AND-SEM2-062) — THM-005 carried at candidate strength.
- Whether error/UB/implementation-defined absence means none exist (PTX-AND-SEM2-048/049/050) — absence records only.
- Exact operand-typing formulation (OQ-7 / PTX-AND-SEM2-067) and predicate-value encoding (OQ-5 / PTX-AND-SEM2-065) — deferred to static-well-formedness / encoding decisions.
- Version/target gating theorems (PTX-AND-SEM2-044/046/047/059) — deferred to the validation layer (VAL-5/VAL-6).

## 8. Critic independence statement

The critic did not edit, replace, or repair any reviewed artifact. No Lean code, theorem statement, proof, semantics, or source bundle was written during this review. No gate was approved and nothing was promoted to `accepted/`. The required final-review artifact was created as a new immutable revision at the orchestrator-supplied path; no existing revision was overwritten.
