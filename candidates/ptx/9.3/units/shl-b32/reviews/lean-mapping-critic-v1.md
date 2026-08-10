# Lean Mapping Critique — `shl.b32` (v1)

**Run:** ptx-9.3-shl.b32-1fe9973c  
**Stage:** LEAN_MAPPING_CRITIQUE  
**Artifact reviewed:** `candidates/ptx/9.3/units/shl-b32/lean/ShlB32-v1.lean`

## Scope check
- Reviewed the Lean mapping against approved semantic interpretation `semantics/semantics-v1.json` (interpretation id `ptx-9.3-shl-b32-semantics-v1`).
- Checked: instruction form/arity, operand roles/order, typing-domain modeling, shift semantics (`<<` with clamp behavior), predication semantics, and state read/write shape.

## Findings
No blocking, major, minor, or note-level mapping defects were identified.

- The Lean instruction structure matches the bounded form `shl.b32 d, a, b;` with `d,a,b` roles and arity.
- Source/destination read-write behavior is aligned: reads `a` and `b` from state, computes `d` by `shlValue`, and writes only `d`.
- Guard semantics (`none`/`@p`/`@!p`) and false-guard no-op state behavior are implemented consistently with sourced predication interpretation.
- Shift behavior uses clamped count (`Nat.min b 32`) and 32-bit modular arithmetic via `Fin 2^32`, matching the bounded-unit choice of `.b32`.
- Relational transition form (`ShlB32Step`) is conservative and corresponds to `execShlB32` branches, including explicit guard-false transition.

## Verdict
**READY_FOR_HUMAN_GATE_C** (not approved by this agent; human gate remains pending).
