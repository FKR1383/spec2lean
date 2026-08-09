# Independent Final Critique — not.b32 (run ptx-9.3-not.b32-5e83de43)

## 1. Status

- Stage: FINAL_CRITIQUE (stage attempt 1, run revision 35).
- This is the aggregation final review for the bounded PTX ISA 9.3 `not.b32` formalization unit. It reviews the complete artifact chain (architecture → source bundle → semantics → Lean mapping → theorem obligations → proofs) and the human gate records.
- This review is an independent semantic-critic aggregation. It does **not** approve Gate FINAL and does not edit or repair any artifact.
- Required artifact: `candidates/ptx/9.3/units/not-b32/reviews/final-critic-v1.md` (created new; no prior revision existed).

## 2. Inputs reviewed

- Run metadata: `runs/ptx-9.3-not.b32-5e83de43/run.json` (520 lines; full history and execution records; gates A/B/C/THEOREM_STRENGTH approved, FINAL pending).
- Human gate records:
  - `reviews/ptx-not-b32/gate-a/ptx-not-b32-a-approval-v1.json` — decision `approved`, humanConfirmationRecorded true, submittedAtUtc 2026-08-09T12:23:43.550Z.
  - `reviews/ptx-not-b32/gate-b/ptx-not-b32-b-approval-v1.json` — decision `approved`, humanConfirmationRecorded true, submittedAtUtc 2026-08-09T12:53:51.135Z.
  - `reviews/ptx-not-b32/gate-c/ptx-not-b32-c-approval-v1.json` — decision `approved`, humanConfirmationRecorded true, submittedAtUtc 2026-08-09T13:16:40.284Z.
  - `reviews/ptx-not-b32/theorem-strength/ptx-not-b32-theorem-strength-approval-v1.json` — decision `approved`, humanConfirmationRecorded true, submittedAtUtc 2026-08-09T13:33:26.177Z.
- Prior critiques (all read in full):
  - `candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v2.md` (verdict: SUITABLE for Gate A; 0 BLOCKER, 0 MAJOR, 0 MINOR, 2 NOTE; F-1 v1-MAJOR verified resolved).
  - `candidates/ptx/9.3/units/not-b32/reviews/semantics-critic-v1.md` (verdict: SUITABLE for Gate B; 0 BLOCKER, 0 MAJOR, 1 MINOR F-1, 3 NOTE F-2..F-4).
  - `candidates/ptx/9.3/units/not-b32/reviews/lean-mapping-critic-v1.md` (verdict: SUITABLE for Gate C; 0 BLOCKER, 0 MAJOR, 0 MINOR, 4 NOTE F-1..F-4).
  - `candidates/ptx/9.3/units/not-b32/reviews/theorem-strength-critic-v1.md` (verdict: ADEQUATE; 0 BLOCKER, 0 MAJOR, 1 MINOR F-1, 3 NOTE F-2..F-4).
- Approved semantic artifact: `candidates/ptx/9.3/units/not-b32/semantics/semantics-v1.json` (SHA-256 `477f9408...`, 73 claims, 337 lines) — read in full.
- Theorem obligations: `candidates/ptx/9.3/units/not-b32/theorems/obligations-v1.json` (SHA-256 `5b477e89...`, 491 lines) — read in full.
- Lean semantics (installed and candidate): `lean/Spec2Lean/PTX/NotB32.lean` and `candidates/ptx/9.3/units/not-b32/lean/NotB32-v1.lean` — identical (SHA-256 `d73332a9...`, 413 lines); full read; re-checked with Lean tooling.
- Lean proofs (installed and candidate): `lean/Spec2Lean/PTX/NotB32Proofs.lean` and `candidates/ptx/9.3/units/not-b32/lean/NotB32Proofs-v1.lean` — identical (SHA-256 `391ee89f...`, 488 lines); full read; re-checked with Lean tooling.
- Root Lean package: `lean/Spec2Lean.lean` (imports Spec2Lean.Basic, AddU32(+Proofs), MovB32(+Proofs), NotB32(+Proofs)) — re-checked.
- `lean/Spec2Lean/Basic.lean` — 1-line placeholder, no axioms.
- Source bundle: `candidates/ptx/9.3/units/not-b32/source-bundles/source-bundle-v1.json` — 33 fragments PTX-9.3-NOT-001..033, gaps GAP-1..GAP-8 (fragment/claim cross-checks only).
- Official source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — two load-bearing anchors re-verified (not section 14358-14388; false-guard clause 21826-21853); no conflicts found with the prior critiques' verified source facts.
- Auxiliary: `candidates/ptx/9.3/units/not-b32/lean/NotB32Probe.lean` — neutralized compiling stub (imports NotB32 only; no declarations).

