# PTX cnot.b32 Foundation Architecture v1 — DRAFT — NOT HUMAN APPROVED

## 1. Revision status and bounded scope

Status note (project metadata, not specification evidence): this artifact is a bounded architecture draft for the automated run `ptx-9.3-cnot.b32-96465672` and is marked `DRAFT — NOT HUMAN APPROVED`. It is not promoted to `accepted/`, and it does not claim Gate A readiness.

- DESIGN CHOICE (D-0) — Scope is language-wide foundations required for future formalization of instruction `cnot.b32` only: instruction representation, type/size model, operands, registers and values, minimal machine state, guard/predication, result metadata (version/target), traceability, and candidate validation/theorem families.
- DESIGN CHOICE (D-0b) — This artifact describes architecture only; no Lean code and no instruction-level proof obligations are fully formalized yet.
- DESIGN CHOICE (D-0c) — `cnot.b32` denotes the scalar 32-bit form `cnot.type d, a;` under `logic-and-shift-instructions-cnot`, with `.type = { .b16, .b32, .b64 }`.

## 2. Inputs and critique context

- Run metadata: `runs/ptx-9.3-cnot.b32-96465672/run.json` (unit `cnot.b32`, stage `ARCHITECTURE`).
- Source identity evidence: `documents/sources/nvidia/ptx/9.3/source-manifest.json` and `documents/sources/nvidia/ptx/9.3/SHA256SUMS`.
- Official specification text: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`.
- No prior `cnot.b32` architecture artifact exists under `candidates/ptx/9.3/units/cnot-b32` at the time of this attempt.

## 3. Official source facts

Primary source: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, NVIDIA PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`.

- SOURCE FACT (SF-C1) — The logic and shift family section (`logic-and-shift-instructions`, anchor `logic-and-shift-instructions`, lines 14236–14255) states the family is “fundamentally untyped” and performs bit-wise operations on same-size operands; it lists `and`, `or`, `xor`, `not`, `cnot`, `lop3`, `shf`, `shl`, `shr` (lines 14240–14255).
- SOURCE FACT (SF-C2) — The `cnot` subsection exists at anchor `logic-and-shift-instructions-cnot` and has heading `Logic and Shift Instructions: cnot`.
- SOURCE FACT (SF-C3) — `cnot` syntax is `cnot.type d, a;` with `.type = { .b16, .b32, .b64 }` (lines 14400–14403).
- SOURCE FACT (SF-C4) — `cnot` is described as “C/C++ style logical negation.” and as “Compute the logical negation using C/C++ semantics.” (lines 14406–14407).
- SOURCE FACT (SF-C5) — `cnot` semantics are `d = (a==0) ? 1 : 0;` (lines 14409–14410).
- SOURCE FACT (SF-C6) — `cnot` notes include “The size of the operands must match, but not necessarily the type.” (line 14413).
- SOURCE FACT (SF-C7) — `cnot` PTX ISA note: “Introduced in PTX ISA version 1.0.” (line 14415).
- SOURCE FACT (SF-C8) — `cnot` target note: “Supported on all target architectures.” (line 14417).
- SOURCE FACT (SF-C9) — `cnot` provides an example `cnot.b32 d,a;` (line 14420).
- SOURCE FACT (SF-C10) — Family intro specifically says only `and`, `or`, `xor`, and `not` operate on predicates (lines 14242–14243). `cnot` is listed among instructions but not in that predicate-operates subgroup.
- SOURCE FACT (SF-C11) — PTX instruction descriptions omit optional guard predicate in syntax: “All PTX instructions may be predicated… optional guard predicate is omitted” (section `instructions`, lines 8722–8723).
- SOURCE FACT (SF-C12) — Predication details: predicate registers are `.pred` and are virtual; all instructions have optional guard `@{!}p`; unguarded instructions execute unconditionally; `@p`/`@!p` control execution; examples are provided (section `predicated-execution`, lines 7547–7550 and 7562,7570).
- SOURCE FACT (SF-C13) — PTX instructions generally have an optional guard after `@`, destination `d`, and sources `a,b,c`; bit bucket `_` may denote optional destination (`_`) (section `ptx-instructions`, lines 7517–7518, 7526–7527, 7534–7535).
- SOURCE FACT (SF-C14) — Fundamental types include `.b16/.b32/.b64` as bits basic type under “Fundamental Type Specifiers” and type-specifier compatibility is defined (section `fundamental-types`, lines 3025–3066).
- SOURCE FACT (SF-C15) — `b`-width register values are possible for scalar registers and predicate registers are 1-bit (`.pred`) and stored in `.reg` state space (section `register-state-space`, lines 2617–2624).
- SOURCE FACT (SF-C16) — Predicate variables may only be declared in register state space (section `variables`, line 3755).
- SOURCE FACT (SF-C17) — `.b32` is not in the restricted sub-word list (`.u8`, `.s8`, `.b8` are restricted to specific instructions) (section `restricted-use-of-sub-word-sizes`, lines 3070–3076).
- SOURCE FACT (SF-C18) — The official sources and section indexes used in this pass were read; no PDF lines were opened (`documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.pdf` not read).

