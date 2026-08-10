# Independent Final Critique — and.b16 (PTX ISA 9.3), run ptx-9.3-and.b16-d33cf813

## Stage status

- Stage: `FINAL_CRITIQUE` (attempt 1, run revision 21).
- Required artifact created at `candidates/ptx/9.3/units/and-b16/reviews/final-critic-v1.md`.
- This review is an aggregation pass only; it does **not** approve any gate.

## 1) Inputs reviewed

1. `candidates/ptx/9.3/units/and-b16/architecture/foundation-v2.md`
2. `candidates/ptx/9.3/units/and-b16/source-bundles/source-bundle-v4.json`
3. `candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json`
4. `candidates/ptx/9.3/units/and-b16/reviews/architecture-critic-v2.md`
5. `candidates/ptx/9.3/units/and-b16/reviews/semantics-critic-v1.md`
6. `candidates/ptx/9.3/units/and-b16/lean/AndB16-v1.lean`
7. `candidates/ptx/9.3/units/and-b16/reviews/lean-mapping-critic-v1.md`
8. `candidates/ptx/9.3/units/and-b16/theorems/obligations-v1.json`
9. `candidates/ptx/9.3/units/and-b16/reviews/theorem-strength-critic-v1.md`
10. `candidates/ptx/9.3/units/and-b16/lean/AndB16Proofs-v1.lean`
11. `lean/Spec2Lean/PTX/AndB16.lean`
12. `lean/Spec2Lean/PTX/AndB16Proofs.lean`
13. `lean/Spec2Lean.lean`
14. Human gate records in `runs/ptx-9.3-and.b16-d33cf813/run.json` and benchmark-auto evidence in `reviews/ptx-and-b16/benchmark-auto/*`.

## 2) Findings

### F-AND16-FC-001 (MINOR)
- **Severity:** MINOR
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/theorems/obligations-v1.json`
- **Exact location:** `theorem_obligations[3]`, `PTX-AND16-THM-004` (`AndB16Step_false_guard_preserves_state`)
- **Evidence references:** theorem-sketch in obligations-v1.json lines 145-159; theorem in `candidates/ptx/9.3/units/and-b16/lean/AndB16Proofs-v1.lean` lines 140-143
- **Description:** The stated intent is “when the guard is false, no modeled state changes occur,” but the theorem is `s = s` with a precondition `hstep : AndB16Step s i s`, i.e., it proves only constructor triviality, not no-op preservation for an arbitrary step target.
- **Consequence:** Conclusion is weaker than intent and is non-vacuous only for a restricted premise shape; it does not characterize arbitrary false-guard no-op preservation.
- **Required owner for revision:** Lean Formalizer / Proof Engineer
- **Human review required:** Yes

### F-AND16-FC-002 (MINOR)
- **Severity:** MINOR
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/lean/AndB16-v1.lean`
- **Exact location:** header lines 4-8
- **Evidence references:** semantics file status line 6 (`READY_FOR_CRITIQUE`), gate records in `run.json`
- **Description:** File comment states “Approved semantic interpretation,” but the paired semantic artifact is marked `READY_FOR_CRITIQUE` and gates B/C are benchmark-auto (non-human) in this run.
- **Consequence:** Pure traceability/provenance hygiene issue; no semantic or proof impact.
- **Required owner for revision:** Lean Formalizer
- **Human review required:** No

### F-AND16-FC-003 (NOTE)
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json`
- **Exact location:** `source_bundle_references[0].bundle_of`
- **Evidence references:** `PTX-9.3-AND16-001`..`010`, `PTX-AND16-SEM2-001`
- **Description:** `bundle_of` contains `source-bundle-v3` while text references `source-bundle-v4`.
- **Consequence:** Traceability metadata noise only.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** No

### F-AND16-FC-004 (NOTE)
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json`
- **Exact location:** `state_reads` / `state_writes` entries (lines ~213-252)
- **Evidence references:** `PTX-9.3-AND16-001`, `PTX-9.3-AND16-003`, `PTX-9.3-AND16-006`
- **Description:** Reads/writes are framed as unconditional register read/write for `a` and `b`; this is a valid bounded commitment only under the unit’s explicit no-immediate-design, but should be interpreted under that design constraint.
- **Consequence:** Non-blocking semantic-drift hygiene item; already represented as OPEN_QUESTIONs in the same artifact.
- **Required owner for revision:** Semantic Extractor
- **Human review required:** No

## 3) Disposition counts

- **BLOCKER:** 0
- **MAJOR:** 0
- **MINOR:** 2
- **NOTE:** 2
- **Pre-gate revision required:** No

## 4) Source-faithfulness status

Overall status: **largely faithful for this bounded unit**, with unresolved operand-form scope questions left explicit. The formal model is consistent with the approved artifacts in this run and does not claim unsupported behavior beyond the bounded restrictions (`reg` destination only, no immediate sources). Open questions remain documented (immediate source in `a/b`, `_` destination) and are not hidden.

## 5) Unresolved state-affecting gaps

- `OQ-AND16-IMM-A` / `OQ-AND16-IMM-B`: whether immediate source operands are legal for and.b16 is unresolved in bounded evidence.
- `OQ-AND16-DST`: whether `_` destination is legal for and.b16 is unresolved in unit-specific evidence.
- No blocked missing behavior claims for the chosen bounded profile; gaps are declared and scoped as bounded-construction assumptions.

## 6) Theorem-weakening status

- No direct theorem weakening in Lean mapping declarations.
- One non-blocking weakness remains from proof obligations: `PTX-AND16-THM-004` is weaker than the natural no-op intent (as in F-AND16-FC-001).

## 7) Proof bypass status

- Checked via `lean_check_file`/`lean_get_diagnostics`: no `sorry`, `admit`, `axiom`, or `unsafe` in proof artifacts.
- Proof files are compilable and contain direct case splits/simp proofs; no bypass behavior detected.

## 8) Lean compilation status

- `lean/Spec2Lean/PTX/AndB16.lean`: `lean_check_file` success (exit 0, 0 errors, 0 warnings).
- `lean/Spec2Lean/PTX/AndB16Proofs.lean`: `lean_check_file` success (exit 0, 0 errors, 5 linter warnings).
- `candidates/ptx/9.3/units/and-b16/lean/AndB16-v1.lean`: success (0 errors, 0 warnings).
- `candidates/ptx/9.3/units/and-b16/lean/AndB16Proofs-v1.lean`: success (0 errors, 5 warnings).
- `lean/Spec2Lean.lean`: success (0 errors, 0 warnings).
- Human final proof-gate check not performed by this stage (not requested for final critique); Lean success is internal validity, not source-faithfulness.

## 9) Final disposition / readiness

- **SOURCE:** non-blocking minor/note gaps only.
- **State-affecting unresolved claims:** bounded and documented.
- **Theorem weakening:** one minor non-blocking issue retained for human awareness.
- **Proof bypass:** none.

**READY for explicit Human FINAL approval** (the FINAL gate itself is not approved by this reviewer).