## 3. Independent Lean verification performed in this pass

| Check | Result |
|---|---|
| `lean_check_file lean/Spec2Lean/PTX/NotB32.lean` | success, exit 0, 0 errors, 0 warnings |
| `lean_check_file lean/Spec2Lean/PTX/NotB32Proofs.lean` | success, exit 0, 0 errors, 0 warnings |
| `lean_check_file candidates/.../lean/NotB32-v1.lean` | success, exit 0, 0 errors, 0 warnings |
| `lean_check_file candidates/.../lean/NotB32Proofs-v1.lean` | success, exit 0, 0 errors, 0 warnings |
| `lean_check_file lean/Spec2Lean.lean` (root package) | success, exit 0, 0 errors, 0 warnings |
| `lean_check_file candidates/.../lean/NotB32Probe.lean` | success, exit 0, 0 errors, 0 warnings (neutralized stub) |
| `lean_run_eval lean/Spec2Lean/PTX/NotB32.lean` | 11/11 executable examples evaluate to the expected results: `4294967295` (~0), `0` (~0xFFFFFFFF), `4294967290` (~5), `some true` (unguarded), `some true` (@!p, p=false), `some 100` (destination update), `some 1` (bit bucket no-write), `some 5` (@p p=false guard-false), `some 4294967290` (@!p executes ~5), `some 4294967290` (aliasing read-before-write), `"partial-none"` (missing source → partial) |
| Forbidden constructs (`sorry`/`admit`/`axiom`/`unsafe`/`set_option`) in all Lean files | none; only prose mentions inside comments |

All 16 approved theorem declarations are present in `NotB32Proofs.lean` and their statements match the human-approved obligation set `obligations-v1.json` exactly:

- PTX-NOT-THM-001 `notB32Step_deterministic` — relational determinism (PRF-1), non-vacuous over the inductive relation (D-25).
- PTX-NOT-THM-002 (a)-(d) `exec_sound_executed`, `exec_sound_guardFalse`, `step_complete`, `step_partial_complete` — function/relation correspondence bridge, including `none ↔ no-step` partial-completeness. The single syntactic substitution `not` → `Not` in part (d) is documented in the file header and is definitionally identical (`Not` is the propositional negation), so it is not a weakening.
- PTX-NOT-THM-003 `execNotB32_complement_fidelity` — full-strength `d = ~a;` with pre-state source read (read-before-write aliasing preserved).
- PTX-NOT-THM-004 `notB32Step_destination_only_frame` — destination-only frame with `r' != r` inequality as approved.
- PTX-NOT-THM-005 `notB32Step_bit_bucket_preserves_state` — at general-rule strength with the R-3 caveat retained (kept at candidate strength by the human theorem-strength gate).
- PTX-NOT-THM-006 (functional + relational) `execNotB32_guard_false_preserves_state`, `notB32Step_guard_false_frame` — DERIVED interpretation, never an assumption.
- PTX-NOT-THM-007 `notB32_executes_iff_guard_true` + 5 supporting `evalGuard` lemmas — guard classification with the explicit conditioned `hsources` well-formed-domain hypothesis (risk R-2) as approved.

No statement was weakened, no precondition was silently added or hardened, and no theorem name overstates its content.

## 4. Findings table (aggregated)

