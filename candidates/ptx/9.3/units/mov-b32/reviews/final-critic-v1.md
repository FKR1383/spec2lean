# Independent Final Critique — mov-b32 (PTX ISA 9.3), run ptx-9.3-mov.b32-f910feea

## 1. Status

- Stage: FINAL_CRITIQUE (attempt 1, run revision 23). Required artifact: `candidates/ptx/9.3/units/mov-b32/reviews/final-critic-v1.md` (created as a new immutable revision; the path did not exist before this stage).
- This is the final independent aggregation critique of the bounded `mov.b32` formalization unit. It does not approve the FINAL gate and does not edit or repair any reviewed artifact.
- Run metadata consulted: `runs/ptx-9.3-mov.b32-f910feea/run.json` (unit `mov.b32`, gates A/B/C/THEOREM_STRENGTH approved, FINAL pending; PROOF_GENERATION completed by orchestrator-local-lean at 2026-08-07T15:40:34 with "All 16 approved theorem declarations are present and the proof artifact compiles cleanly with no prohibited verification bypass").
- Source identity: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines); PDF SHA-256 `769cc12e...`; manifest SHA-256 `622e6ce0...`. These were verified by the source-curator (SOURCE_CURATION) and the prior critics; no new raw-source research was performed in this aggregation review per final-review discipline.
- Review discipline: this is an aggregation review. The source facts, the guard-false source resolution, the Lean mapping, and the theorem-strength assessments were independently reviewed at their own stages (architecture-critic-v1, semantics-critic-v2, lean-mapping-critic-v1, theorem-strength-critic-v1) with no BLOCKERs or MAJORs. This final review re-verifies the end-to-end artifact chain and the installed Lean package only; official source evidence is revisited only where prior reviewed artifacts conflict or an unresolved state-affecting claim remains (none found).

## 2. Inputs reviewed

1. **Approved language architecture** — `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md` (Gate A approval `reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json`, decision `approved`).
2. **Bounded source bundle** — `candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v2.json` (38 fragments `PTX-9.3-MOV-001..038`; GAP-1 RESOLVED_BY_SUPPLEMENT; GAP-2..GAP-8 recorded).
3. **Approved semantic interpretation** — `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json` (interpretation_id `ptx-9.3-mov-b32-semantics-v2`; 76 claims: 35 SOURCE_FACT, 21 DERIVED_INTERPRETATION, 6 DESIGN_DEPENDENCY, 0 ASSUMPTION, 14 OPEN_QUESTION; Gate B approval `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-approval-v1.json`, decision `approved`, artifact SHA-256 `904e10e1...`).
4. **Lean mapping (candidate)** — `candidates/ptx/9.3/units/mov-b32/lean/MovB32-v1.lean` (Gate C approval `reviews/ptx-mov-b32/gate-c/ptx-mov-b32-c-approval-v1.json`, decision `approved`, artifact SHA-256 `c1ddad16...`).
5. **Theorem obligations** — `candidates/ptx/9.3/units/mov-b32/theorems/obligations-v1.json` (obligation_set_id `ptx-9.3-mov-b32-obligations-v1`; theorem-strength approval `reviews/ptx-mov-b32/theorem-strength/ptx-mov-b32-theorem-strength-approval-v1.json`, decision `approved`, artifact SHA-256 `23611715...`).
6. **Installed Lean semantics** — `lean/Spec2Lean/PTX/MovB32.lean` (389 lines, SHA-256 `ca07f24001588da4bbb092cde6526e607f5bcbfa4e37a65b344610eceb29b097`, 17,234 bytes).
7. **Installed Lean proofs** — `lean/Spec2Lean/PTX/MovB32Proofs.lean` (282 lines, SHA-256 `654f8b1753f69114d3f1899edff9dcddfaba6ee50a17fac09331b755aaf9d288`, 8,757 bytes).
8. **Candidate proof artifact** — `candidates/ptx/9.3/units/mov-b32/lean/MovB32Proofs-v1.lean` (byte-identical to the installed proofs file: same SHA-256 `654f8b17...`; read in full and cross-checked).
9. **Prior critiques** — `architecture-critic-v1.md`, `semantics-critic-v1.md`, `semantics-critic-v2.md`, `lean-mapping-critic-v1.md`, `theorem-strength-critic-v1.md`.
10. **Human gate records** — Gate A approved; Gate B rejected then approved (rejection directive implemented via v2 bundle); Gate C approved; theorem-strength approved; FINAL pending.
11. **Root Lean package** — `lean/Spec2Lean.lean` (imports Basic, AddU32, AddU32Proofs, MovB32, MovB32Proofs), `lean/lakefile.toml` (`name = "Spec2Lean"`), `lean/lean-toolchain`, `lean/lake-manifest.json` all present.

