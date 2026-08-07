# Final Independent Review — PTX ISA 9.3 `add.u32`

- **Unit:** first complete Spec2Lean formalization unit: PTX ISA 9.3 `add.u32`
- **Reviewer role:** Semantic Critic (independent; no artifact edits, no repair, no gate approval)
- **Review date:** 2026-08-07
- **Stage:** final independent semantic, Lean-mapping, theorem, proof, executable-example, and traceability critique (post Gate A/B/C, post theorem-strength approval, post traceability cleanup)
- **Final verdict:** **CHANGES_REQUESTED**

---

## 1. Scope and inputs

This critique reviews the bounded formalization unit for PTX ISA 9.3 `add.u32` (scalar, base form only; `sat` and packed `.u16x2/.u8x4` forms out of scope per the approved bounded model).

Inputs reviewed:

1. Official source manifest: `documents/sources/nvidia/ptx/9.3/source-manifest.json`
2. Bounded source bundles: `candidates/ptx/9.3/source-bundles/add-u32-v1.json`, `candidates/ptx/9.3/source-bundles/add-u32-blockers-supplement-v2.json`
3. Official HTML evidence: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (sha `e2095c4a…`)
4. Approved language architecture: `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md` (sha `3857b9cb…`)
5. Semantic interpretation: `candidates/ptx/9.3/semantics/add-u32-v2.json` (sha `76499344…`)
6. Human-approved assumption records: `reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json`; gate records `reviews/ptx-add-u32/gate-a/…v2.json`, `gate-b/…v2.json`, `gate-c/…v1.json`, `theorem-strength/…v1.json`, `finalization/traceability-closure-v1.json`
7. Lean definitions (candidate): `candidates/ptx/9.3/lean/AddU32.lean`, `candidates/ptx/9.3/lean/AddU32Proofs.lean`
8. Lean definitions (installed package): `lean/Spec2Lean/PTX/AddU32.lean`, `lean/Spec2Lean/PTX/AddU32Proofs.lean`, `lean/Spec2Lean.lean`, `lean/Spec2Lean/Basic.lean`
9. Theorem obligations: `candidates/ptx/9.3/theorems/add-u32-obligations-v1.json` (sha `411cdd55…`)
10. Lean-checked proofs: `lean/Spec2Lean/PTX/AddU32Proofs.lean` (compiles, 0 errors / 0 warnings)
11. Prior reviews: `candidates/ptx/9.3/reviews/add-u32-semantics-v2-critic.md`, `add-u32-lean-mapping-v1-critic.md`, `add-u32-obligations-v1-strength-critic.md`

## 2. Missing-inputs report

No required input is missing. All five inputs for a semantic-interpretation critique (bounded source bundle, exact evidence fragment IDs, semantic interpretation candidate, approved language architecture), all additional Lean-mapping inputs (Lean definitions, semantic→Lean traceability), and all proof-critique inputs (theorem obligations, theorem statements, Lean-checked proofs) were present and reviewed.

## 3. Review dimensions

### 3.1 Source faithfulness and evidence traceability
- The base scalar `add.u32` clause is grounded in HTML 9.7.1.1 (anchor `integer-arithmetic-instructions-add`, HTML line 8757): "Performs addition and writes the resulting value into a destination register," with `.type2` = `{.u32, .u16x2, .u8x4, .s32, .s16x2, .s8x4}` bounding the unit to the `.u32` member.
- False-guard behavior is source-grounded: HTML 9.7.13.2 (anchor `control-flow-instructions-at`, line 21826/21839): "Threads with a False guard predicate do nothing," corroborated by 9.3 predicated execution (anchor `predicated-execution`, line 7537).
- Register-reuse/aliasing is grounded in the official example `add.u32 %r, %r, 4` (HTML line 2902), supporting the read-before-write aliasing corollary.
- Overflow behavior `d := (a + b) mod 2^32` is traceable to the human-approved project assumption PTX-ADD-SEM2-015, **not** to NVIDIA prose. This attribution is consistent across the assumption record, Gate B rationale, and both Lean file headers.

### 3.2 Approved human-assumption attribution
Correct. The modulo-2^32 rule is explicitly marked as a human-approved project assumption with its own review record and published SHA-256 (`d8a7b36e45c027e9783f22810661debd649ef3dd765d9fcdaccca6ae8b6c1acf`), closed under SEM2-CRIT-F2/PTX-ADD-SEM2-058 in the traceability closure. No NVIDIA source claim is made for overflow.

