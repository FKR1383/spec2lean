# Independent Lean-Mapping Critique — xor-b16 Lean mapping v2

## 1. Reviewed artifact

- `candidates/ptx/9.3/units/xor-b16/lean/XorB16-v2.lean`
- Inputs used:
  - `candidates/ptx/9.3/units/xor-b16/semantics/semantics-v1.json` (approved artifact)
  - `candidates/ptx/9.3/units/xor-b16/source-bundles/source-bundle-v1.json`
  - `candidates/ptx/9.3/units/xor-b16/architecture/foundation-v1.md`

## 2. Verdict

**SUCCESS**: No unresolved BLOCKER/MAJOR Lean-mapping defects found against the approved semantic artifact. Minor fidelity gaps remain.

## 3. Findings

| Finding ID | Severity | Affected artifact | Location | Evidence references | Description | Consequence | Required owner | Human review required |
|---|---|---|---|---|---|---|---|---|
| LMC-2 | MINOR | `candidates/ptx/9.3/units/xor-b16/lean/XorB16-v2.lean` | `eval` / `execXorB16` / `XorB16Step.guardFalse`, lines 165-211 | `PTX-XORB16-SEM-006`, `SF-9` | The semantics artifact keeps false-guard behavior as an open question (`PTX-XORB16-SEM-006`), but the Lean transition still commits a concrete behavior (`some s` / `ExecOutcome.guardFalse s` with no undefined case). This is an explicit behavioral commitment beyond an approved claim. | Downstream theorems can prove false-guard no-op without an additional assumption, strengthening claims beyond the currently approved semantic scope. | Lean Formalizer | Yes |
| LMC-3 | MINOR | `candidates/ptx/9.3/units/xor-b16/lean/XorB16-v2.lean` | `SourceA` and `SourceB` definitions, lines 62-73 | `PTX-XORB16-SEM-007`, `XOR16_EXAMPLE_B16` | Source operand `a` remains register-only because immediates are only allowed for `SourceB`. Since `PTX-XORB16-SEM-007` leaves whether `a` can be immediate unresolved, the mapped syntax is a strict subset of the unresolved-but-allowed possibility. | Completeness over instruction forms is not preserved; the relation and executable semantics omit any immediate-`a` encodings until that open question is resolved. | Lean Formalizer | Yes |

## 4. Disposition

- BLOCKER: 0
- MAJOR: 0
- MINOR: 2
- NOTE: 0
- Pre-gate revision required: **No**

## 5. Routing

These are **MINOR/coverage** issues to address in future iteration; they do not block progression to Gate C on this automated run.