## 3. Independent Lean verification performed in this final review

The following were executed with the restricted Lean tools on the installed package artifacts:

| Check | Tool | Result |
|---|---|---|
| `lean/Spec2Lean/PTX/MovB32.lean` compiles | `lean_check_file` | SUCCESS, exit 0, 0 errors, 0 warnings |
| `lean/Spec2Lean/PTX/MovB32Proofs.lean` compiles | `lean_check_file` | SUCCESS, exit 0, 0 errors, 0 warnings |
| `lean/Spec2Lean/PTX/MovB32Proofs.lean` diagnostics | `lean_get_diagnostics` | 0 errors, 0 warnings, 0 information |
| Root package entry `lean/Spec2Lean.lean` (transitively imports all five modules) | `lean_check_file` | SUCCESS, exit 0, 0 errors, 0 warnings |
| Executable examples in packaged semantics | `lean_run_eval` | 9 outputs, all matching expected values: `3735928559` (0xDEADBEEF copy), `some true` (unguarded), `some true` (@!p with p=false), `some 100` (destination update), `some 1` (bit bucket: no write), `some 5` (guard-false: unchanged), `some 7` (@!p imm copy), `some 5` (aliasing self-copy), `"partial-none"` (partial execution) |
| Prohibited tokens in mov.b32 files | grep scan | Only comment/string occurrences of `sorry`, `admit`, `axiom`, `unsafe`, `partial`, `opaque`; no declarations |

Theorem-declaration audit: `lean/Spec2Lean/PTX/MovB32Proofs.lean` contains exactly 16 `theorem` declarations, matching the run-history claim and the approved obligation set:
- THM-001: `movB32Step_deterministic` (1)
- THM-002: `exec_sound_executed`, `exec_sound_guardFalse`, `step_complete`, `step_partial_complete` (4, emitted as four separate theorems per theorem-strength-critic F-2)
- THM-003: `execMovB32_copy_fidelity` (1)
- THM-004: `movB32Step_destination_only_frame` (1)
- THM-005: `movB32Step_bit_bucket_preserves_state` (1)
- THM-006: `execMovB32_guard_false_preserves_state`, `movB32Step_guard_false_frame` (2)
- THM-007: `movB32_executes_iff_guard_true` + 5 per-constructor `evalGuard` lemmas (6)

Each theorem statement in the installed proofs was compared statement-by-statement with the approved `lean_statement_sketch` in `obligations-v1.json`: hypotheses and conclusions match exactly; no hypothesis was added or dropped; no conclusion was weakened; the `hsources` hypothesis of THM-007 remains conditional (`b = true -> Exists ...`), preserving the theorem-strength critic's F-4 directive; THM-005 carries the AMB-3 / general-section-9.2 strength caveat at the statement level (comment at proof-file lines 189-194), implementing theorem-strength-critic F-1.

Namespace/statement pinning (theorem-strength-critic F-2): the installed semantics file wraps the Gate-C-approved declarations in an additional `namespace MovB32` (`Spec2Lean.PTX.MovB32`), and the proofs file opens `Spec2Lean.PTX.MovB32`, so all unqualified identifiers (`MachineState`, `MovB32Step`, `execMovB32`, ...) resolve. I read both the candidate (`MovB32-v1.lean`, 387 lines) and the installed semantics (`MovB32.lean`, 389 lines) in full: the declaration bodies are identical; the only difference is the added `namespace MovB32` / `end MovB32` wrapper. No semantic content changed; eval outputs are identical. The candidate artifact was not overwritten or modified.