### 3.3 Semantic interpretation
The semantics `candidates/ptx/9.3/semantics/add-u32-v2.json` are internally consistent, state that all residual OPEN_QUESTIONs (e.g., PTX-ADD-SEM2-055..057) are non-state-affecting for legal bounded `add.u32` executions, and match the Gate-B-approved interpretation. Semantic claims carry evidence IDs traceable to the bundle.

### 3.4 Lean mapping
The installed package maps the semantic model to `lean/Spec2Lean/PTX/AddU32.lean` (register file + predicate file minimal `MachineState`, partial source-operand lookup, destination write) and compiles cleanly (0 errors / 0 warnings). **However**, the candidate artifact `candidates/ptx/9.3/lean/AddU32.lean` on disk does **not** compile standalone (see finding F1). This is a Lean-mapping artifact integrity defect, not a semantic drift.

### 3.5 Executable behavior
`lean_run_eval` on the installed `AddU32.lean` produced: `12`, `0`, `some true`, `some true`, `some 100`, `some 1`, `some 5`, `some 12`, `"partial-none"` — concrete results consistent with the semantic model, including the partial (nonexistent-source) case.

### 3.6 Theorem-statement strength
The six theorem obligations (PTX-ADD-THM-001..006) were approved at full strength in `reviews/ptx-add-u32/theorem-strength/ptx-add-u32-theorem-strength-v1.json`; no weakening was authorized or found. The aliasing corollary `execAddU32_alias_source_a_uses_pre_state_value` is proved in the proofs file and is grounded in the official `%r, %r, 4` example plus the already-approved modulo assumption.

### 3.7 Machine-checked proofs
`lean/Spec2Lean/PTX/AddU32Proofs.lean` and `lean/Spec2Lean.lean` both compile with 0 errors / 0 warnings. Remaining goal count is 0.

### 3.8 Absence of theorem weakening / circularity / vacuity
No weakening, circularity, or vacuous claims found. Grep across `lean/Spec2Lean` for `sorry|admit|axiom|unsafe|#check|#print|set_option|by_contra|Classical` matched only a comment in AddU32Proofs.lean line 27 stating the file contains none. Proofs reference concrete executable semantics, not the theorems being proved.

### 3.9 Final residual risks
- The candidate `AddU32.lean` import defect (F1) is the only blocking-class residual issue; it is technical, not semantic.
- The exact text of the negative-evidence caveat was confirmed through the closure record and the WARNING header in the installed file; a final human spot-check of the comment block is recommended at the acceptance gate.

### 3.10 Final traceability closure
`reviews/ptx-add-u32/finalization/traceability-closure-v1.json` is CLOSED_FOR_FINAL_REVIEW. SEM2-CRIT-F2/PTX-ADD-SEM2-058 (assumption SHA published) and SEM2-CRIT-F1/LMAP-CRIT-F1 (comment-only traceability repair, `semantic_change=false`) are CLOSED. The closure does **not** reference the current on-disk candidate sha `e803a200…` (see finding F2).

### 3.11 Consistency of installed Lean package with the reviewed bounded model
The installed package is internally consistent and compiles as a whole. Its `AddU32Proofs.lean` sha `b2a0e076…` is byte-identical to the candidate proofs file, and the installed `AddU32.lean` differs from the candidate only in the import statement (`import Spec2Lean.Basic` vs candidate `import Spec2Lean`). The installed sha `9c1dd50a…` is not itself published in any gate/traceability record (see F3).

---

## 4. Findings

### F1 — MAJOR
- **Finding ID:** F1
- **Severity:** MAJOR
- **Affected artifact:** `candidates/ptx/9.3/lean/AddU32.lean`
- **Exact location:** line 43 (`import Spec2Lean`); consequence errors begin line 53 col 4 (`Spec2Lean.PTX.u32Bits` has already been declared)
- **Evidence references:**
  - `lean_check_file candidates/ptx/9.3/lean/AddU32.lean` → FAILED, exit 1, 19 errors, sha `e803a2005b5a15cddebf616b64831a4ee7355bec357496fec89e2633f1f978e1`, size 14350 B
  - `lean_get_diagnostics candidates/ptx/9.3/lean/AddU32.lean` → 19 "has already been declared" errors
  - Contrast: `lean_check_file lean/Spec2Lean/PTX/AddU32.lean` → PASSED, 0 errors / 0 warnings, sha `9c1dd50a994401d971b1e4d6420af5814e5f0206e57c89a5f1850c39e8bafc54`, line 43 is `import Spec2Lean.Basic`
