# Independent Theorem-Strength Critique — and-b16 (obligations-v1)

## 1. Scope
- Reviewed artifact: `candidates/ptx/9.3/units/and-b16/theorems/obligations-v1.json`
- Inputs: `candidates/ptx/9.3/units/and-b16/lean/AndB16-v1.lean`, `candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json`, `candidates/ptx/9.3/units/and-b16/architecture/foundation-v2.md`, and `candidates/ptx/9.3/units/and-b16/source-bundles/source-bundle-v4.json`.
- Stage: THEOREM_STRENGTH_CRITIQUE (run `ptx-9.3-and.b16-d33cf813`, revision 18).
- This critique is independent and does **not** approve any gate.

## 2. Overall verdict

The obligation set is broadly faithful to the bounded Lean mapping and PTX semantics and is suitable for human theorem-strength approval after addressing one strength/clarity issue below.

## 3. Findings

### F-AND16-TS-001 (MINOR)
- **Severity:** MINOR
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/theorems/obligations-v1.json`
- **Exact location:** `theorem_obligations[3]` / `PTX-AND16-THM-004` (`AndB16Step_false_guard_preserves_state`), lines 145-160
- **Evidence references:**
  - Semantics claim `PTX-AND16-SEM2-004`, `PTX-AND16-SEM2-005` (semantics-v2.json)
  - Lean declaration `AndB16Step` constructor `guardFalse` in `lean/AndB16-v1.lean` lines 129-136
- **Description:** The proposed theorem statement is: for any `h : evalGuard s i.guard = some false` and `hstep : AndB16Step s i s`, conclude `s = s`. Because the relation constructor `AndB16Step.guardFalse` already forces the post-state argument to be exactly `s`, this theorem is essentially tautological and does not assert no-op preservation for an arbitrary relational target state.
- **Consequence:** The theorem is weaker than the stated intent “false-guard steps do not change state.” It provides limited proof value for the intended property and can be misleading at the theorem-strength stage.
- **Required owner for revision:** Proof Engineer / Lean Formalizer
- **Human review required:** Yes

## 4. Additional verification notes

- No Lean proof files are present for this unit yet; theorem-strength review therefore evaluates obligation statements and non-vacuity only.
- Remaining obligations (determinism, function/relation correspondence, write fidelity, predicate preservation) are compatible with `AndB16Step` and `execAndB16` in `AndB16-v1.lean` and are not found to be vacuous.
- No `sorry`, `admit`, new `axiom`, or `unsafe` constructions are introduced in the reviewed artifacts.

## 5. Disposition

- **BLOCKER:** 0
- **MAJOR:** 0
- **MINOR:** 1
- **NOTE:** 0
- **Pre-gate revision required:** No (non-blocking)
