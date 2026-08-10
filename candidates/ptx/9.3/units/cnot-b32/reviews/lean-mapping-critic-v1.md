# Independent Lean-Mapping Critique — CnotB32-v1 (cnot.b32)

## 1. Reviewed artifacts
- `candidates/ptx/9.3/units/cnot-b32/lean/CnotB32-v1.lean`
- `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json`

## 2. Verdict
**REVISE**: Lean mapping is not yet suitable for direct Gate C presentation due to traceability defects.

## 3. Findings

| ID | Severity | Affected artifact | Exact location | Evidence references | Description | Consequence | Required owner | Human review required |
|---|---|---|---|---|---|---|---|---|
| F-LM-1 | MAJOR | `candidates/ptx/9.3/units/cnot-b32/lean/CnotB32-v1.lean` | Multiple declarations with semantic comment tags, e.g. `U32` line 35, `RegId` line 42, `PredId` line 49, `SourceOperand` line 59, `MachineState` line 99, and related comment blocks | `candidates/ptx/9.3/units/cnot-b32/semantics/semantics-v2.json` defines claim IDs as `SF-1..SF-8`, `DI-1..DI-4`, `OQ-1..OQ-4` (no `SF-C*`/`DI-*`/`D-*` IDs) | The Lean file repeatedly cites non-existent semantic IDs such as `SF-C3`, `SF-C12`, `SF-15`, `DI-1`, etc., and `D-*` design IDs. This does not establish exact traceability from each definition to approved semantics IDs. | Blocked Gate C auditability: reviewers cannot mechanically verify semantic correspondence claim-by-claim; a future proof engineer may overstate coverage or miss mismatches because citation IDs are not grounded in the approved semantic artifact. | Lean formalizer | Yes |

## 4. Additional notes
- `lean_check_file` on the reviewed file succeeded (exit code 0, no errors/warnings), but compile success is not sufficient for semantic faithfulness.
- `semantics-v2.json` includes open question `OQ-3` about literal width-casting of `0`/`1`. The Lean implementation fixes this by constructing `Fin (2^32)` values via `mkB32`; this should be explicitly documented with the corresponding open question resolution status before Gate C, rather than treated as implicit commitment.

## 5. Required revision
- Update all semantic traceability comments to reference exact IDs from `semantics-v2.json` and explicitly annotate where Lean makes a design-resolution choice for `OQ-*` items.

