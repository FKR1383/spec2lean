# PTX `or.b32` Foundation Architecture v4 — DRAFT (UNAPPROVED)

## 1) Scope

- DESIGN CHOICE (SC-1): Bound language architecture to PTX ISA 9.3 instruction unit `or.b32` only.
- DESIGN CHOICE (SC-2): Covers instruction syntax/operands, typing boundaries, minimal state, guard semantics, and one-step execution behavior for local semantics.
- DESIGN CHOICE (SC-3): Excludes whole-program parsing, scheduling, barriers/sync, memory model, function call/return machinery, and non-control-flow side effects.
- DESIGN CHOICE (SC-4): No Lean code, proof scripts, axioms, or theorems are introduced in this stage.
- AMBIGUITY (AMB-S0): No source text in scope establishes full operational treatment of invalid declarations (e.g., out-of-scope references) beyond single-step malformed input handling.

## 2) Official source facts

Evidence format below follows: document identity, spec version, section anchor, line range, status.

- **SF-PG-1 (direct):** `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`) — `logic-and-shift-instructions-or`, lines 14298–14301 (anchor `logic-and-shift-instructions-or`), syntax `or.type d, a, b;` with `.type = { .pred, .b16, .b32, .b64 }`.
- **SF-PG-2 (direct):** same file, `logic-and-shift-instructions-or`, lines 14295–14295, description “Biwise OR.”
- **SF-PG-3 (direct):** same file, `logic-and-shift-instructions-or`, lines 14297–14308, semantics `d = a | b;` and description “Compute the bit-wise or operation...”.
- **SF-PG-4 (direct):** same file, `logic-and-shift-instructions-or`, lines 14310–14312, notes: “The size of the operands must match, but not necessarily the type.” and “Allowed types include predicate registers.”
- **SF-PG-5 (direct):** same file, `logic-and-shift-instructions-or`, lines 14313–14316, intro/target notes: introduced in PTX ISA 1.0; supported on all target architectures.
- **SF-PG-6 (direct):** same file, `logic-and-shift-instructions-or`, lines 14318–14320, examples: `or.b32  mask mask,0x00010001` and `or.pred  p,q,r;` (immediate appears in **b** position of the example for `or.b32`).
- **SF-PTX-1 (direct):** same file, anchor `ptx-instructions`, lines 7517–7527, optional guard predicate form and operand roles where `d` is destination and `a,b,c` are sources.
- **SF-PTX-2 (direct):** same file, lines 7528–7535, destination may be optional; bit bucket `_` may be used in place of destination register for some instructions.
- **SF-PRED-1 (direct):** same file, `predicated-execution`, lines 1751–1754 (source: lines 1753–1754), optional guard is `@p` and may be negated as `@!p`.
- **SF-PRED-2 (direct):** same file, lines 21838–21839, predicated execution “do nothing” when predicate is False.
- **SF-PRED-3 (direct):** same file, `predicated-execution`, lines 7541–7544, predicate registers use `.pred` and are declared as `.reg .pred ...`.
- **SF-TYPE-1 (direct):** same file, `fundamental-types`, lines 3020–3022, same type-size specifiers used for variable declarations and instruction typing.
- **SF-TYPE-2 (direct):** same file, `logic-and-shift-instructions` lines 14240–14243, logic/shift family “fundamentally untyped,” same-size bit-wise operands, and `and/or/xor/not` also operate on predicates.
- **SF-TYPE-3 (direct):** same file, `register-state-space`, lines 2621–2624, registers: scalar widths 8/16/32/64/128 bits; predicate registers are 1-bit.
- **SF-DECL-1 (direct):** same file, `variables`, lines 3751–3755, variable declaration form and predicate variables may only be declared in register state space.
- **SF-DECL-2 (direct):** same file, `parameterized-variable-names`, lines 3939–3944, example `.reg .b32 %r<100>;`.
- **SF-SM-1 (direct/limited):** same file, section `ptx-instructions`, lines 1749–1750 and 1755, operands include register variables and constant expressions (general property, not unit-specific).

## 3) Proposed Lean architecture

- D-1: Instruction syntax node `OrB32` with fields:
  - `guard : Option Guard` (`none | some pos(p) | some neg(p)`)
  - `dst : OrB32Dst`
  - `src1 : RegisterRef`
  - `src2 : OrB32Src2`
- D-2: Operand taxonomy:
  - `OrB32Dst := RegisterRef | BitBucket`
  - `OrB32Src2 := RegisterRef | Immediate`
- D-3: Unit-specific typing:
  - Active type family is `.b32` only.
  - Destination and both sources are required to be 32-bit-size compatible values in the bounded domain.
  - Source-1 is **explicitly register-only**; source-2 can also be immediate for bounded support of `or.b32 mask, mask, 0x00010001`.
  - Predicate forms (`.pred`) are excluded at this unit boundary by design scope (separate `or.pred` unit).
- D-4: State model:
  - `State := RegFile × PredFile` where `RegFile` and `PredFile` map declared names to value cells; predicate declarations restricted to register-space by fact SF-DECL-1.
  - No memory, control-stack, or thread-group state in this unit.
- D-5: Guard evaluation:
  - `none` means true;
  - `some pos(p)` reads predicate `p`;
  - `some neg(p)` is Boolean negation.
- D-6: Execution relation:
  - `exec : State → OrB32 → ExecResult State` with outcomes:
    - `executed`: operands well-formed + guard true;
    - `notExecuted`: guard evaluates false;
    - `stuck`: malformed references/typing inconsistencies not representable in the bounded well-formedness relation.
  - On `executed`, destination update writes bitwise-or of source values when `dst` is a register; no update if `dst = _`.