| ID | Severity | Origin | Location | Summary |
|----|----------|--------|----------|---------|
| F-1 | MINOR | semantics-critic v1 | SOURCE_FACT claim PTX-NOT-SEM1-015 | Interpretive tail "(32-bit width is therefore possible for .b32 registers)" inside a SOURCE_FACT statement; classification hygiene only, content accurate, acknowledged in interpretation_note; approved at Gate B with the finding documented; not state-affecting |
| F-2 | MINOR | theorem-strength critic v1 | PTX-NOT-THM-005 / PRF-3 | Bit-bucket theorem stated at general section 9.2 rule strength while scalar not.b32-specific applicability remains open (PTX-NOT-SEM1-067 / GAP-2); the human theorem-strength gate resolved the decision (approved keeping THM-005 at candidate strength); caveat R-3 retained in the proof file and traceable to final acceptance |
| N-1 | NOTE | architecture-critic v2 | foundation-v2 metadata | foundation-v1 line-count 271 vs 272 tool convention; cosmetic |
| N-2 | NOTE | architecture-critic v2 | run.json citation | as-of-write metadata; cosmetic |
| N-3 | NOTE | semantics-critic v1 | bundle `sha256` null | honest null with sha256_note; fragment-level hashes recorded; traceability intact |
| N-4 | NOTE | semantics-critic v1 | PDF page fields | HTML (primary) re-verified; PDF pages verified by curator, not re-checked here |
| N-5 | NOTE | semantics-critic v1 | bounded scope / DERIVED guard-false | Gate B reconfirmed the bounded scope (D-0c) and the DERIVED state-level reading of "do nothing" |
| N-6 | NOTE | lean-mapping-critic v1 | `PredId`/`predRegs : Option Bool` | Bool encoding of the 1-bit predicate domain (OQ-5) confirmed at Gate C |
| N-7 | NOTE | lean-mapping-critic v1 | `Destination.bitBucket` | Bit bucket modeled at general-rule strength with source still read when d = `_`; confirmed at Gate C |
| N-8 | NOTE | lean-mapping-critic v1 | file header | No theorems in mapping candidate; deferred by design; theorem-strength gate subsequently run |
| N-9 | NOTE | lean-mapping-critic v1 | version/target | Version/target modeled as validation metadata (VAL-5/VAL-6), not state behavior |
| N-10 | NOTE | theorem-strength critic v1 | PTX-NOT-THM-007 | `hsources` conditioned on `b = true` is a necessary, explicit, documented domain restriction (not hidden, not hardened); proof file retains it exactly |
| N-11 | NOTE | theorem-strength critic v1 | PTX-NOT-THM-003 | Existential conclusion is faithful to the semantic claim; direct post-state equality was optional and not required |
| N-12 | NOTE | theorem-strength critic v1 | PTX-NOT-VAL-002 / PRF-6 | PRF-6 disposition as VAL-style definitional check confirmed; avoids vacuous theorem |
| N-13 | NOTE | this final review | `runs/.../run.json` executions (15:26:35Z) | The final PROOF_GENERATION execution record shows outcome SUCCESS / nextStage FINAL_CRITIQUE, while its embedded SPEC2LEAN_RESULT line reads `"outcome":"RETRY","nextStage":"PROOF_GENERATION"`. The orchestrator's recorded transition (PROOF_GENERATION → FINAL_CRITIQUE) is authoritative and correct: all 16 theorem declarations are present and the artifact compiles. Stale embedded-protocol metadata only; no artifact impact |
| N-14 | NOTE | this final review | `candidates/.../lean/NotB32Probe.lean` | Resolved proof-engineer probe retained as a compiling stub (imports only NotB32; no semantics, theorems, or axioms); not part of the installed package; harmless |

**Counts: BLOCKER 0, MAJOR 0, MINOR 2, NOTE 14.**

## 5. Required final-review determinations