## 4. Findings table (final-review findings, including carried items)

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| FC-1 | MINOR | semantics-v2 claims PTX-MOV-SEM2-070..075 (SOURCE_FACT statements) | Carried from semantics-critic-v2 F-1: interpretive/derivation tails remain embedded in the statements of the six new SOURCE_FACT claims (e.g., SEM2-072 "by the general predicability rule it is the applicable evidence for predicated instructions including mov.b32"). Content is accurate and the same conclusions exist at the correct DERIVED level (SEM2-034/038/076); classification-hygiene only. Non-blocking; no Lean impact |
| FC-2 | MINOR | semantics-v2 claims PTX-MOV-SEM2-034/038 (`confidence: high`) | Carried from semantics-critic-v2 F-2: confidence calibration slightly optimistic for a DERIVED claim containing an acknowledged interpretive step ("no state component changes" is the state-level reading of "do nothing"). Claim text is transparent; risk contained. Non-blocking |
| FC-3 | NOTE | installed `lean/Spec2Lean/PTX/MovB32.lean` vs Gate-C candidate | The installed semantics is the Gate-C-approved candidate wrapped in an added `namespace MovB32`; bodies byte-identical, eval identical. This implements theorem-strength-critic F-2 (namespace pinning) and does not change semantics. The Gate-C-approved candidate remains immutable under `candidates/` |
| FC-4 | NOTE | semantics-v2 `source_bundle_references[0].sha256` (null) | Carried from semantics-critic-v2 F-3: bundle-level SHA-256 honestly null; fragment-level and source-document hashes recorded. Traceability soft spot only |
| FC-5 | NOTE | `documents/sources/nvidia/ptx/9.3/source-manifest.json` vs run metadata | Carried from architecture-critic-v1 F-4: manifest `initial_formalization_unit` records `add.u32` while the run unit is `mov.b32`; handled as project metadata, not evidence. Orchestrator-level reconciliation recommended; no semantic impact |
| FC-6 | NOTE | architecture D-0c / SEM2-004/-013 / AMB-2 | Carried from architecture-critic F-5 and semantics-critic-v2 F-5: the bounded base unit covers only register/immediate sources of scalar `mov.b32`, a proper subset of the official form (`sreg`, `avar`, `avar+imm`, `fname`, `kernel` out of scope). Human-confirmed at Gate A and reconfirmed at Gate B; retained for FINAL reviewer awareness |
| FC-7 | NOTE | obligations-v1 `PTX-MOV-VAL-002` (PRF-6 disposition) | PRF-6 result-domain membership is adopted as a VAL-style definitional well-formedness obligation under the typed register-file representation (B32 wraps `Fin 2^32`), per the recorded disposition in semantics-v2; not a semantic theorem. Non-vacuity of the theorem set is preserved |
| FC-8 | NOTE | proof-file THM-005 caveat comment (lines 189-194) | lean-mapping-critic F-1 (bit-bucket at candidate strength) is resolved-with-caveat: the statement-level AMB-3 caveat required by theorem-strength-critic F-1 is now carried directly above the theorem |

Counts: **BLOCKER 0, MAJOR 0, MINOR 2 (both carried, non-blocking), NOTE 6.**

## 5. Source-faithfulness status

**FAITHFUL to the approved bounded semantics, with all state-affecting claims source-anchored or honestly derived.** The semantics-v2 interpretation (Gate-B-approved) contains 76 claims referencing only bundle fragment IDs `PTX-9.3-MOV-001..038`; zero ASSUMPTION-classified claims remain. The state-affecting commitments are:

- Copy rule `d = a;` — SOURCE_FACT SEM2-035 (mov Semantics first line, fragment MOV-006) plus DERIVED copy interpretation SEM2-036. Implemented as `copyValue v := v` (identity), with no arithmetic/truncation.
- Guard-false no-op — DERIVED_INTERPRETATION SEM2-034/038, source-resolved per the Human Gate B rejection via the official section 9.7.13.2 clause "Threads with a False guard predicate do nothing." (fragments MOV-035/036; SOURCE_FACT SEM2-072/073; derivation chain SEM2-076). It is never presented as a per-instruction SOURCE_FACT or as a human assumption.
- Destination-only write and read-before-write aliasing — DERIVED SEM2-032/033/062, consistent with the copy rule and the minimal state design SEM2-058.
- Determinism — DERIVED SEM2-039 with explicit GAP-2 non-statement note, realized non-vacuously as relational determinism over `MovB32Step` (THM-001).
- No error/trap/UB invented — partial-execution convention (`none` = out-of-domain partiality, SEM2-041/042/043), precisely characterized by THM-002(d).

The prior critics independently re-verified all load-bearing source anchors verbatim against the official HTML (scalar mov section 9.7.9.3 at anchor `data-movement-and-conversion-instructions-mov` incl. `d = a;` at line 15039; general predication section 9.7.13.2 at anchor `control-flow-instructions-at` incl. the do-nothing clause at lines 21838-21839; `.b32` "Bits (untyped)" Table 8; register state space; predicated-execution section 9.3; vector mov 9.7.9.4 as out-of-scope). This final review found no conflict between any prior reviewed artifact and the official evidence, and no unresolved state-affecting semantic claim requiring new source research. Lean compilation success is noted as necessary but not sufficient for source faithfulness; the faithfulness judgment rests on the approved claim-by-claim mapping and the prior verbatim source re-verifications.

## 6. Unresolved state-affecting gaps