Negative evidence (literal search):

- SEARCH FACT (SF-C19) — `@p cnot` returned 0 matches in `ptx_isa_9.3.html`.
- SEARCH FACT (SF-C20) — `cnot.pred` returned 0 matches.
- SEARCH FACT (SF-C21) — `cnot.b32` returned 1 match (the section example `cnot.b32 d,a;`, line 14420).

## 4. Proposed minimal Lean architecture (design decisions)

- DESIGN CHOICE (D-1) — Instruction AST: `PTXInstr` constructor for `cnot` with fields:
  `(guard : Option Guard) (ty : BitType) (dst : Operand) (src : Operand)`;
  where type is fixed to `.b32` for this bounded unit.
- DESIGN CHOICE (D-2) — Operand model for bounded base: destination and source operands are register references by default; immediate source is an unresolved design question (see OQ-1).
- DESIGN CHOICE (D-3) — Type model: minimal mapping of relevant fundamental types, at least `{Bit16, Bit32, Bit64}` and `{Pred}`; for `cnot.b32`, operand/result width is 32.
- DESIGN CHOICE (D-4) — Register/value model: register file maps names to values tagged by declared fundamental type; values for `.b32` form use fixed-width 32-bit bit-value domain; predicate values are 1-bit/Boolean-like domain.
- DESIGN CHOICE (D-5) — Minimal state: value-register file plus predicate-register file; no memory/shared/special-register state required for the base instruction form.
- DESIGN CHOICE (D-6) — Execution relation consumes `(state, cnot_inst)` and either updates destination (or none under bit-bucket if chosen) or returns unchanged state under guard-false.
- DESIGN CHOICE (D-7) — Predication: explicit optional guard `@p` / `@!p` evaluated from predicate register; no-guard executes unconditionally.
- DESIGN CHOICE (D-8) — Outcome type: at least `{exec : State, guardFalse : State}` for bounded unit; no error constructor yet, since no exception behavior is in `cnot` section.
- DESIGN CHOICE (D-9) — Version/target metadata for the unit: introduced-in PTX ISA 1.0, supported on all target architectures.
- DESIGN CHOICE (D-10) — All semantic claims include traceability metadata (`document`, `version`, `section heading`, `anchor`, `lines`, `sha256`).

## 5. Fact-to-design mapping