- **Description:** The candidate semantics file imports the root `Spec2Lean` module, which transitively imports the installed `Spec2Lean.PTX.AddU32`; the candidate's own declarations then collide with the installed ones, producing 19 duplicate-declaration errors on a standalone check. The installed package file, importing `Spec2Lean.Basic`, compiles cleanly. The on-disk candidate sha `e803a200…` also differs from the Gate-C/theorem-strength-approved sha `4fa14a35f4d127b4df6cd10eb541bf6a4503042c6dc306290e4258f90c691b7b`.
- **Consequence:** The reviewed candidate artifact does not satisfy "successful Lean semantics compilation" as it stands; a promotion of the candidate as-is would install a file that fails standalone checking. The semantic content itself is unaffected and the installed package is sound.
- **Required owner for revision:** Repair Agent (technical Lean failure; route per workflow).
- **Human review required:** Yes — after repair, re-run this critique and require explicit human final acceptance.

### F2 — MINOR
- **Finding ID:** F2
- **Severity:** MINOR
- **Affected artifact:** `reviews/ptx-add-u32/finalization/traceability-closure-v1.json` and the gate records
- **Exact location:** closed items SEM2-CRIT-F1/LMAP-CRIT-F1 and SEM2-CRIT-F2/PTX-ADD-SEM2-058
- **Evidence references:** traceability closure (status CLOSED_FOR_FINAL_REVIEW); grep for `4fa14a35` in gate-c, theorem-strength, obligations, and both prior critics; absence of any record referencing `e803a200…`
- **Description:** The closure claims a comment-only traceability repair (`semantic_change=false`) for the candidate `AddU32.lean`, but the current on-disk sha `e803a200…` is not referenced by any gate/traceability record, and the record set still cites `4fa14a35…`. The import-statement difference between the candidate (`import Spec2Lean`) and the installed file (`import Spec2Lean.Basic`) is not accounted for in the closure.
- **Consequence:** Byte-level provenance of the promoted candidate file is not documented; an auditor cannot determine from records alone which sha was approved.
- **Required owner for revision:** Repair Agent (with Lean Formalizer sign-off on the import fix); Source Curator not involved (no source evidence change).
- **Human review required:** Yes — include the updated sha in the final acceptance gate material.

### F3 — NOTE
- **Finding ID:** F3
- **Severity:** NOTE
- **Affected artifact:** traceability records for the installed package
- **Exact location:** `lean/Spec2Lean/PTX/AddU32.lean` (sha `9c1dd50a…`) and `lean/Spec2Lean/PTX/AddU32Proofs.lean` (sha `b2a0e076…`)
- **Evidence references:** sha comparison of candidate vs installed files; `candidate_diff` unavailable for `lean/` paths (tool restriction to `candidates/`/`accepted/`)
- **Description:** The installed package's `AddU32.lean` sha is not published in any gate/traceability record; only the candidate path shas are cited. The proofs file sha is identical across candidate and installed, and the two `AddU32.lean` files differ only in the import statement, but this equivalence is not recorded.
- **Consequence:** The required review dimension "consistency of installed Lean package with the reviewed bounded model" is verifiable now but not auditable from records alone after the fact.
- **Required owner for revision:** Lean Formalizer (record installed shas) — no semantic change.
- **Human review required:** No (record-keeping only; include in final gate material).

### F4 — NOTE
- **Finding ID:** F4
- **Severity:** NOTE
- **Affected artifact:** `lean/Spec2Lean/PTX/AddU32.lean` and `lean/Spec2Lean/PTX/AddU32Proofs.lean`
- **Exact location:** header WARNING blocks and negative-evidence caveat comments
- **Evidence references:** traceability closure (LMAP-CRIT-F1 CLOSED, COMMENT_ONLY_TRACEABILITY_REPAIR); file headers; grep results showing no prohibited constructs (only the line-27 comment in the proofs file mentioning their absence)
- **Description:** The negative-evidence caveat closure is attested by the record and the WARNING headers are present in both installed files; the full comment text was not re-inspected line-by-line in this final pass (reads were bounded/truncated).
- **Consequence:** No impact on soundness; recommend a final human spot-check of the comment blocks at the acceptance gate for completeness.
- **Required owner for revision:** none (verification only).
- **Human review required:** Yes (spot-check at final gate).