**None blocking for the bounded unit.** All state-affecting behavior for the approved bounded domain is source-anchored or derived with explicit chains (Section 5). The recorded open questions are non-state-affecting for the bounded base form or are handled by explicit conventions:
- Scalar base form target set (GAP-7 / SEM2-046 / AMB-6): metadata completeness, not execution behavior; deferred (DEF-004).
- Scalar mov.b32-specific bit-bucket demonstration (GAP-6 / SEM2-047 / AMB-3): THM-005 is stated and caveated at general section 9.2 strength; deferred strengthening (DEF-002).
- Constant-immediate range/encoding (GAP-5 / SEM2-048 / AMB-4): static well-formedness only; deferred (DEF-003).
- Error/UB/implementation-defined absence (GAP-3 / SEM2-041/042 / AMB-5): absence recorded as OPEN_QUESTION, never asserted as positive fact; partial-execution convention covers out-of-domain behavior (DEF-005/DEF-006).
- Out-of-scope source categories and vector form (GAP-8, AMB-1/AMB-2): outside the human-approved bounded scope (DEF-007 etc.).

## 7. Theorem-weakening status

**No weakening found.** All 16 theorem statements in the installed proofs match the approved obligation sketches exactly (Section 3): hypotheses and conclusions are identical, no unapproved preconditions were added (THM-007's `hsources` remains conditional), and no vacuous or circular statements were introduced. Relational determinism is stated over the Prop-valued `MovB32Step` (not trivial function single-valuedness). THM-005 retains the AMB-3 strength caveat at the statement level. Non-vacuity was established at the theorem-strength stage (all hypotheses satisfiable) and re-confirmed by the executable examples. No theorem name overstates its statement; no conclusion is stronger than the model/evidence supports without a retained caveat.

## 8. Proof-bypass status

**No proof bypass.** No `sorry`, `admit`, `axiom`, `unsafe`, `partial`, or `opaque` declarations exist in the installed semantics or proofs (grep hits are documentation comments/strings only). The proofs are genuine case-analysis/rewrite/simp proofs that compile with 0 errors and 0 warnings; no new axioms or unsafe shortcuts were introduced; no set_option diagnostics suppression was found. The `Spec2Lean.Basic` import in the semantics is a placeholder with no axioms or hidden trust (previously noted by lean-mapping-critic F-6).

## 9. Lean compilation status

**COMPILES — 0 errors / 0 warnings** for all checked targets:
- `lean/Spec2Lean/PTX/MovB32.lean` (lean_check_file: success, exit 0, 0/0)
- `lean/Spec2Lean/PTX/MovB32Proofs.lean` (lean_check_file: success, exit 0, 0/0; lean_get_diagnostics: 0/0/0)
- Root entry `lean/Spec2Lean.lean` (lean_check_file: success, exit 0, 0/0; this transitively compiles the full installed package through `lake env lean`)
- Executable examples evaluate to the exact 9 expected outputs (Section 3).

A full `lake build` was not re-run by this critic (no shell tool in the critic toolset); the per-file `lake env lean` checks of the root module and both mov.b32 modules provide the package-level compilation evidence available in this environment. Compilation is treated as internal formal validity only, not source faithfulness.

## 10. Readiness for explicit human final approval

**READY for presentation to Human FINAL approval. The FINAL gate is NOT approved by this review.**

The end-to-end chain is complete and consistent: Gate-A-approved architecture → Gate-B-approved semantics-v2 (guard-false source-resolved; zero assumptions) → Gate-C-approved Lean mapping → theorem-strength-approved obligation set → machine-checked proofs (16 theorems) → installed package compiling with 0 errors/0 warnings and matching executable behavior. Prior critiques found no BLOCKER or MAJOR at any stage; the two carried MINOR findings (FC-1 classification tails, FC-2 confidence calibration) are non-blocking hygiene/annotation items, and the six NOTE observations document honest limitations and reconfirmation points for the human reviewer. No theorem weakening, no proof bypass, no semantic invention, no sorry/admit/axiom/unsafe, no promotion to `accepted/`. The human FINAL reviewer should specifically reconfirm the bounded scope (register/immediate sources only) and the DERIVED (not per-instruction SOURCE_FACT) status of the guard-false consequence, which are the two decisions this critique carries forward as the correct reading of the evidence.

## 11. Critic independence statement

The critic did not edit, repair, or replace any reviewed artifact: no semantic claims, Lean definitions, theorem statements, or proofs were rewritten; no source evidence was fabricated; no gate was approved; nothing was promoted to `accepted/`. The installed Lean files and the candidate artifacts were read and verified as-is.
