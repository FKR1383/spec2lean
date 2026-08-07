# Final Independent Review v2 — PTX ISA 9.3 `add.u32` (post technical repair)

- **Unit:** first complete Spec2Lean formalization unit: PTX ISA 9.3 `add.u32`
- **Reviewer role:** Semantic Critic (independent; no artifact edits, no repair, no gate approval)
- **Review date:** 2026-08-07
- **Stage:** final independent semantic, Lean-mapping, theorem, proof, executable-example, and traceability critique, re-run after the technical repair requested by `add-u32-final-critic-v1.md` (F1/F2/F3)
- **Final verdict:** **READY_FOR_FINAL_HUMAN_APPROVAL**

---

## 1. Scope and inputs

This re-review verifies that the v1 blocking/major/minor findings are resolved and that the bounded formalization unit for PTX ISA 9.3 `add.u32` (scalar, base form only) satisfies every required review dimension. The v1 critique (`candidates/ptx/9.3/reviews/add-u32-final-critic-v1.md`) is the baseline; all v1 findings are re-checked against the current on-disk state.

Inputs reviewed in this pass:

1. Prior final critique: `candidates/ptx/9.3/reviews/add-u32-final-critic-v1.md` (v1, verdict CHANGES_REQUESTED, findings F1 MAJOR / F2 MINOR / F3-F5 NOTE)
2. Traceability closure: `reviews/ptx-add-u32/finalization/traceability-closure-v1.json`
3. Lean semantics (candidate): `candidates/ptx/9.3/lean/AddU32.lean`
4. Lean proofs (candidate): `candidates/ptx/9.3/lean/AddU32Proofs.lean`
5. Lean semantics (installed package): `lean/Spec2Lean/PTX/AddU32.lean`
6. Lean proofs (installed package): `lean/Spec2Lean/PTX/AddU32Proofs.lean`
7. Lean root and base: `lean/Spec2Lean.lean`, `lean/Spec2Lean/Basic.lean`
8. Governing context (re-used, unchanged): Gate A `…gate-a-v2.json`, Gate B `…gate-b-v2.json`, Gate C `…gate-c-v1.json`, theorem-strength `…theorem-strength-v1.json`, overflow assumption `…overflow-assumption-v1.json`, semantics `candidates/ptx/9.3/semantics/add-u32-v2.json`, obligations `candidates/ptx/9.3/theorems/add-u32-obligations-v1.json`, architecture `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md`, source bundles `add-u32-v1.json` + `add-u32-blockers-supplement-v2.json`, and prior critics (`add-u32-semantics-v2-critic.md`, `add-u32-lean-mapping-v1-critic.md`, `add-u32-obligations-v1-strength-critic.md`)
9. Official source HTML: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (sha `e2095c4a…`)

## 2. Missing-inputs report

No required input is missing. All semantic-critique inputs (bounded source bundle, exact evidence fragment IDs, semantic interpretation, approved language architecture), all Lean-mapping inputs (Lean definitions, semantic→Lean traceability), and all proof-critique inputs (theorem obligations, theorem statements, Lean-checked proofs) were present and reviewed. The installed package files were readable directly from `lean/`.

## 3. Repair verification (v1 findings)

### F1 — MAJOR (candidate `AddU32.lean` standalone compile failure) — **RESOLVED**

- v1 evidence: `lean_check_file candidates/ptx/9.3/lean/AddU32.lean` failed with 19 "has already been declared" errors, sha `e803a200…`, because line 43 was `import Spec2Lean`, which transitively imported the installed `Spec2Lean.PTX.AddU32` and collided with the candidate's own declarations.
- Current evidence: `lean_check_file candidates/ptx/9.3/lean/AddU32.lean` → **success, exit code 0, 0 errors, 0 warnings**, sha `9c1dd50a994401d971b1e4d6420af5814e5f0206e57c89a5f1850c39e8bafc54`, size 14356 B. Line 43 is now `import Spec2Lean.Basic`.
- The candidate file now compiles standalone. F1 is closed.

### F2 — MINOR (candidate sha not recorded in closure/gate records) — **RESOLVED**

- v1 evidence: the closure and gate records cited only the approved sha `4fa14a35…`; the on-disk candidate sha `e803a200…` was unrecorded.
- Current evidence: `reviews/ptx-add-u32/finalization/traceability-closure-v1.json` now contains a `final_lean_artifacts` section recording the current on-disk shas for all four unit artifacts (candidate/installed semantics `9c1dd50a…`; candidate/installed proofs `b2a0e076…`) with `byte_identical_to_candidate: true` for both installed files, and a `final_candidate_import_repair` section classifying the change as `TECHNICAL_IMPORT_REPAIR` with `semantic_change: false`, `theorem_change: false`, `status: CLOSED`. Byte-level provenance of the candidate file is now documented. F2 is closed.