- **BLOCKER/MAJOR/MINOR/NOTE counts:** 0 BLOCKER, 0 MAJOR, 2 MINOR, 14 NOTE. Both MINOR findings originate in earlier phases and have already passed through the applicable human gates (Gate B for F-1; theorem-strength gate for F-2); neither is state-affecting and neither requires an artifact change before final approval.
- **Source-faithfulness status:** FAITHFUL. The complete evidence chain is intact: 33 official bundle fragments → 73 semantic claims (all referencing only PTX-9.3-NOT-001..033) → Gate-B-approved semantics → Gate-C-approved Lean mapping with 48 valid claim citations → approved theorem obligations → 16 compiled theorems. The two load-bearing official anchors were independently re-verified in this pass (not section 9.7.8.4, lines 14358-14388: `not.type d, a;`, `.type = { .pred, .b16, .b32, .b64 }`, `d = ~a;`, "Introduced in PTX ISA version 1.0.", "Supported on all target architectures.", `not.b32  mask,mask;`; false-guard clause 9.7.13.2, lines 21826-21853: "Threads with a False guard predicate do nothing.", Semantics "If {!}p then instruction"). No semantic drift, no phantom fragments, no invented error/UB behavior, zero ASSUMPTION-classified claims.
- **Unresolved state-affecting gaps:** NONE for the bounded base unit. Every open question (immediate source OQ-1/PTX-NOT-SEM1-066, bit-bucket applicability OQ-2/067, error/UB absence GAP-4/052-054, operand typing OQ-7/071, predicate encoding OQ-5/069, out-of-scope forms OQ-4/068, negative literal searches GAP-8/073) is non-state-affecting for the register-source `.b32` base semantics, is recorded as OPEN_QUESTION or honest DERIVED items, and is carried as deferred properties (PTX-NOT-DEF-001..008) with risks R-1..R-6. Partial execution for out-of-domain states (`Option none`) is a documented convention, never an invented error.
- **Theorem weakening status:** NONE. All 16 declarations match the human-approved obligation statements exactly. The only substitution is `not` → `Not` (definitionally identical propositional negation) in THM-002(d). The `hsources` hypothesis in THM-007 is the approved, explicit, necessary well-formed-domain restriction (risk R-2) — not a silent weakening. THM-005 is stated at the strength the human theorem-strength gate approved, with its caveat retained.
- **Proof bypass status:** NONE. No `sorry`, `admit`, new axioms, `unsafe`, or diagnostics suppression in any Lean artifact (only prose mentions in comments). Both the semantics and the proof files, the identical candidates, and the root package check cleanly (0 errors, 0 warnings).
- **Lean compilation status:** ALL GREEN. Installed semantics, installed proofs, candidate semantics, candidate proofs, neutralized probe stub, and the root `Spec2Lean.lean` package all compile with `lean_check_file` success, exit code 0, 0 errors, 0 warnings. The 11 executable semantics examples evaluate exactly to the expected results. Successful compilation establishes internal formal validity only; source faithfulness is established separately by the evidence chain above.
- **Readiness for explicit human final approval:** READY. The run is at the correct boundary (gates A/B/C/THEOREM_STRENGTH approved, FINAL pending; run.json `activeExecution` at FINAL_CRITIQUE with the expected artifact `final-critic-v1.md`). All artifacts are immutable revisions under `candidates/`; nothing has been promoted to `accepted/`; no gate has been self-approved. This review presents the material as ready for the human FINAL approval decision; it does not grant that approval.

## 6. Required-owner / human-review routing

- F-1 (MINOR, classification tail): Semantic Extractor only if a future semantic revision is ever produced; otherwise record as accepted-at-Gate-B. No action required before final approval.
- F-2 (MINOR, bit-bucket strength): human final reviewer to reconfirm that THM-005 at general-rule strength (caveat R-3, DEF-002) is the intended commitment; the decision was already made at the theorem-strength gate and the caveat remains traceable.
- N-13/N-14: orchestrator metadata / housekeeping notes; no owner required.
- No BLOCKER or MAJOR findings to route.

## 7. Critic independence statement

The critic did not edit, replace, or repair any reviewed artifact; no semantic claims, Lean definitions, theorem statements, or proofs were modified; no source evidence was fabricated; no gate was approved; nothing was promoted to `accepted/`. All Lean checks were read-only executions of the project's restricted tooling.
