# Independent Theorem-Strength Critique — cnot.b32 obligations-v3

## 1) Scope and artifacts reviewed
- Reviewed artifact: `candidates/ptx/9.3/units/cnot-b32/theorems/obligations-v3.json` (`obligation_set_id` `ptx-9.3-cnot-b32-obligations-v3`, status `READY_FOR_STRENGTH_REVIEW`).
- Inputs used: `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json`, `candidates/ptx/9.3/units/cnot-b32/lean/CnotB32-v3.lean`, and architecture context `candidates/ptx/9.3/units/cnot-b32/architecture/foundation-v1.md`.
- This review performs theorem-strength and non-vacuity analysis only. No proofs are reviewed at this stage.

## 2) Overall verdict
**NOT READY without revision.**

The 3 proposed theorem obligations are mostly well-formed and traceable, and non-vacuous over the current Lean model, but the set does not include any theorem at theorem-strength that explicitly states the true-guard destination-frame behavior (PRF-2 / DI-3 requirement). This weakens coverage relative to the architecture and semantics (destination-only update and unchanged other state on execute). A dedicated frame theorem is needed before this set is safe for theorem-strength approval.

## 3) Findings

| ID | Severity | Affected artifact | Exact location | Evidence references | Description | Consequence | Required owner | Human review required |
|----|----------|------------------|----------------|--------------------|-------------|------------|----------------|----------------------|
| TS-CNOT-001 | MAJOR | `candidates/ptx/9.3/units/cnot-b32/theorems/obligations-v3.json` | theorem obligations list (`obligations-v3.json` lines 133-179): only `PTX-CNOT-THM-001..003` present | `obligations-v3.json` lines 133-179; architecture PRF-2 (`foundation-v1.md` lines 129-133); semantics DI-3 (`semantics-v2.json` lines 72-75, 129-175); lean def `updateDestination` (`CnotB32-v3.lean` lines 161-164) | The theorem set provides:
- guard-false no-change (`THM-001`),
- destination write witness for one register (`THM-002`), and
- partiality characterization (`THM-003`).

No obligation asserts that on execute (`evalGuard = some true`) the post-state changes only `d` and leaves all other value/predicate state unchanged. `THM-002` only claims `s'.valueRegs r = some (cnotB32 va)` for one register, which is weaker than DI-3 / PRF-2 and does not make destination-only framing explicit.
 | The theorem-strength gate cannot verify that frame obligations are fully discharged from stated theorems. Result: under-specified obligations set; hidden assumptions about implicit extensionality or function unfolding are not documented in theorem text.
 | Proof/Theorem Engineer (theorem-obligation set) | Yes |

## 4) Traceability and non-vacuity checks
- `PTX-CNOT-THM-001`: directly matches `DI-2` guard semantics and `SF-5` false-guard no-op; statement is non-vacuous.
- `PTX-CNOT-THM-002`: matches `SF-2` and `DI-2`; non-vacuity with concrete source values (`0`, `nonzero`).
- `PTX-CNOT-THM-003`: matches partiality characterization of `execCnotB32` and is non-vacuous.
- No `sorry/admit/axiom/unsafe` issues are introduced in theorem statements.

## 5) Required owner and next action
- Add an explicit frame theorem (at least one dedicated theorem mirroring PRF-2) over execute-path true guard, proving unchanged predicate registers and unchanged non-destination value registers.
- Then rerun theorem-strength critique on the revised obligations.

## 6) Human-gate status
This review does **not** approve any gate.
