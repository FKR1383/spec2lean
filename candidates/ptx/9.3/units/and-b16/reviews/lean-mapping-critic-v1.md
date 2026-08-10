# Independent Lean Mapping Critique — and.b16 (AndB16-v1)

## 1. Scope

- Reviewed artifact: `candidates/ptx/9.3/units/and-b16/lean/AndB16-v1.lean` (stage `LEAN_MAPPING_CRITIQUE`, run `ptx-9.3-and.b16-d33cf813`, revision 15).
- Semantic reference used: `candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json`.
- Architecture/design context: `candidates/ptx/9.3/units/and-b16/architecture/foundation-v2.md`.
- This review is independent and does **not** approve any gate.

## 2. Overall verdict

**READY FOR PRESENTATION TO HUMAN GATE C** (no blockers/majors identified).

The mapping implements the bounded `and.b16` semantics as encoded in `semantics-v2` with correct operand order/state shape/width and predication behavior:
- `d,a,b` ordering and arity match.
- 16-bit value domain and `Nat.land` computation model are consistent with `d = a & b` over `.b16`.
- Guarded execution is `unguarded`/`@p`/`@!p` with false-guard `guardFalse` and no state change.
- State model and reads/writes are minimal to value and predicate registers.
- No additional assumptions, no errors/axioms/sorry/unsafe shortcuts, and no vacuous theorems are present (no theorem statements exist yet).

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/and-b16/lean/AndB16-v1.lean` (all lines)
- `candidates/ptx/9.3/units/and-b16/semantics/semantics-v2.json` (all claims)
- `candidates/ptx/9.3/units/and-b16/architecture/foundation-v2.md` (DRAFT architecture context)
- `candidates/ptx/9.3/units/and-b16/source-bundles/source-bundle-v4.json`
- `runs/ptx-9.3-and.b16-d33cf813/run.json`
- Lean diagnostics via `lean_check_file` (success, 0 errors, 0 warnings)

Lean check summary:
- `functions.lean_check_file` for `candidates/ptx/9.3/units/and-b16/lean/AndB16-v1.lean`: success.

## 4. Findings

### F-AND16-LM-001 — NOTE
- **Severity:** NOTE
- **Affected artifact:** `candidates/ptx/9.3/units/and-b16/lean/AndB16-v1.lean`
- **Exact location:** header comments at lines 5–8
- **Evidence references:** `PTX-9.3-AND16-006`, `PTX-9.3-AND16-007`, `semantics-v2` field `status` (`READY_FOR_CRITIQUE`)
- **Description:** The header states the semantic source is "approved," but the paired semantic artifact is marked `status: READY_FOR_CRITIQUE` and there is no local Gate B approval record in this run (gates are benchmark-auto-advanced). The Lean definitions themselves still match the semantics file, but the provenance wording overstates the approval state of the source artifact.
- **Consequence:** Non-blocking traceability-hygiene issue; it should not affect executable semantics but can confuse auditability.
- **Required owner for revision:** Lean Formalizer
- **Human review required:** No

## 5. Disposition

- **BLOCKER:** 0
- **MAJOR:** 0
- **MINOR:** 0
- **NOTE:** 1
- **Pre-gate revision required:** No (No BLOCKER/MAJOR findings)

## 6. Gate readiness note

The mapping is coherent with the current bounded semantic interpretation and is suitable for human Gate C presentation. No semantic drift was found in operand order, bit-width, control-flow/guard behavior, state read/write footprint, or encoding choices beyond a provenance clarity item above.
