# Final Independent Critique — `cnot.b32` (v1)

Run: `ptx-9.3-cnot.b32-96465672` · Stage: `FINAL_CRITIQUE` · Revision: 24  
Artifact root: `candidates/ptx/9.3/units/cnot-b32`

## 1) Verdict
- **Overall:** Acceptable for human final review with non-blocking notes.
- **Read artifacts:** architecture critic v1, semantics v2 + critics, lean-mapping critic v3, theorem-strength critic v2, source bundle v1, obligations v3, Lean modules (`lean/Spec2Lean/PTX/CnotB32.lean`, `lean/Spec2Lean/PTX/CnotB32Proofs.lean`), run state (`runs/ptx-9.3-cnot.b32-96465672/run.json`).

## 2) Finding counts
- BLOCKER: **0**
- MAJOR: **0**
- MINOR: **0**
- NOTE: **2**

## 3) Source-faithfulness status
- **Status:** PASS (bounded to `cnot.b32` with explicit traceability).
- Operand order/roles and predicate semantics align with `cnot.type d, a;`, `cnot.b32 d, a;`, and guard forms from the bounded semantics (`PTX-9.3-CNOT-003`, `PTX-9.3-CNOT-005`, `PTX-9.3-CNOT-009`, `PTX-9.3-CNOT-015`, `PTX-9.3-CNOT-016`).
- No detected contradictions against cited claim IDs.

## 4) Findings

### NOTE-1
- **Affected artifact:** `cnot.b32 semantics` / `CnotB32` mapping
- **Location:** `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json` open questions `OQ-2`, `OQ-3`, `OQ-4`
- **Description:** Three behaviorally relevant ambiguities are still explicit but unresolved in the approved semantics:
  - destination bit-bucket legality (`OQ-2`),
  - width/cast of constants `0/1` (`OQ-3`),
  - whether “do nothing” on false guard has strictly no architectural side effect beyond unchanged visible state (`OQ-4`).
- **Consequence:** Current theorems are conditioned by this bounded model and do not close the broader, unresolved PTX variance.
- **Required owner:** **Semantic Extractor / Lean Formalizer**
- **Human review required:** Yes, for final semantic scope decision.

### NOTE-2
- **Affected artifact:** `candidates/ptx/9.3/units/cnot-b32/lean/CnotB32Proofs-v1.lean`
- **Location:** compilation output for file
- **Description:** `lean_check_file` succeeds, but reports warnings (non-blocking)
  `candidates`: `lean/Spec2Lean/PTX/CnotB32Proofs.lean` warningCount=6.
- **Consequence:** Diagnostics are not proof-bypass failures; proofs still compile and remain valid, but warning hygiene should be cleaned in a future cleanup pass.
- **Required owner:** **Proof Engineer**
- **Human review required:** No (non-blocking hygiene).

## 5) Unresolved state-affecting gaps
1. `OQ-2` (destination `_`): not modeled; current Lean/API excludes bit-bucket behavior.
2. `OQ-4` (true meaning of no-op on false guard): Lean models false-guard as unchanged machine state with explicit `guardFalse` outcome.
3. `OQ-3` (literal width casting): Lean resolves with modulo-`2^32` construction (`mkB32`), which is an explicit bounded design choice.

## 6) Theorem weakening / strengthening check
- **Status:** No theorem weakening detected.
- Theorem obligations in `obligations-v3.json` and proofs in `CnotB32Proofs-v1.lean` match declaration-level intent and are not broader than executable semantics; no overclaiming or vacuous theorems identified.

## 7) Proof bypass check
- **Status:** **PASS**
- Verified artifacts contain no `sorry`, `admit`, new axioms, or `unsafe` constructs.

## 8) Lean compilation status
- `lean/Spec2Lean/PTX/CnotB32.lean`: SUCCESS (0 errors).
- `lean/Spec2Lean/PTX/CnotB32Proofs.lean`: SUCCESS (0 errors, warnings only).
- Root package `lean/Spec2Lean.lean`: SUCCESS (0 errors).

## 9) Readiness for human final approval
- **Ready for explicit human final approval gate** (status is not auto-approved here).
- No blocking or proof-bypass issues found at this stage.