### F3 — NOTE (installed package shas not recorded) — **RESOLVED**

- Current evidence: the closure records installed shas for both `lean/Spec2Lean/PTX/AddU32.lean` (`9c1dd50a…`) and `lean/Spec2Lean/PTX/AddU32Proofs.lean` (`b2a0e076…`) and asserts byte-identity with the candidate files. This critic independently confirmed byte-identity (see §5.2/§5.3). F3 is closed.

### F4 — NOTE (spot-check of negative-evidence caveat comments) — **VERIFIED**

- This pass read both files in full (340 lines and 273 lines). The WARNING headers (`AddU32.lean` lines 22–28, `AddU32Proofs.lean` lines 14–22), the destination-update negative-evidence caveat (`AddU32.lean` lines 209–219), and the THM-004 frame caveat (`AddU32Proofs.lean` lines 118–130) are present and correct. The caveat is also preserved in the closure record (SEM2-CRIT-F1/LMAP-CRIT-F1, `semantic_change: false`). A final human spot-check at the acceptance gate remains recommended as routine gate practice.

### F5 — NOTE (residual non-state-affecting open questions) — **CARRIED FORWARD**

- `candidates/ptx/9.3/semantics/add-u32-v2.json` status_rationale still states that no unsupported state-affecting machine-state behavior remains and that residual open questions (including PTX-ADD-SEM2-055..057) concern only non-state-affecting matters. The semantics artifact is unchanged from its Gate B sha (`76499344…`). No new gap was introduced by the repair.

## 4. Review dimensions

### 4.1 Source faithfulness and evidence traceability (re-spot-checked)
- Add clause: anchor `integer-arithmetic-instructions-add`, HTML line 8757, section 9.7.1.1 — "Add two values." / `add.type1 d, a, b; add{.sat}.type2 d, a, b;`. Confirmed.
- False-guard behavior: anchor `control-flow-instructions-at`, HTML line 21826, section 9.7.13.2, line 21839: "Threads with a `False` guard predicate do nothing." Confirmed.
- Aliasing/read-before-write shape: official example `add.u32 %r, %r, 4;` at HTML line 2902 (local state-space example). Confirmed (literal search `%r, %r, 4` resolves to line 2902).
- Overflow rule `d := (a + b) mod 2^32` remains traceable exclusively to human-approved project assumption PTX-ADD-SEM2-015 (`reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json`), never to NVIDIA prose. Attribution consistent across the assumption record, Gate B rationale, closure notes, semantics, and both Lean file headers.

### 4.2 Approved human-assumption attribution
Correct and unchanged. Modulo-2^32 is explicitly a HUMAN_APPROVED_ASSUMPTION in the semantics (`assumption_id: PTX-ADD-SEM2-015`, classification note: "never classified as SOURCE_FACT"), in the closure notes, and in the WARNING headers of both Lean files. Its decision-record sha (`d8a7b36e…`) is published in the closure (SEM2-CRIT-F2 / PTX-ADD-SEM2-058, CLOSED).

### 4.3 Semantic interpretation
`candidates/ptx/9.3/semantics/add-u32-v2.json` is unchanged (Gate B sha `76499344…`). Internally consistent; all residual OPEN_QUESTIONs non-state-affecting for legal bounded `add.u32` executions; matches Gate-B-approved interpretation. The repair did not touch this artifact.

### 4.4 Lean mapping
Candidate and installed semantics files are now byte-identical (`9c1dd50a…`, 14356 B) and both compile standalone with 0 errors / 0 warnings. The import chain is `Spec2Lean.Basic` (defines only `hello`; no collision) ← `Spec2Lean.PTX.AddU32` ← `Spec2Lean.PTX.AddU32Proofs`, with root `Spec2Lean.lean` importing all three and compiling 0 errors / 0 warnings. The Lean mapping matches the Gate-C-approved mapping content; the only delta from the Gate-C sha (`4fa14a35…`) is the comment-only negative-evidence caveat (SEM2-CRIT-F1/LMAP-CRIT-F1, `COMMENT_ONLY_TRACEABILITY_REPAIR`) plus the import-statement repair (`TECHNICAL_IMPORT_REPAIR`).

### 4.5 Executable behavior (re-run)
`lean_run_eval candidates/ptx/9.3/lean/AddU32.lean` → stdout exactly:
`12`, `0`, `some true`, `some true`, `some 100`, `some 1`, `some 5`, `some 12`, `"partial-none"`.
Identical to the v1 record on the installed file. Concrete results are consistent with the semantic model, including the modulo wrap (`0xFFFFFFFF + 1 = 0`), the guard-false no-op, the bit-bucket no-write, the `@!p` negation path, and the partial (missing source) `"partial-none"` case.

