# PTX `shl.b32` Foundation Architecture v4 — DRAFT (UNAPPROVED)

## 1) Scope

- **DESIGN CHOICE (SC-1):** Single-unit, language-wide architecture foundation for PTX ISA 9.3 instruction unit `shl.b32`.
- **DESIGN CHOICE (SC-2):** This artifact covers:
  - syntax/operands and type-parameter constraints,
  - declaration/typing assumptions needed for this unit,
  - optional predication/guards,
  - minimal execution-state model,
  - version/target metadata handling,
  - and candidate theorem-obligation families.
- **DESIGN CHOICE (SC-3):** Bounded scope excludes control-flow instructions, memory/state-space behavior outside `.reg`/`.pred`, inter-instruction sequencing, barriers, synchronization, concurrency model, and fault/exception taxonomy.
- **DESIGN CHOICE (SC-4):** This stage introduces no Lean code, parser, or proofs.
- **DESIGN CHOICE (SC-5):** This is an architecture artifact intended for Gate A review; it is not human-approved.

## 2) Official source facts

- `documents/sources/nvidia/ptx/9.3/source-manifest.json` (PTX 9.3, SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`).
- `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (index, SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`).

### 2.1 Fact inventory (source-backed)

- **SF-INS-SHL-1 (source-backed):** In section `logic-and-shift-instructions-shl`, heading `Logic and Shift Instructions: shl` (anchor `logic-and-shift-instructions-shl`, lines 14697–14730), syntax is `shl.type d, a, b;` with `.type = { .b16, .b32, .b64 }`; description says “Shift a left … by unsigned 32-bit value in b”; semantics block is `d = a << b`; note says shift amounts > register width `N` are clamped to `N`; destination and first source sizes must match; operand `b` must be 32-bit regardless of type; PTX notes introduced 1.0; target notes supported on all architectures; example `shl.b32 q,a,2;`.
- **SF-INS-GEN-1 (source-backed):** In `ptx-instructions` (anchor `ptx-instructions`, lines 7517–7527), PTX instructions optionally take 0–4 operands and may have an optional guard predicate on the left of opcode; in result-producing instructions, `d` is destination and `a,b,c` are sources.
- **SF-INS-GEN-2 (source-backed):** In the same section, one-line note states the destination may be optional via bit-bucket `_` for some instructions.
- **SF-PRED-1 (source-backed):** In `predicated-execution` (anchor `predicated-execution`, lines 7541–7549), predicate registers use `.pred`, may be declared as `.reg .pred p, q, r;`; all instructions have optional guard `@{!}p`; guarded instructions execute conditionally; unguarded instructions execute unconditionally.
- **SF-PRED-2 (source-backed):** In `instructions` (anchor `instructions`, lines 8722–8723), all PTX instructions may be predicated and optional guard is omitted from the per-instruction syntax description.
- **SF-PRED-3 (source-backed):** In `control-flow-instructions-at` (anchor `control-flow-instructions-at`, lines 21838–21839), predicated execution for guarded instruction form is explicitly described as “threads with a False predicate do nothing.”
- **SF-TYPE-1 (source-backed):** In `fundamental-types` (anchor `fundamental-types`, lines 3020–3022), register variables are of fundamental type and instruction type specifiers are shared with variable definitions.
- **SF-TYPE-2 (source-backed):** In `fundamental-types-fundamental-type-specifiers` (within the same section, lines 3040–3058), `.b16/.b32/.b64` are bit-size types; compatibility includes same basic type and size, and bit-size types are compatible with any fundamental of same size (lines 3062–3066).
- **SF-TYPE-3 (source-backed):** In `restricted-use-of-sub-word-sizes` (anchor, lines 3074–3078), `.u8/.s8/.b8` are restricted to listed instructions; `.b32` is not restricted there.
- **SF-REG-1 (source-backed):** In `register-state-space` (anchor `register-state-space`, lines 2617–2624), registers are fast storage in `.reg`, typed/typed/untyped; scalar widths include 8/16/32/64/128 bits; predicates are 1-bit; registers are non-addressable.
- **SF-DECL-1 (source-backed):** In `variables` (anchor `variables`, lines 3751–3755), every variable has declaration state space/type/name and predicates may only be declared in register state space.
- **SF-DECL-2 (source-backed):** In `parameterized-variable-names` (anchor, lines 3940–3944), `.reg .b32 %r<100>;` is shown as declaration syntax for many `%b32` names.

### 2.2 Evidence status

- All source facts in §2.1 are **read directly from official PTX 9.3 HTML/PDF sources**; none are inferred.

## 3) Proposed Lean architecture (design choices)

- **D-1 (instruction node):** Represent the bounded instruction form as a node with fields:
  - `ty : Type` (active bounded value `.b32`),
  - `guard : Option Guard`,
  - `dst : Operand`,
  - `srcA : Operand`,
  - `srcB : Operand`.
- **D-2 (bounded type scope):** For this unit, enforce `ty = .b32` in architecture validation. The family set `{.b16,.b32,.b64}` is retained only as reference metadata (from SF-INS-SHL-1), not as an active parse branch.
- **D-3 (operand arity and roles):** Operands are exactly three for this unit (`d,a,b`) in this order.
- **D-4 (destination form):** In this bounded architecture revision, `dst` is required (no `_`), because the unit syntax requires `d` and `_` permissiveness is only a general statement for “some instructions.”
- **D-5 (destination/source typing):** `dst` and `srcA` are required to be value registers in `.reg` space with compatibility constraints; for this bounded unit they must satisfy 32-bit-compatible operand sizing by source rules.
- **D-6 (source `b` typing):** `srcB` is required to be a 32-bit value (source rule), but its concrete source form (register/immediate/constant-expression) is represented as a bounded operand category with family-specific parser openness kept by a local constraint record; this is not resolved directly by the `shl.b32` syntax line.
- **D-7 (state):** A minimal machine state for this unit is:
  - `regFile : Name ↦ Value` for `.reg` scalar storage,
  - `predFile : Name ↦ Bool` for predicate registers,
  - optional `declMeta` mapping names to declared type/space metadata for validation (not required for execution step).
- **D-8 (predication):** Guard is interpreted from sectioned syntax:
  - no guard => true,
  - `@p` => value of predicate `p`,
  - `@!p` => logical negation.
- **D-9 (guard-false behavior):** If guard condition is false, the instruction does not write and state remains unchanged (no update branch). This uses SF-PRED-2 + SF-PRED-3 as the principal sources.
- **D-10 (execution result shape):** Single-step relation returns `executed` with update, or `skipped` when guard false; and `stuck` for out-of-scope malformed state/type violations.
- **D-11 (shift abstract operator):** Define execution effect via an abstract `Shl` operator constrained only by source requirements:
  - third-operand unsigned interpretation and
  - clamp-on-`N` amount discipline (with `N=32` in this unit),
  while leaving concrete bit-level representation choices to Lean mapping/theorem boundary.
- **D-12 (metadata):** Store unit metadata as `{introduced=1.0, target=all architectures, unit=shl.b32, specVersion=9.3}` for traceable record-keeping.

## 4) Fact-to-design mapping

- SF-INS-SHL-1 ⇒ D-1, D-2, D-3, D-5, D-6, D-11, D-12.
- SF-INS-GEN-1 ⇒ D-1, D-3, D-7, D-8, D-9, D-10.
- SF-INS-GEN-2 ⇒ D-4 (and explicitly NOT D-4 in source-unsupported sense).
- SF-PRED-1 / SF-PRED-2 ⇒ D-8, D-9.
- SF-PRED-3 ⇒ D-9 (as an operational source pattern).
- SF-TYPE-1 / SF-TYPE-2 / SF-TYPE-3 ⇒ D-2, D-5, D-7, D-11.
- SF-REG-1 / SF-DECL-1 / SF-DECL-2 ⇒ D-5, D-7, D-8, metadata model.

## 5) Dependency graph

- Syntax/operand constraints depend on: SF-INS-SHL-1, SF-INS-GEN-1, SF-INS-GEN-2.
- Operand typing and declaration constraints depend on: SF-TYPE-1, SF-TYPE-2, SF-REG-1, SF-DECL-1, SF-DECL-2.
- Predication constraints depend on: SF-PRED-1, SF-PRED-2, SF-PRED-3.
- Shift-clamp + metadata constraints depend on: SF-INS-SHL-1, SF-TYPE-2.

## 6) Register, value, and state foundations

- **D-S1:** Register storage is modeled as finite mappings in `.reg` with typed names/values; not addressable (matching register state-space).
- **D-S2:** Register value domain for this architecture is fixed by bounded scope to 32-bit width for active `.b32` semantics.
- **D-S3:** Predicates are separate boolean storage domain, backed by `.pred` declarations in `.reg`.
- **D-S4:** State equality for skipped steps is over all tracked state components (`regFile`, `predFile`, optional metadata map).

## 7) Operand architecture

- **D-O1:** Unit operand list is fixed as `d, a, b`.
- **D-O2:** `dst` and `srcA` are scalar value operands tied to `.reg` declarations.
- **D-O3:** `srcB` must be 32-bit valued; its source representation is parameterized to avoid overcommitting to register-only vs immediate-only before full grammar resolution.
- **D-O4:** No memory-address or surface-related operands in bounded unit state.

## 8) Predication architecture

- **D-P1:** Instructions are optionally guardable by `@p` / `@!p`.
- **D-P2:** `@p` and `@!p` semantics defined via predicate lookup + boolean negation.
- **D-P3:** Guard false yields no write and no state change in this bounded architecture.
- **D-P4:** Predicate inputs are expected to be declared `.pred` names in `.reg` state space.

## 9) Version and target representation

- **D-V1:** Unit metadata stores `(introducedIn = 1.0, target = all architectures, ptxVersion = 9.3, unit = shl.b32)`.
- **D-V2:** This metadata is non-executable and used for governance/proof obligations, not instruction semantics.

## 10) Candidate theorem-obligation families

### 10.1 Validation obligations (well-formedness)

- **VAL-1:** Unit parser/constructor is for `shl` with bounded active `.b32` in the `shl.b32` family context.
- **VAL-2:** Operand arity is exactly 3 (`d,a,b`); no additional operands.
- **VAL-3:** `dst` and `srcA` are `.reg` declared names of compatible widths with each other.
- **VAL-4:** `srcB` is 32-bit compatible.
- **VAL-5:** Guard target (if present) resolves to declared predicate in `.pred` declaration space.
- **VAL-6:** Unit metadata equals source-stated values (`introduced 1.0`, `supported all architectures`).

### 10.2 Semantic obligations (execution-relation properties)

- **PRF-1 (determinism):** For validated well-typed inputs, the single-step semantics relation is deterministic.
- **PRF-2 (guard correctness):** Guard true branch executes `d = shl(srcA, srcB)`; guard false gives `skipped`.
- **PRF-3 (locality):** A successful execution updates at most one value register (the destination) and does not change predicate state.
- **PRF-4 (typing preservation):** Destination updates remain compatible with bounded `.b32` constraints and source-check rules.
- **PRF-5 (clamp contract):** Shift-count handling obeys clamped-amount rule (`> N` clamped to `N`) with `N=32` for this unit.

## 11) Assumptions

- **ASS-1:** The explicit “do nothing” phrase from `control-flow-instructions-at` is treated as a generic predication behavior for false guards in this unit, though that section describes a control-flow mnemonic.
- **ASS-2:** Family-level `.b16/.b32/.b64` syntax is normalized to metadata-only context in this bounded `.b32` architecture.
- **ASS-3:** `stuck` is a bounded-model validation outcome for malformed or out-of-scope state; no PTX exception/fault semantics are claimed for this stage.

## 12) Ambiguities

- **AMB-1:** Is `b` in `shl.b32` always register/constant-expression in parse layer, or is this operand category mixed (register + immediate) by full PTX grammar?
- **AMB-2:** Whether `_` destination is actually accepted for `shl` specifically is unresolved at this bounded layer.
- **AMB-3:** Exact concrete Lean arithmetic witness for `clamp` plus shift operation is not fixed by source beyond source-text contract; only abstract constraints are sourced.
- **AMB-4:** Which state-map components must remain equal on skipped execution (only values vs all tracked metadata) is unresolved.

## 13) Open questions

- **OQ-1:** Resolve whether `shl` permits bit-bucket `_` destination in normative grammar for all forms, not just from generic section remark.
- **OQ-2:** Resolve canonical operand-form grammar for `b` (register, immediate, or both) within PTX parser rules for `shl` in this version.
- **OQ-3:** Decide canonical abstract-shift operator construction to witness clamped amount and 32-bit domain behavior in Lean without over-committing.
- **OQ-4:** Decide whether skipped-execution equality must include only runtime value maps or complete tracked metadata in this bounded model.

## 14) Evidence index

| ID | Source | Anchor/section | Lines | Evidence status |
|---|---|---|---:|---|
| E-SHL-1 | PTX HTML | `logic-and-shift-instructions-shl` / Logic and Shift Instructions: shl | 14697–14730 | read |
| E-GEN-1 | PTX HTML | `ptx-instructions` / PTX Instructions | 7517–7536 | read |
| E-PRED-1 | PTX HTML | `predicated-execution` / Predicated Execution | 7541–7550 | read |
| E-PRED-2 | PTX HTML | `instructions` / 9.7 Instructions | 8722–8723 | read |
| E-PRED-3 | PTX HTML | `control-flow-instructions-at` | 21834–21839 | read |
| E-TYPE-1 | PTX HTML | `fundamental-types` | 3019–3067 | read |
| E-TYPE-2 | PTX HTML | `restricted-use-of-sub-word-sizes` | 3074–3078 | read |
| E-REG-1 | PTX HTML | `register-state-space` | 2617–2624 | read |
| E-DECL-1 | PTX HTML | `variables` | 3751–3755 | read |
| E-DECL-2 | PTX HTML | `parameterized-variable-names` | 3940–3944 | read |
| E-META-1 | manifest | `documents/sources/nvidia/ptx/9.3/source-manifest.json` | lines 1–38 | read |
| E-META-2 | checksum index | `documents/sources/nvidia/ptx/9.3/SHA256SUMS` | lines 1–2 | read |

Source identity SHA summary: HTML=`e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`; manifest=`622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`; sums=`e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`.

## 15) Gate A review checklist

- [ ] Artifact is explicitly marked DRAFT and non-approved.
- [ ] Scope is bounded to `shl.b32` only.
- [ ] Official sources are traceable (document identity, anchor/section, lines, status).
- [ ] Source facts and design choices are separated.
- [ ] Design records assumptions, ambiguities, and open questions explicitly.
- [ ] Architecture includes syntax/operands, typing, register/predicate state, predication, execution shape, metadata.
- [ ] Candidate theorem obligations are non-vacuous and separated from validation checks.
- [ ] `d`-underscore support is not asserted without source confirmation.
- [ ] Shift semantics are not over-specified beyond sourced constraints (`<<` + clamp-to-`N`).
- [ ] Family-level `.b16/.b32/.b64` is bounded to `.b32` in active parser/type layer as intended.
