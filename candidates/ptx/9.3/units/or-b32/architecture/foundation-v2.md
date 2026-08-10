# PTX `or.b32` Foundation Architecture v2 — DRAFT (UNAPPROVED)

## 1. Scope

**Scope (architecture-only):** bounded language architecture for PTX ISA 9.3 instruction unit `or.b32`.

### In-scope
- Syntactic shape and operand roles for `or.b32` (destination + two sources).
- Predication/guard syntax interaction.
- Type/width constraints relevant to `or` (`.b32` and compatible `.pred`).
- Minimum machine state required for single-step local interpretation.
- Control-flow effect only via guard (instruction execution gating), no memory side effects.

### Out-of-scope
- Parsing whole PTX programs, other control-flow instructions, and other `or` widths.
- Full formal Lean proofs (for later Gate B/C and theorem stages).
- Microarchitectural scheduling/performance details.

## 2. Official source facts (versioned evidence)

Document: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`), spec version 9.3.

### SF-1: `or` instruction definition
- Section 9.7.8.2, anchor `logic-and-shift-instructions-or`, lines 14292–14320.
- Evidence:
  - Rubric `or`, text “Biwise OR.” (lines 14294–14295).
  - Syntax `or.type d, a, b;` with `.type = { .pred, .b16, .b32, .b64 };` (14298–14301).
  - Semantics `d = a | b;` (14307).
  - Notes: “size of operands must match, but not necessarily the type” and “Allowed types include predicate registers.” (14311–14312).
  - PTX ISA notes: introduced in 1.0 (14314).
  - Target ISA notes: supported on all target architectures (14316).
  - Example includes `or.b32  mask mask,0x00010001` and `or.pred  p,q,r;` (14319–14320).

### SF-2: Instruction families are fundamentally untyped bit-wise when size matches
- Section 9.7.8, anchor `logic-and-shift-instructions`, lines 14240–14243.
- Evidence: logic/shift instructions are fundamentally untyped, bit-wise on operands of any type with same size; `and/or/xor/not` also operate on predicates.

### SF-3: Instruction shape and optional operands
- Section 9.2, anchor `ptx-instructions`, lines 7515–7524.
- Evidence: PTX instructions have optional guard `@` and 0–4 operands; destination `d` is the result register and `a,b,c` are source registers.

### SF-4: Optional bit-bucket destination
- Section 9.2, lines 7528–7535.
- Evidence: for some instructions destination is optional; `_` may be used in place of destination register.

### SF-5: Predication model
- Section 9.3, anchor `predicated-execution`, lines 7537–7550.
- Evidence: instructions have optional guard predicate `@{!}p` where `p` may be negated; guard controls conditional execution.
- Section 9.7.13.2 anchor `control-flow-instructions-at`, lines 21834–21840.
- Evidence: `@!p instruction;` executes for threads with guard `True`, threads with `False` do nothing.
- Section 9.2 section intro note lines 8722–8723: all PTX instructions may be predicated and descriptions omit optional guard in syntax.

### SF-6: Predicate type and register properties
- Section 9.3, line 7541.
- Evidence: predicate registers have `.pred` type.
- Section 5.1.1, lines 2621–2624.
- Evidence: scalar registers are 8/16/32/64/128-bit except predicates which are 1-bit.

### SF-7: Fundamental types and compatibility
- Section 5.2.1, anchor `fundamental-types`, lines 3019–3022 and 3062–3066.
- Evidence: type names are used for variable definitions and instruction typing; bit-size and other compatibility rules (same size; bit-size compatible with any fundamental type same size).

### SF-8: Predicate declaration domain constraints
- Section 5.4, anchor `variables`, lines 3751–3755.
- Evidence: variables reside in a state space; predicate variables may only be declared in register space.

### SF-9: `.reg` parameterized names
- Section 5.4.1 example, lines 3940–3944.
- Evidence: `.reg .b32 %r<100>;` form exists; indicates many concrete registers may be declared.

### SF-10: `st.param`/`ld.param` predication exception
- Section around 6257–6262.
- Evidence: st.param/ld.param argument-passing instructions cannot be predicated.

## 3. Proposed Lean architecture (bounded)

### D-1: Core instruction syntax abstraction
`or.b32` instruction syntax node has fields:
- `guard : Option Guard` (`none | some (pos pred) | some (neg pred)`).
- `dst : Operand`.
- `src1 : Operand`, `src2 : Operand`.
- Optional alias forms may reuse a bit-bucket destination (`_`) as per SF-4.

### D-2: Operand domain
- Operand is either:
  - register (typed name, bound to a state-space mapping), or
  - immediate/constant token.
- For this unit, destination may be only register or bit-bucket.

### D-3: Type/width layer
- Introduce constructors for `.b32` and `.pred` with explicit widths (32 and 1).
- Permit `.b32` operation only when all operands satisfy SF-1 and SF-2 constraints:
  - same size across operands,
  - same-type or compatibly-sized fundamental type as per SF-7.

### D-4: Machine state
- `State := { regFile : RegFile, predFile : PredFile }`.
- `PredFile` is separate from `RegFile` and keyed by predicate identifiers (because SF-6/5.4 restricts predicates to register space).
- No memory, branch state, or thread metadata in this bounded model.

### D-5: Execution relation
- `exec : State → GuardedOrB32 → State` (partial or total as design variant) with explicit outcome:
  - `executed` when guard true and operands satisfy typing/availability requirements,
  - `not_executed` when guard false,
  - `stuck` for ill-typed/ill-formed operand references.
- On `executed`, destination update is computed by bitwise-or operation on the two source values.

### D-6: Guard semantics
- `none` guard = true.
- `some (pos p)` guard = predicate value `p`.
- `some (neg p)` guard = logical negation of predicate value.
- `False` guard behavior: no state update (`not_executed`) (from SF-5/21840).

### D-7: Metadata
- Record PTX introduction/version provenance (`introduced = 1.0`) and target scope (`all architectures`) as properties of the bounded unit.

### D-8: Restriction boundaries
- This architecture assumes no special-case side effects for `or.b32` are introduced by sections outside 9.7.8.2.
- The `st.param`/`ld.param` non-predication restriction in SF-10 is treated as excluded by construction because it is stated only for those instructions (not for `or`).

## 4. Fact-to-design mapping

- SF-1 → D-1, D-3, D-5
- SF-2 → D-3
- SF-3 → D-1
- SF-4 → D-1 (candidate optional field), D-2
- SF-5 → D-6, D-5
- SF-6 → D-3, D-4
- SF-7 → D-3
- SF-8 → D-4
- SF-9 → D-4
- SF-10 → D-8

## 5. Dependency graph

1. **Types/values layer**
   - SF-6, SF-7, SF-8 → D-3, D-4
2. **Instruction syntax layer**
   - SF-3, SF-4 → D-1, D-2
3. **Predication layer**
   - SF-5 → D-6, D-5
4. **Execution semantics layer**
   - SF-1, SF-2, SF-5, D-1/D-2/D-3/D-4/D-6 → D-5
5. **Unit metadata layer**
   - SF-1, D-7

## 6. Assumptions

- ASS-1: A single global register namespace can represent both `.reg` bit-vector names and predicate names, with explicit partitioning by state map.
- ASS-2: The family-level statement “for some instructions destination is optional” (SF-4) is sufficient to allow `_` with `or.b32` unless later section-specific disallowance is found.
- ASS-3: No memory side effects are required from `or.b32`; this instruction is treated as pure register/predicate-domain computation.
- ASS-4: Predicate runtime values are interpreted as 2-state booleans for this bounded architecture (source text does not specify X/undefined predicate value state in this unit).
- ASS-5: This unit is isolated from exception-state and call/return calling-convention rules.

## 7. Open questions

- OPEN QUESTION (OQ-1): Is `_` destination explicitly permitted for `or` in any normative text beyond the general instruction description in 9.2?
- OPEN QUESTION (OQ-2): Are immediate literals in examples (`0x00010001`) resolved as `.b32`-typed literals in the parser/type checker of bounded architecture, or via separate literal-typing rules?
- OPEN QUESTION (OQ-3): What is the exact representation discipline for predicate values when lifted through bitwise OR (`.pred` operation) if we remain in a two-valued abstraction?
- OPEN QUESTION (OQ-4): Does this bounded architecture need explicit `stuck` vs malformed-program handling for missing declarations in one-step semantics, or can all inputs be assumed well-formed by construction?

## 8. Candidate theorem-obligation families

### Validation obligations
- **VAL-1 (Shape):** `or.b32` has exactly two source operands and one destination/bit-bucket.
- **VAL-2 (Guard syntax):** optional guard is either absent, positive predicate, or negated predicate.
- **VAL-3 (Type compatibility):** operands in a well-typed `or.b32` satisfy same-size requirement (SF-1 note + SF-2).
- **VAL-4 (Type-operator support):** `.pred`, `.b16`, `.b32`, `.b64` are admissible type annotations for syntax class; for this bounded unit only `.b32` and `.pred` are in active scope.
- **VAL-5 (Target/version metadata):** introduced-in and supported-on fields match SF-1.

### Proof obligations
- **PRF-1 (Guard-totality):** `guard_false` implies no state update.
- **PRF-2 (Determinism):** single-step execution of well-formed, well-typed `or.b32` is deterministic.
- **PRF-3 (Locality):** when execution occurs and destination is a register, only destination register/predicate updated.
- **PRF-4 (Bitwise result):** when execution occurs with well-typed operands, resulting destination value equals bitwise-or of source bits.
- **PRF-5 (Guard completeness):** execution occurs iff complete-guard evaluates true.
- **PRF-6 (No-op on bit-bucket):** when destination is `_`, state is unchanged.

## 9. Source evidence index and status

- [**SF-1**] HTML anchor `logic-and-shift-instructions-or`, 14290–14321: **Status: direct fact (confirmed)**
- [**SF-2**] HTML anchor `logic-and-shift-instructions`, 14240–14243: **Status: direct fact (confirmed)**
- [**SF-3**] HTML anchor `ptx-instructions`, 7515–7527: **Status: direct fact (confirmed)**
- [**SF-4**] HTML anchor `ptx-instructions`, 7534–7535: **Status: direct fact (confirmed)**
- [**SF-5**] HTML anchor `predicated-execution`, 7537–7550; control-flow `@`, 21834–21840: **Status: direct fact (confirmed)**
- [**SF-6**] HTML anchor `predicated-execution` + `register-state-space`, 7541, 2621–2624: **Status: direct fact (confirmed)**
- [**SF-7**] HTML anchor `fundamental-types`, 3019–3022, 3062–3066: **Status: direct fact (confirmed)**
- [**SF-8**] HTML anchor `variables`, 3751–3755: **Status: direct fact (confirmed)**
- [**SF-9**] HTML anchor `variable-declarations` example, 3940–3944: **Status: direct fact (confirmed)**
- [**SF-10**] HTML lines 6257–6262: **Status: direct fact (confirmed, negative rule for specific mnemonics only)**

Supporting project metadata:
- Source manifest: `documents/sources/nvidia/ptx/9.3/source-manifest.json` (specVersion 9.3, run run manifest hash path).

## 10. Gate A review checklist draft

- [ ] Scope limited to bounded architecture for `or.b32`.
- [ ] All statements are categorized only as **SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION**.
- [ ] Every SOURCE FACT has explicit source anchor or line references.
- [ ] Predicate/guard architecture is explicit for no guard, `@p`, and `@!p`.
- [ ] Validation obligations and proof obligations are present and non-vacuous.
- [ ] Dependency graph explains dependencies between type, syntax, predication, and execution.
- [ ] Open questions are explicit and unresolved where evidence is insufficient.
- [ ] No Lean code/theorems/axioms are introduced in this stage.
- [ ] No assumptions are unstated.

## 11. Explicitly unresolved

- UR-1: Whether `_` is formally required or merely allowed for `or.b32` by the generic optional-destination rule remains unresolved (see OQ-1).
- UR-2: Exact literal typing and literal normalization for immediate operands are not specified in the `or.b32` section.
- UR-3: Predicate value model (2-valued vs extended/proofs-opaque) is a design commitment outside explicit SF-1 text.