### F5 — NOTE
- **Finding ID:** F5
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/semantics/add-u32-v2.json`
- **Exact location:** status_rationale and OPEN_QUESTION entries PTX-ADD-SEM2-055..057
- **Evidence references:** semantics v2 (sha `76499344…`); Gate B record
- **Description:** Residual open questions (immediate-range/encoding details, bit-bucket demo wording, absence-of-clause meaning, family-target phrasing, PDF page numbers, unpublished HTML sha) are all non-state-affecting for the legal bounded `add.u32` executions covered by this unit.
- **Consequence:** None for the resulting machine state of legal bounded executions; documented as residual risk.
- **Required owner for revision:** none.
- **Human review required:** No.

---

## 5. Review questions

1. **Bounded to base scalar `add.u32`?** Yes — bundles and semantics bound the unit; syntax evidence (`add.type1 {.u16,.u64,.s16,.s64}`, `add{.sat}.type2 {.u32,...}`) confines the model to `.u32`; `sat`/packed forms explicitly out of scope.
2. **Semantic claims traceable?** Yes — claims carry evidence fragment IDs; critical claims (add semantics, false guard, aliasing) verified directly against HTML anchors.
3. **Mod 2^32 never presented as NVIDIA fact?** Yes — human-approved project assumption, WARNING headers, assumption record, Gate B rationale.
4. **False-guard behavior source-grounded?** Yes — HTML 9.7.13.2 line 21839 "Threads with a False guard predicate do nothing"; 9.3 predication line 7537.
5. **Lean model implements Gate-B semantics?** Yes for the installed file (compiles 0/0, eval matches model); the on-disk candidate file is inconsistent (F1).
6. **Six obligations proved at approved strength?** Yes — proofs file compiles 0/0; PTX-ADD-THM-001..006 present; no weakening found.
7. **Aliasing corollary proved without new assumptions?** Yes — `execAddU32_alias_source_a_uses_pre_state_value` compiles; grounded in official `%r, %r, 4` example and the already-approved modulo assumption.
8. **Destination-only/frame reasoning bounded?** Yes — minimal `MachineState` (register file + predicate file) in `AddU32.lean`; mapping critic confirms; negative-evidence caveat preserved.
9. **Negative-evidence caveat preserved?** Yes — closure CLOSED with `semantic_change=false`; WARNING header present (F4).
10. **Assumption SHA-256 recorded?** Yes — `d8a7b36e45c027e9783f22810661debd649ef3dd765d9fcdaccca6ae8b6c1acf` in closure record.
11. **No `sorry`/`admit`/axiom/`unsafe`?** Yes — grep across `lean/Spec2Lean` found only the comment mentioning their absence.
12. **Remaining Lean goals?** 0 — installed files and root module compile 0 errors / 0 warnings.
13. **Executable examples demonstrative?** Yes — eval output shows concrete results including the partial-lookup `"partial-none"` case.
14. **Theorem weakening during repair?** No — theorem-strength decision approved full strength; no repair weakened it.
15. **New semantic precondition added during repair?** No — no unapproved precondition introduced.
16. **Proof files compile independently?** Installed: yes (`AddU32.lean` 0/0, `AddU32Proofs.lean` 0/0). Candidate proofs: yes (sha `b2a0e076…`, compiles). Candidate `AddU32.lean`: **no** (F1).
17. **Full package consistent?** Yes — root `lean/Spec2Lean.lean` compiles 0 errors; import chain `Basic → PTX.AddU32 → PTX.AddU32Proofs` sound.
18. **Unresolved state-affecting gap?** No — all residual open questions are non-state-affecting for legal bounded executions.
19. **Anything blocking human final acceptance?** Yes — F1 (candidate `AddU32.lean` standalone compile failure and unrecorded sha drift) must be repaired and re-verified before final human approval; F2 requires record refresh.

---

## 6. Final verdict

**CHANGES_REQUESTED**

Rationale: The semantic interpretation, Lean mapping content, theorem statements, machine-checked proofs, and traceability closure are sound and human-approvable in substance; no source-faithfulness, weakening, circularity, vacuity, or prohibited-shortcut problem exists. However, the review target artifact `candidates/ptx/9.3/lean/AddU32.lean` on disk fails standalone Lean checking (19 duplicate-declaration errors) and its sha (`e803a200…`) is not covered by any gate/traceability record (approved sha was `4fa14a35…`). Per the review dimensions, "successful Lean semantics compilation" and "consistency of installed Lean package with the reviewed bounded model" are not both satisfied for the candidate artifact. This is a technical Lean failure routed to the Repair Agent; after repair and re-verification, this critique must be repeated before explicit human final acceptance.

This critic does **not** grant final acceptance and has not approved Gate A/B/C/D. Nothing has been promoted to `accepted/`.