- D-7: Runtime representation:
  - Bit patterns are 32-bit words for `.b32` unit arithmetic.
  - Predicate runtime value is modeled as `Bool` for this bounded phase.
- D-8: Metadata record for this unit includes `introduced = 1.0`, `target = all architectures` from SF-PG-5.

## 4) Fact-to-design mapping

- SF-PG-1, SF-PG-2, SF-PG-3, SF-PG-5 → D-1, D-6, D-8
- SF-PG-6 → D-2, D-3 (src2 immediate support, bounded by unit example)
- SF-PTX-1, SF-PRED-1 → D-1, D-5
- SF-PTX-2 → D-2
- SF-PG-4, SF-TYPE-2, SF-TYPE-1 → D-3
- SF-PRED-2, SF-PG-5 → D-6
- SF-PRED-3, SF-TYPE-3, SF-DECL-1, SF-DECL-2 → D-4, D-7

## 5) Dependency graph

1. **Typing/state foundations**: SF-TYPE-1, SF-TYPE-2, SF-TYPE-3, SF-DECL-1, SF-DECL-2 ⇒ D-3, D-4, D-7.
2. **Instruction/operand shapes**: SF-PTX-1, SF-PG-1, SF-PG-6 ⇒ D-1, D-2, D-3.
3. **Predication layer**: SF-PRED-1, SF-PRED-2, SF-PRED-3 ⇒ D-5, D-6.
4. **Execution layer**: SF-PG-3 + layer1-3 deps ⇒ D-6.

## 6) Assumptions

- ASS-1: The global parser/lexer constraints from instruction grammar are delegated; this architecture states bounded normalization: first source is register-only.
- ASS-2: Immediate literals in source-2 are treated as bounded 32-bit literals consistent with the `or.b32` example.
- ASS-3: No exceptional control transfers are modeled for `or.b32`; only guard-driven no-op and malformed-input `stuck`.
- ASS-4: Predicate runtime values are modeled as classical booleans for this architecture draft.

## 7) Ambiguities

- AMB-1: Whether `or.b32` syntax actually allows immediate in source-1 at the language level is not shown by unit-specific text; only source-2 immediate is evidenced (`...mask,0x00010001`).
- AMB-2: The precise acceptance rule for `_` as destination for `or.b32` is inherited from generic syntax (SF-PTX-2) and not explicitly repeated in the `or` unit section.
- AMB-3: Canonical width/typing for immediate 0x00010001 is not explicitly stated in `or.b32` text.
- AMB-4: Predicate behavior for malformed states (uninitialized predicates, unknown register mapping) is not specified in this unit.

## 8) Open questions

- OQ-1: Should bounded architecture permit immediate literals at source-1 for `or.b32` once full parser evidence for this exact mnemonic variant is gathered?
- OQ-2: Should `_` be explicitly included in final Lean parsing schema for `or.b32` or narrowed further by instruction-family-specific parsing tests?
- OQ-3: Should immediate typing be rule-based by parser literal width or inferred from destination/operation width?

## 9) Candidate theorem-obligation families

### Validation obligations

- VAL-1: Structural well-formedness: one optional guard, one destination, and exactly two source operands.
- VAL-2: Destination must be register or `_`.
- VAL-3: `src1` must be a register reference (unit restriction).
- VAL-4: `src2` is either register reference or immediate.
- VAL-5: Active instruction is unit-tagged `.b32`, and source/dest values are 32-bit-size-compatible.
- VAL-6: Predicate guard is absent or `{ p, !p }` with declared predicate name.

### Proof obligations (non-vacuous)

- PRF-1: Guard false implies `notExecuted` and state unchanged.
- PRF-2: For well-formed, well-typed inputs with true guard, execution is deterministic.
- PRF-3: On `executed`, only destination register is updated (or no update for `_`).
- PRF-4: `dst` value equals bitwise-or of resolved source values at 32-bit width.
- PRF-5: Version/target metadata is preserved as part of unit descriptor.

## 10) Evidence index

- `documents/sources/nvidia/ptx/9.3/source-manifest.json` (specification_version 9.3).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`), anchors/lines:
  - `logic-and-shift-instructions-or`: 14295–14321
  - `logic-and-shift-instructions`: 14240–14243
  - `ptx-instructions`: 7517–7535
  - `predicated-execution`: 7541–7544
  - `control-flow-instructions-at`: 21838–21840
  - `fundamental-types`: 3019–3022
  - `register-state-space`: 2617–2624
  - `variables`: 3751–3755
  - `parameterized-variable-names`: 3939–3944
  - `instructions`: 8722–8723
- Evidence status: all entries above are direct text pulls from the cited HTML lines except D-6 (unit-level implication of source-2 immediate, from `or.b32` example, not symmetric proof for source-1).

## 11) Gate A review checklist draft

- [ ] Bounded scope is explicitly `or.b32` only (no active cross-unit inclusion of `or.pred`, `or.b16`, `or.b64`).
- [ ] Source facts are separated from design choices/assumptions/ambiguities/open questions.
- [ ] Each source fact has document identity, version, anchor/line span, and evidence status.
- [ ] Proposed architecture identifies syntax, operand classes, type constraints, state model, predication semantics, execution outcomes, and metadata.
- [ ] Source-1 register-only restriction is explicit and justified as unit-specific, not a global claim.
- [ ] Validation and proof-obligation families are non-vacuous and local to `or.b32`.
- [ ] Open questions are explicit and unresolved where text is insufficient.
- [ ] No Lean code/theorems/axioms are introduced.
- [ ] Major scope/typing drift risks from prior attempts are explicitly eliminated (especially immediate-generalization).