### 4.6 Theorem-statement strength
The six obligations (PTX-ADD-THM-001..006) plus the one human-approved aliasing corollary were approved at full strength in `ptx-add-u32-theorem-strength-v1.json` ("No semantic change, theorem weakening, or new precondition is authorized"). The proofs file is byte-identical to the v1-reviewed file (sha `b2a0e076…`, unchanged), so no theorem statement changed during the repair. The theorem names in the proofs file match the obligation `proposed_name`s exactly:
- THM-001 `execAddU32_total_on_well_formed_lookup_domain`
- THM-002 `execAddU32_result_conforms_modulo_with_read_before_write`
- THM-003 `execAddU32_guard_false_preserves_state`
- THM-004 `execAddU32_destination_only_frame`
- THM-005 `execAddU32_bit_bucket_preserves_state`
- THM-006 `execAddU32_executes_iff_guard_true`
- Corollary `execAddU32_alias_source_a_uses_pre_state_value`
All seven compile (0 errors / 0 warnings in both candidate and installed proofs files). No weakening, no unapproved new precondition.

### 4.7 Machine-checked proofs
`lean_check_file` results (all exit 0, 0 errors, 0 warnings):
- `candidates/ptx/9.3/lean/AddU32.lean` — PASS (sha `9c1dd50a…`)
- `candidates/ptx/9.3/lean/AddU32Proofs.lean` — PASS (sha `b2a0e076…`)
- `lean/Spec2Lean/PTX/AddU32.lean` — PASS (sha `9c1dd50a…`)
- `lean/Spec2Lean/PTX/AddU32Proofs.lean` — PASS (sha `b2a0e076…`)
- `lean/Spec2Lean.lean` — PASS (sha `ed9c671d…`)
Remaining Lean goals: 0 (Lean reports unclosed goals as errors; all files are error-free).

### 4.8 Absence of theorem weakening / circularity / vacuity / shortcuts
Grep across `lean/Spec2Lean` and `candidates/ptx/9.3/lean` for `sorry|admit|axiom|unsafe|#check|#print|set_option|by_contra|Classical` matches only the comment at line 27 of each proofs file stating that the file contains none. The proofs reference the executable semantics definitions, not the theorems being proved; no circularity or vacuity found. The non-vacuity arguments in the obligations record (e.g., THM-005 satisfiable-hypotheses argument) remain valid because the proofs file is byte-identical to the reviewed version.

### 4.9 Final residual risks
- All v1 findings F1–F3 are closed; F4 verified; F5 carried as documented non-state-affecting residual risk.
- NOTE N1 below: the root module sha (`ed9c671d…`) is not itself recorded in the closure record; the file is a trivial 3-line import module and this does not affect the bounded unit's soundness.
- Final human gate should spot-check the WARNING/caveat comment blocks (routine practice; contents verified present this pass).

### 4.10 Final traceability closure
`reviews/ptx-add-u32/finalization/traceability-closure-v1.json` is CLOSED_FOR_FINAL_REVIEW. It now records the current shas of all four unit Lean artifacts (candidate + installed semantics `9c1dd50a…`; candidate + installed proofs `b2a0e076…`) with byte-identity flags, the closed assumption-sha item, the closed comment-only caveat item, and the closed `TECHNICAL_IMPORT_REPAIR` item (`semantic_change: false`, `theorem_change: false`). The current on-disk shas match the recorded values exactly (verified independently by `lean_check_file`).

### 4.11 Consistency of installed Lean package with the reviewed bounded model
Verified: installed `AddU32.lean` ≡ candidate `AddU32.lean` (sha `9c1dd50a…`, byte-identical, 14356 B); installed `AddU32Proofs.lean` ≡ candidate `AddU32Proofs.lean` (sha `b2a0e076…`, byte-identical, 12009 B). Root module compiles. Package content matches the reviewed bounded model.

## 5. Findings (v2)

No BLOCKER, MAJOR, or MINOR findings remain.

### N1 — NOTE
- **Finding ID:** N1
- **Severity:** NOTE
- **Affected artifact:** `lean/Spec2Lean.lean` (sha `ed9c671d13736855f7362ea568e0d284cb6a7f6c1747f111beb15c226f0cdcd2`, 85 B)
- **Evidence references:** `lean_check_file lean/Spec2Lean.lean` → PASS 0/0; closure record `final_lean_artifacts` (records only the four AddU32 files)
- **Description:** The closure record does not publish the root module sha. The file contains only the three imports (`Spec2Lean.Basic`, `Spec2Lean.PTX.AddU32`, `Spec2Lean.PTX.AddU32Proofs`) and is trivially stable.
- **Consequence:** None for soundness or traceability of the bounded unit; minor completeness gap in the audit trail.
- **Required owner for revision:** none (optional record addition by Lean Formalizer for full auditability).
- **Human review required:** No.

