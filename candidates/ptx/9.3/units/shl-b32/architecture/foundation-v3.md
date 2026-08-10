# PTX `shl.b32` Foundation Architecture v3 — DRAFT (UNAPPROVED)

## 1) Scope
- **DESIGN CHOICE (SC-1):** Bounded language architecture for PTX ISA 9.3 construct `shl.b32` (single-instruction-family unit).
- **DESIGN CHOICE (SC-2):** Includes instruction shape, operand structure, type-compatibility constraints used by this unit, predication/guard model, minimal machine state (register + predicate), execution relation shape, metadata, and theorem-obligation families.
- **DESIGN CHOICE (SC-3):** Excludes control-flow scheduling, barriers, full program memory model, exceptions/interrupts, and semantics of other instruction families.
- **DESIGN CHOICE (SC-4):** This stage is architecture-only: no Lean definitions, parser, or proofs.
- **DESIGN CHOICE (SC-5):** Bounded active type for this unit is `.b32`; family-level `.b16/.b32/.b64` grammar is retained only as context for the family entry and not as required active type behavior.
- **DESIGN CHOICE (SC-6):** The artifact is explicitly not human-approved and is intended for Gate A review only.

## 2) Official source facts

Source identity:
- PTX 9.3 HTML: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`
- Source manifest: `documents/sources/nvidia/ptx/9.3/source-manifest.json`, SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`
- Hash index: `documents/sources/nvidia/ptx/9.3/SHA256SUMS`, SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`

- **SF-SHL-1 (direct):** `logic-and-shift-instructions-shl` (sec. 9.7.8.8), syntax `shl.type d, a, b;` with `.type={.b16,.b32,.b64}` and semantics `d = a << b;` lines 14705–14715.
- **SF-SHL-2 (direct):** `logic-and-shift-instructions-shl` notes: shift amounts > register width `N` are clamped to `N`; dst and first source sizes match; `b` is 32-bit regardless of instruction type; PTX/target notes introduced 1.0 / all architectures; example `shl.b32 q,a,2;` lines 14718–14729.
- **SF-INS-1 (direct):** `ptx-instructions` shows generic PTX forms and operand-role convention (`d` destination, `a,b,c` sources) and optional destination note with `_` may substitute destination; optional destination is stated for “some instructions.” lines 7517–7535.
- **SF-INS-2 (direct):** `instructions` states all PTX instructions may be predicated and optional guard omitted in syntax lines 8722–8723.
- **SF-PRED-1 (direct):** `predicated-execution` states optional `@{!}p` guard controls conditional execution and unguarded instructions execute unconditionally; predicate type is `.pred` lines 7547–7550.
- **SF-PRED-2 (direct):** `control-flow-instructions-at` describes `@{!}p instruction;` as predicated execution where False guard means do nothing lines 21834–21839.
- **SF-TYPE-1 (direct):** `fundamental-types` and table show `.pred`, `.b16`, `.b32`, `.b64`; bit-size types compatible with same-size fundamental type lines 3020–3066.
- **SF-TYPE-2 (direct):** `register-state-space` states `.reg` registers are scalar widths 8/16/32/64/128 bits (predicates 1 bit), typed/untyped, non-addressable, finite local names lines 2617–2627.
- **SF-DECL-1 (direct):** `variables` says declaration specifies state space/type/name and all variables reside in a state space; predicate vars only in register space lines 3751–3755.
- **SF-DECL-2 (direct):** `parameterized-variable-names` shows `.reg .b32 %r<100>;` pattern for b32 declarations lines 3940–3944.
- **SF-SUBWORD-1 (direct):** `restricted-use-of-sub-word-sizes` lists `.u8/.s8/.b8` restrictions in an instruction set that does not include `.b32`, relevant for compatibility interpretation only lines 3074–3076.

Evidence status: SF-SHL-1/SF-SHL-2/SF-INS-1/SF-INS-2/SF-PRED-1/SF-PRED-2/SF-TYPE-1/SF-TYPE-2/SF-DECL-1/SF-DECL-2/SF-SUBWORD-1 all read from source HTML.

## 3) Proposed Lean architecture (design choices)
- **D-1:** Represent a bounded instruction node with fields `{guard?, dst, srcA, srcB, ty}` and mnemonic tag in the `shl` family.
- **D-2:** Constrain bounded active type to `.b32` for this unit.
- **D-3:** Keep operand positions fixed and ordered as `(d, a, b)` per unit syntax.
- **D-4:** `dst` is required in the bounded unit syntax as written in SF-SHL-1. The generic `_` destination possibility is **not assumed** for this unit.
- **D-5:** Constrain `dst` and `srcA` to register operands in `.reg` storage.
- **D-6:** Constrain `srcB` to be 32-bit-valued. Category of `srcB` source form (register vs immediate) is marked unresolved: source text gives example literal `2` but no normative form grammar here.
- **D-7:** Model predication as optional guard annotation on instruction; absent guard = `true`, `@p` reads predicate value, `@!p` is negated predicate.
- **D-8:** State for this stage is `state := { regs, preds, declMeta }`, with `regs`/`preds` as maps from declared names to runtime values and `declMeta` preserving declared types/state spaces for validation.
- **D-9:** Execution relation is small-step over single instruction with result in {`executed`, `stuck`}; in `executed`, either guard succeeds and a target-state update happens (as defined by D-11), or guard-false means no state change (`skipped`), represented explicitly as a tagged result branch.
- **D-10:** Implement core shift as an abstract parameter `ShiftShiftOp` that enforces: (a) unsigned interpretation of `b` and (b) clamp of shift amount as required by SF-SHL-2, without committing bit-level/wrapping policy beyond that requirement.
- **D-11:** Type/compatibility checks include: destination/source size match between `d` and `a`; `srcB` is 32-bit valued requirement.
- **D-12:** Version/target metadata for this unit: `(introducedIn=1.0, target=all)`.
- **D-13:** Keep explicit unresolveds as separate items: `_` destination support for `shl`, operand-category of `b`, and full numeric representation consequences of out-of-range shift semantics.

## 4) Fact-to-design mapping
- **SF-SHL-1** ⇒ D-1, D-2, D-3, D-4
- **SF-SHL-2** ⇒ D-2, D-3, D-10, D-11, D-12
- **SF-INS-1** ⇒ D-1, D-3, D-8
- **SF-INS-2, SF-PRED-1** ⇒ D-7, D-9
- **SF-PRED-2** ⇒ D-9 (guard false no-op)
- **SF-TYPE-1, SF-SUBWORD-1** ⇒ D-11, D-12
- **SF-TYPE-2, SF-DECL-1, SF-DECL-2** ⇒ D-5, D-8, D-13
- **SF-DECL-1 (predicate restriction)** ⇒ D-7, D-8

## 5) Dependency graph
- Instruction syntax & role dependencies: SF-SHL-1 → D-1, D-2, D-3; SF-INS-1 → D-1; SF-INS-2/SF-PRED-1 → D-7
- Typing/value dependencies: SF-SHL-2 + SF-TYPE-1 + SF-TYPE-2 + SF-SUBWORD-1 → D-10, D-11
- Predication dependencies: SF-PRED-1 + SF-PRED-2 → D-7, D-9
- State/declaration dependencies: SF-TYPE-2 + SF-TYPE-1 + SF-DECL-1 + SF-DECL-2 → D-5, D-8
- Metadata dependencies: SF-SHL-2 (PTX notes/target notes) → D-12
- Uncertainty dependencies: SF-INS-1 optional `_` + absence of per-unit evidence for `_` in SF-SHL-1 and operand-form listing for `b` → unresolved design items OQ-1, OQ-2

## 6) Register, value, and state foundations
- **D-S1:** Register declarations are state-space typed and map names to runtime values; no address-of/register-addressability support in this bounded model.
- **D-S2:** Predicate values are separate from value registers; guards read predicate declarations.
- **D-S3:** Value domains are not fixed to a specific Lean representation at this stage; only size/type compatibility constraints from source are required.
- **D-S4:** For `shl.b32`, active size constraints require `dst` and `srcA` to be compatible at 32-bit width; `srcB` requires 32-bit value.
- **D-S5:** State equality for no-op transitions is over both `regs` and `preds` (and metadata if present), matching D-9 with explicit total-state no-change intent.

## 7) Operand architecture
- **D-O1:** Operands are exactly three for unit syntax: `d, a, b`.
- **D-O2:** `d` is a destination in this architecture revision.
- **D-O3:** `srcA` is source value operand and must satisfy source/destination size compatibility checks.
- **D-O4:** `srcB` is 32-bit shift-count value. Form as register/immediate is unresolved (OQ-2).
- **D-O5:** No immediate/indirect memory address or other non-scalar operands are in scope.

## 8) Predication architecture
- **D-P1:** Every bounded instruction may carry optional guard `@p` or `@!p`.
- **D-P2:** Guard evaluation: unguarded = true; `@p` = predicate value; `@!p` = not predicate.
- **D-P3:** On false guard, state transition may be represented as a `skipped` branch with no state updates.
- **D-P4:** Guarded execution therefore controls whether D-11 is applied.
- **D-P5:** This architecture treats predication as control behavior (not an exception/sync mechanism).

## 9) Version and target representation
- **D-V1:** Unit metadata is a structural record: `{unit="shl.b32", introduced="1.0", target="all architectures", specVersion="9.3"}`.
- **D-V2:** Metadata is non-normative to semantic clauses and is carried separately for documentation/proof obligations.

## 10) Candidate theorem-obligation families

Validation checks (structural / typing obligations):
- **VAL-1:** Unit syntax is exactly `shl.type d, a, b;` with active type context `.b32`.
- **VAL-2:** Operand roles are bound to `d,a,b` and no additional operands in this stage.
- **VAL-3:** Destination/source declarations require `.reg` storage; predicate declarations for guards are `.pred` in `.reg` per declaration rules.
- **VAL-4:** `dst` and `srcA` satisfy size compatibility and matching constraints; for this bounded unit this is 32-bit compatibility.
- **VAL-5:** `srcB` is a 32-bit value and compatible with shift-count requirement.
- **VAL-6:** Unit metadata fields match stated PTX notes.

Execution semantics obligations:
- **PRF-1 (determinism candidate):** For validated well-typed states, execution result is deterministic (`executed`/`skipped`/`stuck` unique).
- **PRF-2 (guard semantics):** Unconditionally true iff no guard or predicate evaluates true (negation handled for `@!p`); false implies skipped branch.
- **PRF-3 (frame locality):** In `executed`, only destination write target for `d` may change in `regs`; `preds` and other registers remain unchanged.
- **PRF-4 (shift relation):** In `executed`, destination value satisfies the unit’s `d = a << b` clause with unsigned-count handling and amount policy constrained by clamped-to-`N` behavior.
- **PRF-5 (well-formedness):** If execution is `executed`, resulting destination state is valid w.r.t. pre-state declaration metadata for `.b32`-bounded unit.

## 11) Assumptions / ambiguities / open questions and unresolved claims

### Assumptions
- **ASS-1:** For this bounded architecture, operand form of `b` is parameterized as `{reg | imm}` until unit grammar is clarified.
- **ASS-2:** The architecture models `stuck` as a validation-failure outcome for malformed declarations/typing, not as architecturally specified trap/exception behavior.
- **ASS-3:** Guard false is interpreted as full no-op over all tracked state components in this bounded model.

### Ambiguities
- **AMB-1:** SF-INS-1 says underscore destination is available for some instructions, but SF-SHL-1 unit syntax does not explicitly permit it.
- **AMB-2:** Unit text does not enumerate `srcB` as register/immediate syntax form.
- **AMB-3:** SF-SHL-2 constrains amount clamping but does not normatively define concrete bit-level numeric representation details for all corner cases.

### Open questions (unresolved)
- **OQ-1:** Is `_` destination legally admissible for `shl` in the normative grammar for all parser targets?
- **OQ-2:** Is `b` restricted to register operands only, immediate only, or both?
- **OQ-3:** What exact concrete shift operator encoding in Lean should witness the combination of “unsigned shift amount” and “clamp to N” without adding extra unproven behavior?
- **OQ-4:** Should skipped (false-guard) states preserve all metadata as exact equality, or only runtime value maps, in later stages?
- **OQ-5:** Can family-level active type `.b16/.b64` information be safely ignored in bounded `.b32` artifact without affecting downstream shared infrastructure?

## 12) Evidence index
| ID | Source fact | Anchor/section | Lines | Status |
|---|---|---|---:|---|
| E-1 | shl syntax/semantics/notes/example | `logic-and-shift-instructions-shl` | 14705–14729 | read |
| E-2 | optional predication and generic operands | `ptx-instructions` | 7517–7535 | read |
| E-3 | all instructions predicated (guard omitted in per-instruction form) | `instructions` | 8722–8723 | read |
| E-4 | predication description | `predicated-execution` | 7547–7550 | read |
| E-5 | predication false does nothing (control-flow example) | `control-flow-instructions-at` | 21834–21839 | read |
| E-6 | predicate declarations in .reg space | `predicated-execution` | 7541–7542 | read |
| E-7 | fundamental types and compatibility | `fundamental-types` / `fundamental-types-fundamental-type-specifiers` | 3019–3022, 3049–3067 | read |
| E-8 | register state space widths and non-addressability | `register-state-space` | 2617–2627 | read |
| E-9 | variable declarations and predicate-space restriction | `variables` | 3751–3755 | read |
| E-10 | .b32 parameterized naming example | `parameterized-variable-names` | 3940–3944 | read |
| E-11 | restricted subword note for `.b8/.s8/.b32` context | `restricted-use-of-sub-word-sizes` | 3074–3076 | read |
| E-12 | source-manifest metadata | `source-manifest.json` | 1–38 | read |
| E-13 | source hashes | `SHA256SUMS` | 1–2 | read |

## 13) Gate A review checklist
- [ ] Artifact scope is bounded to `shl.b32` and language-wide architecture needs only this unit.
- [ ] Source claims are traceable with document identity, version, anchor, and exact lines.
- [ ] Source facts/design choices/assumptions/ambiguities/open questions are clearly separated.
- [ ] No unsourced commitments about `_` destination for `shl`; this is treated as unresolved.
- [ ] Shift-domain behavior is not over-specified beyond sourced requirements (`<<` and clamp-to-`N`).
- [ ] Proposed state and predication architecture matches sourced syntax/control paragraphs.
- [ ] Dependency mapping and evidence index are complete.
- [ ] Candidate theorem obligations are non-vacuous and syntactically separate from validation checks.
- [ ] No Lean code/theorems/axioms are introduced in this stage.