| Source fact | Architecture component |
|---|---|
| SF-C2, SF-C3, SF-C11, SF-C12, SF-C13 | D-1, D-6, D-7 |
| SF-C3, SF-C2, SF-C5, SF-C9 | D-2 |
| SF-C14, SF-C17 | D-3 |
| SF-C14, SF-C15, SF-C16 | D-4 |
| SF-C3, SF-C15 | D-5 |
| SF-C5, SF-C12 | D-6 |
| SF-C12, SF-C13 | D-7 |
| SF-C18, SF-C8 | D-8 |
| SF-C7, SF-C8 | D-9 |
| SF-C1, SF-C2, SF-C3, SF-C5 | D-10 |

## 6. Dependency graph

- D-1 depends on general syntax/predication text (`SF-C3`, `SF-C11`, `SF-C12`, `SF-C13`) and cnot syntax (`SF-C3`).
- D-2 depends on operand conventions (`SF-C3`, `SF-C9`) and instruction-format text (`SF-C13`).
- D-3 depends on fundamental-types (`SF-C14`) and sub-word restriction context (`SF-C17`).
- D-4 and D-5 depend on register/value declarations and `.pred` scope (`SF-C15`, `SF-C16`).
- D-6, D-7, D-8 depend on cnot semantics (`SF-C5`) and predication (`SF-C12`, `SF-C13`).
- D-9 depends on PTX and Target ISA notes (`SF-C7`, `SF-C8`).

## 7. Register, value, and state foundations

- DESIGN CHOICE (D-11) — Register references are names in register-file maps; no address-taking semantics are required.
- DESIGN CHOICE (D-12) — Value domain for `cnot.b32` is 32-bit bit-value; predicate domain is two-valued logic.
- DESIGN CHOICE (D-13) — State combines register map for general values and predicate map.
- DESIGN CHOICE (D-14) — The instruction-local architecture does not model memory hierarchy, launch metadata, or special state spaces.

## 8. Operand architecture

- DESIGN CHOICE (D-15) — `cnot.b32` base form has exactly two explicit operands in order `d, a`.
- DESIGN CHOICE (D-16) — The destination operand is a declared register target (or `_` only if enabled by semantic phase, see OQ-2).
- DESIGN CHOICE (D-17) — The source operand `a` is a declared register for bounded base modeling, with optional extension to immediate pending OQ-1.

## 9. Predication architecture

- DESIGN CHOICE (D-18) — Complete guard expression:
  - no guard ⇒ true;
  - `@p` ⇒ value of `p`;
  - `@!p` ⇒ negation of `p`.
- DESIGN CHOICE (D-19) — Execute iff guard expression is true; otherwise no-state-change outcome.
- DESIGN CHOICE (D-20) — Guard register type for this architecture is `.pred` and must be declared in register state.

## 10. Version and target representation

- DESIGN CHOICE (D-21) — Represent version constraints as introduced-in PTX 1.0 (from SF-C7).
- DESIGN CHOICE (D-22) — Represent target coverage as "all target architectures" (from SF-C8).

## 11. Candidate theorem-obligation families

Validation obligations:

| ID | Obligation | Kind |
|---|---|---|
| VAL-1 | `.b32` is a valid size type and is compatible with this instruction instantiation. | validation |
| VAL-2 | Operand typing: destination and source operands are size-compatible with `.b32` and the “size-match” rule holds for cnot (not necessarily same basic type). | validation |
| VAL-3 | Guard, if present, is a declared `.pred` source. | validation |
| VAL-4 | Destination is declared or (if adopted) bit-bucket `_`; bit-bucket applicability to `cnot.b32` is unresolved (OQ-2). | validation |
| VAL-5 | Unit version metadata equals PTX ISA 1.0 and target metadata equals all architectures. | validation |

Proof obligations (candidate families):

| ID | Obligation |
|---|---|
| PRF-1 | Determinism: at most one resulting state for well-typed instruction and input state. |
| PRF-2 | Destination frame: executing `cnot.b32` changes only destination state (if not `_`), no unrelated register/predicate change. |
| PRF-3 | Guard behavior correspondence: executes exactly when complete guard is true; otherwise unchanged state. |
| PRF-4 | Bit-bucket frame (if adopted): `_` causes no value-register update. |
| PRF-5 | Fidelity: when executing, destination equals `(a == 0) ? 1 : 0` under the model’s value and constant-casting conventions. |

