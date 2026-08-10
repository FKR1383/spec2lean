# Theorem-Strength Critique: shr.b32 (v3)

## Findings

No unresolved BLOCKER/MAJOR theorem-strength or non-vacuity defects were identified in this obligations revision.

- **NOTE-TS-SHR-003**
  - **Severity:** NOTE
  - **Affected Artifact:** `candidates/ptx/9.3/units/shr-b32/theorems/obligations-v3.json`
  - **Location:** `PTX-SHR-THM-002` (statement sketch and disjunctive shape in lines 176-193)
  - **Evidence References:** `PTX-SHR-SEM1-011`, `PTX-SHR-SEM1-012`, `PTX-SHR-SEM1-013`, `PTX-SHR-SEM1-014`, `PTX-SHR-SEM1-015`
  - **Description:** `PTX-SHR-THM-002` still uses an explicit constructor-sync disjunction; because executable semantics is deterministic, each branch is satisfiable and non-empty, but this form is weaker than a direct `if/then` branching equality theorem for all constructors.
  - **Consequence:** The non-exclusive disjunction can make future proof obligations easier than the strongest branch-precise contract, though current text does not appear to be vacuous.
  - **Required Owner for Revision:** Proof Engineer (during proof-generation, can strengthen to direct conditional equations if desired)
  - **Human Review Required:** yes

## Disposition

- BLOCKER: 0
- MAJOR: 0
- MINOR: 0
- NOTE: 1

Pre-gate revision required: **NO**

## Readiness

Marked as ready for human theorem-strength approval.
