# Independent Lean-Mapping Critique — CnotB32-v2 (cnot.b32)

## Reviewed artifacts
- `candidates/ptx/9.3/units/cnot-b32/lean/CnotB32-v2.lean`
- `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json`
- `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json`

## Verdict
**REVISE**: Lean mapping is not yet ready for Gate C due to traceability defects.

## Findings

| ID | Severity | Affected artifact | Exact location | Evidence references | Description | Consequence | Required owner | Human review required |
|---|---|---|---|---|---|---|---|---|
| F-LM-2 | MAJOR | `candidates/ptx/9.3/units/cnot-b32/lean/CnotB32-v2.lean` | Multiple declaration comment headers: `PredId` line 52, `Guard` line 82, `MachineState` line 99, `execCnotB32` line 181 (all containing `SF-12`) | `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json` defines source facts `SF-1`..`SF-8` (no `SF-12`), derived interpretations `DI-1`..`DI-4`, open questions `OQ-1`..`OQ-4` | Several Lean declarations still cite claim ID `SF-12`, which is not present in the approved semantic interpretation. This breaks machine-auditable traceability from Lean definitions to approved semantics and prevents deterministic artifact-level verification of semantic alignment. | Gate C readiness is blocked: semantic-to-Lean mapping cannot be independently validated for the affected declarations because IDs are not traceable to approved semantics. | Lean formalizer | Yes |

## Additional notes
- `lean_check_file` reports `success=true` for `CnotB32-v2.lean` (no Lean errors/warnings).
- Compilation success does not repair semantic traceability gaps.
- One unresolved design question is explicitly preserved in Lean for OQ-3 (`mkB32`), but unresolved questions must remain clearly linked only to IDs present in `semantics-v2.json` and not to nonexistent IDs.