### N2 — NOTE
- **Finding ID:** N2 (carried from v1 F5)
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/semantics/add-u32-v2.json`
- **Exact location:** status_rationale; OPEN_QUESTION entries PTX-ADD-SEM2-055..057 and related
- **Evidence references:** semantics v2 (Gate B sha `76499344…`); closure record
- **Description:** Residual open questions (immediate-range/encoding details, bit-bucket demo wording, absence-of-clause meaning, family-target phrasing, PDF page numbers, unpublished HTML sha) remain documented and are non-state-affecting for legal bounded `add.u32` executions.
- **Consequence:** None for the resulting machine state of legal bounded executions; documented residual risk.
- **Required owner for revision:** none.
- **Human review required:** No.

### N3 — NOTE
- **Finding ID:** N3 (carried from v1 F4)
- **Severity:** NOTE
- **Affected artifact:** `lean/Spec2Lean/PTX/AddU32.lean`, `lean/Spec2Lean/PTX/AddU32Proofs.lean` (and byte-identical candidates)
- **Exact location:** WARNING headers (lines 22–28 / 14–22) and negative-evidence caveat comments (lines 209–219 / 118–130, line 27)
- **Evidence references:** full-file reads this pass; closure SEM2-CRIT-F1/LMAP-CRIT-F1 CLOSED
- **Description:** The WARNING and caveat comment blocks are present and correct; verified line-by-line this pass. As a routine gate practice, a final human spot-check of these comment blocks is recommended at the acceptance gate.
- **Consequence:** None; verification only.
- **Required owner for revision:** none.
- **Human review required:** Yes (spot-check at final gate, routine).

## 6. Review questions

1. **F1 repaired?** Yes — candidate `AddU32.lean` compiles standalone (exit 0, 0/0) with `import Spec2Lean.Basic`.
2. **Candidate semantics standalone compilation?** Yes — `candidates/ptx/9.3/lean/AddU32.lean` 0 errors / 0 warnings.
3. **Candidate/package semantics byte-identical?** Yes — both sha `9c1dd50a…`, 14356 B.
4. **Candidate/package proofs byte-identical?** Yes — both sha `b2a0e076…`, 12009 B.
5. **Current artifact hashes recorded in closure?** Yes — `final_lean_artifacts` records all four shas with byte-identity flags; verified to match on-disk values.
6. **Import repair technical only?** Yes — classified `TECHNICAL_IMPORT_REPAIR`, `semantic_change: false`, `theorem_change: false`; delta is the single import line.
7. **Semantics changed by repair?** No — candidate now byte-identical to the previously verified installed semantics; eval output unchanged; semantics JSON untouched.
8. **Theorem changed or weakened?** No — proofs file byte-identical to v1 (sha unchanged); full-strength approval intact.
9. **All six approved theorems + aliasing corollary compile?** Yes — 0 errors / 0 warnings in candidate and installed proofs files.
10. **Remaining Lean goals?** 0 — all files compile error-free.
11. **No `sorry`/`admit`/axiom/`unsafe`?** Yes — grep matches only the comment stating their absence.
12. **Modulo-2^32 still explicit human-approved project assumption, never NVIDIA source fact?** Yes — WARNING headers, closure notes, semantics classification, assumption record.
13. **Unresolved state-affecting gap?** No — semantics status_rationale confirms none; no new gap introduced.
14. **Anything blocking final human acceptance?** No — all v1 findings closed; only NOTE-level residuals remain.

## 7. Final verdict

**READY_FOR_FINAL_HUMAN_APPROVAL**

Rationale: The technical repair requested by `add-u32-final-critic-v1.md` has been applied and independently verified. The candidate semantics file now compiles standalone; candidate and installed semantics and proofs files are byte-identical; the current SHA-256 values are recorded in the traceability closure; the import repair is technical-only with no semantic or theorem change; all six approved theorem obligations plus the aliasing corollary compile with zero Lean goals; no `sorry`/`admit`/axiom/`unsafe` exists; modulo-2^32 remains explicitly a human-approved project assumption and is never presented as an NVIDIA source fact; and no unresolved state-affecting semantic gap remains. The bounded formalization unit satisfies all required review dimensions and is ready for explicit human final acceptance.

This critic does **not** grant final acceptance and has not approved Gate A/B/C/D. Nothing has been promoted to `accepted/`.
