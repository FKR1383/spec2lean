# Theorem-Strength Critique — `cnot.b32` (v2)

## Artifact under review
- `candidates/ptx/9.3/units/cnot-b32/theorems/obligations-v3.json`
- Review stage: `THEOREM_STRENGTH_CRITIQUE`
- Run: `ptx-9.3-cnot.b32-96465672`

## Overall verdict

**READY — adequate for Human Theorem-Strength approval (not approved here).**

I reviewed the obligation set for theorem-strength and non-vacuity against:
- `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json`
- `candidates/ptx/9.3/units/cnot-b32/lean/CnotB32-v3.lean`
- `candidates/ptx/9.3/units/cnot-b32/source-bundles/source-bundle-v1.json`
- prior critiques in this unit.

## Findings

No blocking defects found. No theorem obligations are vacuous or circular, and no statement appears weaker than the corresponding modeled semantics.

### Traceability and strength check

- `PTX-CNOT-THM-001`: directly states guarded no-op branch (`evalGuard = some false`). It is not circular and is non-vacuous (examples with concrete false predicates exist).
- `PTX-CNOT-THM-002`: expresses core fidelity `d = (a==0)?1:0` on true-guard/source-resolved path, with destination explicitly constrained to register form; this is the correct bounded-domain strength.
- `PTX-CNOT-THM-003`: exactly characterizes partiality for the defined executor (`none` only for missing guard, or true guard + missing source), while explicitly excluding false-guard non-termination.
- All cited `semantic_claim_ids` in the theorem set exist in the approved semantics (`SF-2`, `SF-4`, `SF-5`, `DI-2`, `DI-3`, `DI-4`) and are used at compatible strength.
- Lean declarations referenced in `lean_declarations_used` are present in `CnotB32-v3.lean`.
- No theorem names overstate their claims relative to the formalized assumptions.

### Non-vacuity and model-fit checks

- Validation obligations are static/definitional or compilation-level checks, as expected for this stage.
- Theorem bodies include concrete state-dependent preconditions (`evalGuard`/`evalSource`/destination register equality) so they are not vacuous.
- No `sorry`, `admit`, new axioms, or `unsafe` are introduced in the obligation set.

## Required follow-up

None before theorem-strength gate.

## Theorem-strength gate readiness

This set is strong enough for `THEOREM_STRENGTH` human gate review.

## Critic independence

I did not edit or repair any reviewed artifact, did not approve human gates, and did not promote artifacts to `accepted/`.