## 12. Assumptions

- ASSUMPTION (A-1) — The HTML source text is treated as the canonical evidence for this unit in this run; PDF was not used.
- ASSUMPTION (A-2) — Instruction-local semantics (single-step transition) is a sufficient architecture baseline for `cnot.b32`.
- ASSUMPTION (A-3) — `cnot.b32` has no separate exception/error edge in the bounded text; outcome is either executed or guard-false no-op.
- ASSUMPTION (A-4) — No `.pred`-typed `cnot` form is part of this bounded unit because `.type` list omits `.pred`.
- ASSUMPTION (A-5) — The bounded notation `cnot.b32 d,a` is interpreted as a single-instruction form where `d` and `a` are values in the register or immediate universe as resolved in semantic phase.

## 13. Ambiguity points (OPEN QUESTIONS)

| Ambiguity point | Label | Status |
|---|---|---|
| Whether source operand `a` may be an immediate in `cnot.b32` (no direct `cnot` immediate example is shown). | OQ-1 | Open |
| Whether the bit-bucket `_` destination is legal for `cnot.b32` (only generic rule mentions `_` in `ptx-instructions`). | OQ-2 | Open |
| Whether the constants `1` and `0` in the semantics are width-lifted to `.b32` explicitly or via a coercion rule. | OQ-3 | Open |
| Whether guard-false semantics is strictly strict no-state-change (the text states conditional execution but does not define exact no-op state relation). | OQ-4 | Open |

## 14. Evidence index

| # | Section heading | Anchor | Lines | Source | SHA-256 | Status |
|---|---|---|---|---|---|---|
| E-C1 | source-manifest metadata | n/a | manifest lines 1–38 | manifest | `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2` | Read |
| E-C2 | Logic and Shift Instructions (family intro) | `logic-and-shift-instructions` | 14236–14255 | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Read |
| E-C3 | Logic and Shift Instructions: cnot | `logic-and-shift-instructions-cnot` | 14392–14423 | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Read |
| E-C4 | Instructions (predicate-omitted syntax) | `instructions` | 8718–8723 | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Read |
| E-C5 | Predicated Execution | `predicated-execution` | 7537–7550,7562,7570 | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Read |
| E-C6 | PTX Instructions | `ptx-instructions` | 7513–7536 | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Read |
| E-C7 | Fundamental Types | `fundamental-types` | 3025–3066 | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Read |
| E-C8 | Register State Space | `register-state-space` | 2613–2631 | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Read |
| E-C9 | Variables | `variables` | 3741–3755 | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Read |
| E-C10 | Restricted Use of Sub-Word Sizes | `restricted-use-of-sub-word-sizes` | 3070–3076 | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Read |
| E-C11 | `@p cnot` literal search | n/a | n/a | HTML | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | Search |
| E-C12 | `cnot.pred` literal search | n/a | n/a | HTML | same | Search |
| E-C13 | `cnot.b32` literal search | n/a | line 14420 | HTML | same | Search |

## 15. Gate A review checklist (candidate)

- [ ] Artifact is explicitly marked `DRAFT — NOT HUMAN APPROVED` and not in `accepted/`.
- [ ] Scope is bounded to `cnot.b32` and declares only architecture-level foundations.
- [ ] All statements are labeled as SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION.
- [ ] Every SOURCE FACT has a corresponding evidence-index entry with anchor and line span.
- [ ] Predication model uses complete-guard formulation for `@p` and `@!p`.
- [ ] Operand, typing, state, and version/target foundations are minimal and bounded to the instruction local semantics.
- [ ] Open questions and assumptions are explicit and unresolved.
- [ ] Candidate proof obligations are relational and non-vacuous where possible.
