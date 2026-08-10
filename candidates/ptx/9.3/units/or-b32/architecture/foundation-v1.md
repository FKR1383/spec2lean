# PTX or.b32 Foundation Architecture v1 — DRAFT — NOT HUMAN APPROVED

## 1. Scope

- DESIGN CHOICE (D-0): This artifact is language-wide architecture for the bounded unit `or.b32` in PTX ISA 9.3, covering only foundations needed for future formalization of instruction execution (not source-text parsing of entire PTX programs).
- DESIGN CHOICE (D-1): Scope is the scalar form `or.type d, a, b;` with `.type = .b32`; sibling forms (`.pred`, `.b16`, `.b64`) and the rest of section 9.7.8 are out of scope unless explicitly noted.
- DESIGN CHOICE (D-2): This artifact describes architecture only: syntactic categories, operand model, typing/model constraints, predication, minimal machine state, and candidate obligations. It does **not** define instruction-level Lean code.
- DESIGN CHOICE (D-3): It is a candidate for Gate A review only; no gate is approved here.

## 2. Official source facts

Primary source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`), PTX ISA version 9.3.
Metadata: `documents/sources/nvidia/ptx/9.3/source-manifest.json` and `documents/sources/nvidia/ptx/9.3/SHA256SUMS`.

- SOURCE FACT (SF-O1) — Section 9.7.8.2 “Logic and Shift Instructions: or” exists at HTML anchor `logic-and-shift-instructions-or` (lines 14290-14325).
- SOURCE FACT (SF-O2) — `or.type d, a, b;` syntax with `.type = { .pred, .b16, .b32, .b64 }` (lines 14298-14301).
- SOURCE FACT (SF-O3) — Description: “Biwise OR.” and `d = a | b;` as semantics (lines 14295 and 14307).
- SOURCE FACT (SF-O4) — Notes: “The size of the operands must match, but not necessarily the type.” and “Allowed types include predicate registers.” (lines 14311-14312).
- SOURCE FACT (SF-O5) — PTX ISA Notes: “Introduced in PTX ISA version 1.0.” (line 14314).
- SOURCE FACT (SF-O6) — Target ISA Notes: “Supported on all target architectures.” (line 14316).
- SOURCE FACT (SF-O7) — Examples include `or.b32 mask mask,0x00010001` and `or.pred p,q,r;` (line 14319-14320).
- SOURCE FACT (SF-O8) — Family intro section 9.7.8 states logic/shift instructions are fundamentally untyped, same-size bit-wise operands, and includes `and`, `or`, `xor`, `not` (which also operate on predicates) (lines 14240-14243).
- SOURCE FACT (SF-O9) — General instruction format section 9.2: PTX instructions can have optional guard predicate; destination operand `d` and sources `a`,`b`,`c`; and optional bit bucket `_` destination (lines 7517-7527, 7534-7535).
- SOURCE FACT (SF-O10) — Predicated execution: all instructions have optional `@{!}p`, predicates are `.pred` in `.reg`, and instructions without guard execute unconditionally (lines 7541-7550).
- SOURCE FACT (SF-O11) — Section 9.7 says all instructions may be predicated and optional guard is omitted in syntax (lines 8722-8723).
- SOURCE FACT (SF-O12) — Fundamental types: type names include `.b32` under bits and `.pred`; same type-size specifiers for variable declarations and instructions; operand compatibility rules include “bit-size type is compatible with any fundamental type having same size” (lines 3022, 3023, 3041-3058, 3062-3066).
- SOURCE FACT (SF-O13) — Register state space: `.reg` is fast storage, 32-bit scalar regs supported, predicate registers are 1-bit, registers are not addressable (lines 2617-2627).
- SOURCE FACT (SF-O14) — Variables declare state space/type/name; predicates only in register state space (lines 3753-3755).
- SOURCE FACT (SF-O15) — Parameterized variable names can introduce many registers of a fundamental type, e.g., `.reg .b32 %r<100>;` (lines 3940-3944).
- SOURCE FACT (SF-O16) — Restricted sub-word use: `.b8` is restricted to selected instructions; `.b32` is not in that restriction list (line 3074).

## 3. Proposed Lean architecture (bounded)

- DESIGN CHOICE (D-1) — Instruction node shape: `Instruction` with fields `guard` (optional, `none | pos | neg`), mnemonic `or`, type tag `b32`, destination operand, source1 operand, source2 operand.
- DESIGN CHOICE (D-2) — Operand categories (bounded): destination register; source register/immediate for `a` and `b`; optional candidate destination bit-bucket `_` inherited from 9.2 (SF-O9, OQ-1).
- DESIGN CHOICE (D-3) — Type/width model: minimal type universe including bit-size categories and predicate; `.b32` maps to 32-bit bitwise domain and `.pred` maps to 1-bit predicate domain.
- DESIGN CHOICE (D-4) — State model for bounded semantics: pair of register files `(reg : RegFile, predReg : PredFile)`, where register keys come from declarations and `.reg` values map to typed values.
- DESIGN CHOICE (D-5) — Instruction-local execution relation style: transition relation `exec : State × Instruction → State × Outcome` with `Outcome` at least `{executed, guardFalse}` for this unit.
- DESIGN CHOICE (D-6) — Guard semantics follow complete-guard interpretation: `true` when no guard, value of `p` for `@p`, negation for `@!p`.
- DESIGN CHOICE (D-7) — On guard false: no state change (D-6 consequence). This is pending stronger confirmation as a non-guard-specific rule across PTX (OQ-3).
- DESIGN CHOICE (D-8) — Version/target metadata per unit: recorded introduced-in PTX ISA version 1.0, target applicability “all target architectures.”
- DESIGN CHOICE (D-9) — Error/result behavior: no exceptional outcome is modeled from this unit’s own text since no explicit error, fault, or trap clause is present in 9.7.8.2 (A-2).

## 4. Fact-to-design mapping

- SF-O1, SF-O2 → D-1
- SF-O2, SF-O7, SF-O9 → D-2
- SF-O8, SF-O12 → D-3
- SF-O13, SF-O14, SF-O15 → D-4
- SF-O5, SF-O6, SF-O9, SF-O10, SF-O11 → D-8
- SF-O9, SF-O10, SF-O11 → D-6, D-7
- SF-O9, SF-O13 → D-5
- SF-O2, SF-O3, SF-O5, SF-O6 → D-9

## 5. Dependency graph

- Operand syntax (D-1, D-2) depends on SF-O2 and SF-O9.
- Predicate/guard architecture (D-6, D-7) depends on SF-O10 and SF-O11.
- Type/representation architecture (D-3) depends on SF-O12 and SF-O8.
- Register/state architecture (D-4) depends on SF-O13, SF-O14, SF-O15.
- Execution relation and obligations (D-5) depends on all above.
- Version/target metadata (D-8) depends on SF-O5 and SF-O6.

## 6. Assumptions

- ASSUMPTION (A-1) — The HTML source is the governing evidence in this run; PDF was not read.
- ASSUMPTION (A-2) — Predicate-register value domain is a two-valued logic model for `.pred` (the exact Lean encoding is a Lean-mapping decision).
- ASSUMPTION (A-3) — Instruction-level single-step semantics for `or.b32` is deterministic and side-effecting only via destination writes and no memory system state.
- ASSUMPTION (A-4) — No explicit error/exception behavior appears in section 9.7.8.2, therefore no error outcome is required in the bounded model.
- ASSUMPTION (A-5) — The `st.param`/`ld.param` predication exception for argument-passing instructions does not apply to `or` (because the exception is stated for `st.param`/`ld.param` only), but this is a non-membership argument that depends on the section boundaries.
- ASSUMPTION (A-6) — `or.b32` destination bit bucket `_` is permitted for the unit via the global 9.2 rule; the section has no explicit `_` example.
- ASSUMPTION (A-7) — “The size of the operands must match” plus family untypedness implies immediate operands in `or.b32` examples can be 32-bit constants if typed to `.b32`-compatible size; source typing details are a semantic-phase decision.

## 7. Ambiguities

- AMBIGUITY (AMB-1) — Whether the `or.b32` bounded unit permits bit-bucket `_` as destination is not explicitly shown in section 9.7.8.2.
- AMBIGUITY (AMB-2) — Exact typing of immediate `0x00010001` in the example under `or.b32` is not stated directly as part of `or` operand grammar; it is inferred from family usage and notes.
- AMBIGUITY (AMB-3) — Whether `or.b32` should treat result domain as exact 32-bit word algebra (bit-vector) or an extensional equivalent encoding is a representation choice deferred to Lean mapping.

## 8. Open questions

- OPEN QUESTION (OQ-1) — Confirm whether `_` is accepted in `or.b32` as destination by an explicit rule in any normative text for this family.
- OPEN QUESTION (OQ-2) — Resolve the precise literal typing rule for immediate `b` in `or.b32` (signed/unsigned/bitwise form and parser acceptance).
- OPEN QUESTION (OQ-3) — Confirm that guard-false behavior for all instructions in this family is exactly “no state update,” not merely a convention in syntax omissions.
- OPEN QUESTION (OQ-4) — Decide how to encode predicate values (`.pred`) in Lean while preserving 1-bit semantics in proofs.

## 9. Candidate theorem-obligation families

These are proposed for later semantic proof stages; they are not implemented yet.

### Validation obligations

- VAL-1 — Instruction shape well-formedness: `.b32`-typed instruction has exactly 2 operands after destination.
- VAL-2 — Operand compatibility: `d`, `a`, `b` are size-compatible with `.b32` under family size rule and fundamental compatibility.
- VAL-3 — Guard well-typedness: if guard present, it is a `.pred` variable.
- VAL-4 — Declared destination/source references and optional destination `_`.
- VAL-5 — Version metadata matches PTX ISA Note for base `or.b32` (1.0).
- VAL-6 — Target metadata matches “supported on all target architectures”.

### Proof obligations (non-vacuous)

- PRF-1 — Determinism: for well-typed well-formed states, `or.b32` execution relates to at most one resulting state.
- PRF-2 — Destination-only update: when destination is a register and instruction executes, only that register may change; other registers and predicates unchanged.
- PRF-3 — Bit-bucket locality: when destination is `_`, no value register is updated (if D-2/D-5 includes `_`).
- PRF-4 — Guard-false frame: if complete guard is false, whole state is unchanged.
- PRF-5 — Guard-behavior completeness: executes iff complete guard expression evaluates true.
- PRF-6 — Result-domain membership: computed destination value belongs to `.b32` value domain.
- PRF-7 — Bitwise fidelity: when `or.b32` executes with register/immediate sources, destination receives bitwise-or of read operands (`d = a | b`).

## 10. Evidence index

- `documents/sources/nvidia/ptx/9.3/source-manifest.json` (specVersion 9.3, initial_formalization_unit `add.u32`), lines 1-38.
- `documents/sources/nvidia/ptx/9.3/SHA256SUMS` SHA-256 list for html/pdf hashes.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 14290-14325, anchor `logic-and-shift-instructions-or`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 14236-14243, anchor `logic-and-shift-instructions`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 7517-7535, anchor `ptx-instructions`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 7537-7550, anchor `predicated-execution`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 8722-8723, anchor `instructions`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 3015-3068, anchor `fundamental-types` (and `fundamental-types-fundamental-type-specifiers`).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 2613-2627, anchor `register-state-space`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 3743-3755, anchor `variables`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 3940-3944, anchor `parameterized-variable-names`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 3074-3075, anchor `restricted-use-of-sub-word-sizes`.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` lines 6257-6261, anchor (search context) on predication exception for `st.param`/`ld.param`.
- Searches (this pass): `@p or` (0 matches), `or.b64` (1 match elsewhere), `or.b16` (1 match elsewhere), `or.pred` (1 match at 14320), `or.b32` (1 usage in-family example at 14319, plus non-family mentions).

## 11. Gate A review checklist (for future human Gate A)

- [ ] Scope bounded to `or.b32` and does not pre-define full-or broader families.
- [ ] All statements labeled as SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION.
- [ ] `SOURCE FACT` entries are grounded in the evidence index above with document anchor or line ranges.
- [ ] Predicate/guard architecture is clearly defined for no guard/`@p`/`@!p`.
- [ ] Validation obligations and proof obligations are separated and non-vacuous.
- [ ] Open ambiguities and unresolved questions are explicit and unresolved.
- [ ] No Lean code and no axioms/theorems are introduced.
- [ ] Artifact remains `DRAFT — NOT HUMAN APPROVED`.
