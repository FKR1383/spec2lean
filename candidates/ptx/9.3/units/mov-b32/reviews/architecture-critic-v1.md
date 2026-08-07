# Independent Architecture Critique — mov-b32-foundation-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md` (DRAFT — NOT HUMAN APPROVED), 280 lines.
- This critique is an independent semantic-critic review. It does not approve Gate A and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines).
- Source metadata consulted: `documents/sources/nvidia/ptx/9.3/source-manifest.json` and `documents/sources/nvidia/ptx/9.3/SHA256SUMS`.
- Run metadata consulted: `runs/ptx-9.3-mov.b32-f910feea/run.json` (unit `mov.b32`, stage ARCHITECTURE_CRITIQUE, revision 4).

## 2. Overall verdict

**SUITABLE for Human Gate A presentation (no substantive revision required).**

The artifact is a disciplined architecture draft. All 26 source facts (SF-M1..SF-M26) and the two negative search results were independently re-verified against the official HTML and are accurate. The four-label taxonomy (SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION) is used consistently; project status and bounded scope are correctly classified as metadata/design choices rather than source facts. The guard/predication architecture is stated uniformly via the complete guard expression for `@p` and `@!p`, avoiding the negated-guard phrasing defect found in the add.u32 foundation v1. Validation obligations are distinguished from proof obligations, and the proof-obligation families are relational (execution relation, not function), addressing the vacuity hazard from the add.u32 critique. The Gate A checklist honestly marks Gate A as NOT ready and accurately reflects the artifact's actual state.

Findings are limited to two MINOR evidence-index precision items, one MINOR vacuity-risk note on a candidate obligation family, and two NOTE-level observations (manifest/run metadata discrepancy; bounded base scope being a proper subset of the official `mov.b32` form). None of these require substantive changes to the architecture before it is presented for human Gate A review; they are refinements for the semantic phase and notes for the human reviewer.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md` — complete candidate read (280/280 lines).
- `runs/ptx-9.3-mov.b32-f910feea/run.json` — read in full (75 lines).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` — read in full (38 lines).
- `documents/sources/nvidia/ptx/9.3/SHA256SUMS` — read in full (3 lines).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools:
  - anchor `data-movement-and-conversion-instructions-mov` (line 14999) with lines 14989-15089 (scalar mov section 9.7.9.3);
  - anchor `data-movement-and-conversion-instructions-mov-2` (line 15075) with lines 15065-15165 (vector mov section 9.7.9.4);
  - anchor `data-movement-and-conversion-instructions` (line 14772) with lines 14770-14797 and span 14797-14840 (section 9.7.9 intro);
  - anchor `predicated-execution` (line 7537) with lines 7535-7577 (section 9.3);
  - anchor `ptx-instructions` (line 7513) with lines 7511-7543 (section 9.2);
  - anchor `instructions` (line 8718) with lines 8716-8733 (section 9.7 intro);
  - anchor `fundamental-types` (line 3015) with lines 3013-3070 (section 5.2.1 and Table 8);
  - anchor `register-state-space` (line 2613) with lines 2611-2638 (section 5.1.1);
  - anchor `special-register-state-space` (line 2633) with lines 2631-2643 (section 5.1.2);
  - anchor `variables` (line 3741) with lines 3739-3766 (section 5.4) and anchor `variable-declarations` (line 3747) with lines 3745-3755 (section 5.4.1);
  - anchor `parameterized-variable-names` (line 3933) with lines 3931-3955 (section 5.4.6);
  - anchor `format-and-semantics-of-instruction-descriptions` (line 7505) with lines 7503-7517 (section 9.1);
  - anchor `restricted-use-of-sub-word-sizes` (line 3070) with lines 3068-3085 (section 5.2.2);
  - anchor `statements` (line 1652) with lines 1650-1674 (section 4.3);
  - span 6252-6268 (`st.param`/`ld.param` predication exception);
  - literal search `@p mov` (0 matches);
  - literal search `mov.b32` (25 matches).
- Prior critique consulted as context: `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md` (findings F-1..F-10, used to check that the mov.b32 artifact applied those lessons).
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is an architecture candidate only. No semantic interpretation, source bundle, or Lean mapping was reviewed because none was provided at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | Evidence index E-16 (Section 14) | Line range 14772-14812 is one line short of the 9.7.9 intro extent (14772-14813) |
| F-2 | MINOR | SF-M22 (line 47), E-25 (Section 14) | The "variable declaration names..." sentence is at HTML lines 3753-3754, not line 3755 |
| F-3 | MINOR | PRF-6 (line 162), D-4/D-11 (Section 6) | Result-domain-membership obligation is likely vacuous under the proposed typed register-file representation |
| F-4 | NOTE | Section 1 metadata note (line 10) | Source manifest records `initial_formalization_unit` as `add.u32` while the run designates `mov.b32`; handled correctly as metadata but should be reconciled |
| F-5 | NOTE | D-0c, AMB-2, OQ-1 (Sections 1, 12, 13) | Bounded base unit covers only register/immediate sources of scalar `mov.b32`; the official form (and the canonical example `mov.b32 r1, %tid.x;`) also includes `sreg`, `avar`, `fname`, `kernel` sources — scope decision requires explicit human confirmation |

## 5. Findings detail

### F-1 — MINOR — Evidence index line range for the 9.7.9 intro is one line short

- **Exact location:** Section 14, evidence index entry E-16: "9.7.9 Data Movement and Conversion Instructions (intro) | `data-movement-and-conversion-instructions` | 14772-14812".
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 14772-14813: the section starts at anchor line 14772; the instruction list (including `tensormap.replace` at line 14812) closes with `</ul>` at line 14813; the next subsection 9.7.9.1 begins at line 14814.
- **Description:** The recorded range 14772-14812 covers the heading and all list content actually cited (SF-M13 quotes lines 14776-14780), so no cited fact is affected. The extent is technically 14772-14813.
- **Consequence:** Trivial traceability imprecision only; does not affect any semantic claim.
- **Required owner:** Semantic Extractor.
- **Required revision:** Optionally correct E-16 to 14772-14813 in a future revision; not required before Gate A.
- **Human review required:** No.

### F-2 — MINOR — SF-M22 quotes the variable-declaration sentence at the wrong line

- **Exact location:** Section 3, SF-M22 (line 47): "A variable declaration names the space in which the variable resides, its type and size, its name, an optional array size, an optional initializer, and an optional fixed address for the variable." (line 3755).
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 3753-3754 contain that sentence; line 3755 contains the predicate-only-in-register sentence. Both sentences are correctly quoted and correctly attributed to section 5.4.1/5.4 (E-25 covers 3741-3756).
- **Description:** The quoted text is at lines 3753-3754, not 3755. The predicate sentence at 3755 is quoted correctly. The evidence index E-25 range (3741-3756) is accurate.
- **Consequence:** Cosmetic line attribution error in a source fact; no content error.
- **Required owner:** Semantic Extractor.
- **Required revision:** Correct the line reference in SF-M22 in a future revision; not required before Gate A.
- **Human review required:** No.

### F-3 — MINOR — PRF-6 (result-domain membership) is likely vacuous under the proposed representation

- **Exact location:** Section 10, PRF-6 (line 162): "Result-domain membership: when the instruction executes, the value written to the destination lies in the 32-bit bit-size value domain of `.b32`."; related design choices D-4 (line 61) "a register file maps register names to values of their declared type" and D-11 (line 106) "the value domain for `.b32` is proposed as a fixed-width 32-bit untyped bit-value domain".
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 3019-3022 (register variables always of a fundamental type; instruction types), lines 3053-3054 (`.b32` is "Bits (untyped)").
- **Description:** Under D-4/D-11, the register file stores values of the declared register type; a `.b32` register by construction holds a value in the 32-bit bit-value domain. The execution relation then cannot produce an out-of-domain result unless ill-typed states are admitted, which the well-formed-state design (VAL-1/VAL-2) excludes. PRF-6 would therefore hold definitionally rather than as a meaningful property. The architecture's non-vacuity note ("it does not assert which specific bits are written") acknowledges the obligation is weak but does not resolve the vacuity question. The add.u32 foundation v1 critique (F-7) flagged exactly this class of hazard; the mov.b32 artifact resolved it for determinism (D-25 relational design) but PRF-6 retains a residual risk.
- **Consequence:** If PRF-6 survives unchanged into the theorem stage, it could violate the project's non-vacuous-theorem rule, or force a later weakening/removal.
- **Required owner:** Proof Engineer, with Semantic Extractor for the state representation decision.
- **Required revision:** In the semantic phase, either reclassify PRF-6 as a definitional/validation-style well-formedness obligation (like VAL-1/VAL-2) or state it over a value domain in which membership is non-trivial (e.g., a looser storage representation with a separate width predicate). Not required before Gate A because Section 10 explicitly records PRF-6 as a candidate family with no Lean statement yet.
- **Human review required:** Yes (at the semantic/theorem-strength gate).

### F-4 — NOTE — Manifest/run unit discrepancy is documented but should be reconciled

- **Exact location:** Section 1, metadata note (line 10); `documents/sources/nvidia/ptx/9.3/source-manifest.json` lines 9-15; `runs/ptx-9.3-mov.b32-f910feea/run.json` line 7.
- **Relevant official evidence:** Manifest `initial_formalization_unit` = `add.u32` (lines 9-15); run metadata `unit` = `mov.b32`.
- **Description:** The source manifest still records `add.u32` as the initial formalization unit while this run formalizes `mov.b32`. The architecture correctly identifies this as project metadata (not specification evidence), notes that the orchestrator contract makes run metadata authoritative, and does not treat the manifest record as evidence about `mov`. The handling is correct.
- **Consequence:** No semantic impact; a residual project-metadata inconsistency that could confuse future traceability queries if left unaddressed.
- **Required owner:** Orchestrator / Source Curator.
- **Required revision:** Update the manifest `initial_formalization_unit` record (or add a per-run override) when convenient; not an architecture defect.
- **Human review required:** No.

### F-5 — NOTE — Bounded base unit is a proper subset of the official `mov.b32` form; human must confirm the scope decision

- **Exact location:** D-0c (line 9), AMB-2 (line 181), OQ-1 (line 186), SF-M14 (line 39), SF-M2 (line 27).
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 15008-15015 (scalar mov syntax with `sreg`, `avar`, `avar+imm`, `fname`, `kernel` forms), lines 15026-15027 (operand `a` may be register, special register, variable, or function name), line 1663 (`mov.b32 r1, %tid.x;` with special-register source).
- **Description:** The official scalar `mov.b32` form includes source categories beyond register/immediate: `sreg` (exemplified by the canonical `mov.b32 r1, %tid.x;`), `avar`, `avar+imm`, `fname`, and `kernel`. The architecture's bounded base unit covers only register/immediate sources and records the rest as out of scope (AMB-2, OQ-1). This is a transparent, documented scope decision, and the artifact explicitly notes that the canonical spec example uses an `sreg` source that is out of the bounded base scope (SF-M14). Because the run unit name `mov.b32` is broader than the bounded base unit, the human Gate A reviewer must explicitly confirm this scope reduction as the intended base-unit interpretation.
- **Consequence:** None if the human approves the bounded scope; otherwise the base unit would need to include the `sreg` source category and the special-register state space.
- **Required owner:** Human Gate A reviewer (scope decision); Semantic Extractor for future `sreg`-form units (OQ-1).
- **Required revision:** No artifact change required; this is a decision point for the human gate. The artifact already flags it.
- **Human review required:** Yes (this is precisely the kind of decision Gate A is for).

## 6. Source-verification notes

Specification-tool calls used in this critique: 10 restricted reads/searches (all verified directly).

All explicit SOURCE FACT claims (SF-M1..SF-M26) were re-verified and are accurate against the official HTML and manifest:

- SF-M1: anchor `data-movement-and-conversion-instructions-mov` at line 14999; section 9.7.9.3 spans 14999-15074. Confirmed.
- SF-M2: scalar mov syntax lines 15008-15015; type set lines 15017-15021 includes `.b32`. Confirmed.
- SF-M3: description lines 15004-15005 ("Set a register variable with the value of a register variable or an immediate value.") and lines 15025-15027 ("Write register `d` with the value of `a`."; operand categories). Confirmed.
- SF-M4: address semantics lines 15028-15034. Confirmed.
- SF-M5: Semantics block `d = a;` etc. at lines 15039-15042. Confirmed.
- SF-M6: Notes lines 15047-15052 (bit-size types required; kernel/function type restriction). Confirmed.
- SF-M7: PTX ISA Notes lines 15055-15058 ("Introduced in PTX ISA version 1.0."). Confirmed.
- SF-M8: Target ISA Notes lines 15060-15061 (`mov.f64` requires `sm_13+`; kernel addresses `sm_35+`); no family restriction for scalar `mov.b32` in the section. Confirmed.
- SF-M9: Examples lines 15064-15071 incl. `mov.f32 k,0.1;`. Confirmed.
- SF-M10: anchor `data-movement-and-conversion-instructions-mov-2` at line 15075; section 9.7.9.4 spans 15075-15152; type set `{ .b16, .b32, .b64, .b128 }` at line 15085. Confirmed.
- SF-M11: vector notes lines 15091-15095; PTX ISA Notes lines 15136-15137 (1.0; `.b128` in 8.3); Target ISA Notes lines 15139-15140 ("Supported on all target architectures."; `.b128` requires `sm_70+`). Confirmed.
- SF-M12: vector examples lines 15143-15149. Confirmed.
- SF-M13: 9.7.9 intro anchor at 14772; quoted sentence at lines 14776-14780. Confirmed.
- SF-M14: anchor `statements` at 1652; `.reg .b32 r1, r2;` at line 1660; `mov.b32 r1, %tid.x;` at line 1663 (`%tid.x` is a special register). Confirmed.
- SF-M15: anchor `instructions` at 8718; "All PTX instructions may be predicated." at lines 8722-8723. Confirmed.
- SF-M16: anchor `predicated-execution` at 7537; predicate registers virtual/`.pred` at 7541-7542; guard syntax `@{!}p` and unconditional-execution rule at 7547-7550; setp note 7551-7552; examples `@p add.s32 j, j, 1;` at 7562 and `@!p bra L1;` at 7570. Confirmed.
- SF-M17: anchor `ptx-instructions` at 7513; 0-4 operands plus guard at 7517-7518; destination/source roles at 7526-7527; bit bucket at 7534-7535. Confirmed.
- SF-M18: anchor `fundamental-types` at 3015; register variables of fundamental type at 3019-3022; Table 8 anchor at 3025; `.b32` under "Bits (untyped)" at 3053-3054; `.pred` at 3057-3058. Confirmed.
- SF-M19: compatibility rules at lines 3062-3066 ("The bit-size type is compatible with any fundamental type having the same size."). Confirmed.
- SF-M20: anchor `register-state-space` at 2613; registers fast storage at 2617; widths and 1-bit predicate at 2621-2624; not fully addressable at 2626-2627; ABI/function-scope and legacy notes at 2627-2631. Confirmed.
- SF-M21: anchor `special-register-state-space` at 2633; `.sreg` state space at 2637-2639. Confirmed.
- SF-M22: anchor `variables` at 3741; declaration rule at 3753-3754; predicate-only-in-register at 3755. Content confirmed (line attribution: see F-2).
- SF-M23: anchor `parameterized-variable-names` at 3933; `%r<100>` example at 3940-3943; shorthand rule at 3946-3947. Confirmed.
- SF-M24: anchor `format-and-semantics-of-instruction-descriptions` at 7505; quoted text at 7509-7511. Confirmed.
- SF-M25: `st.param`/`ld.param` predication exception at lines 6260-6261. Confirmed.
- SF-M26: anchor `restricted-use-of-sub-word-sizes` at 3070; restriction list at 3074-3075; `.b32` not in the list. Confirmed.
- Negative search `@p mov`: 0 matches. Confirmed.
- Negative search `mov.b32`: 25 matches; sampled matches at lines 1663, 12621-12950 (vector pack usages), and 15143-15149 (vector examples) match the artifact's description. Confirmed.
- Document hashes and line counts match the tool metadata and manifest: HTML SHA-256 `e2095c4a...`, 47,743 lines; manifest SHA-256 `622e6ce0...`, 38 lines; SHA256SUMS SHA-256 `e02f4fead...`, 3 lines (HTML and PDF hashes recorded). Confirmed.

No SOURCE FACT mislabeling, phantom cross-references, or inaccurate Gate A checklist items were found. The four-label taxonomy is used consistently (no OBSERVATION or other fifth label). Project status and bounded scope are labeled as DESIGN CHOICE/metadata, not SOURCE FACT (add.u32 F-1 lesson applied). Guard-false behavior is stated uniformly via the complete guard expression with no "negated guard true means no-op" phrasing (add.u32 F-5/F-6 lessons applied). Register/value/state foundations are grounded in actual register-chapter reads (add.u32 F-3/F-9 lesson applied).

## 7. Required revisions (consolidated)

No substantive revisions are required before Gate A. Optional refinements:

1. Correct E-16 line range to 14772-14813 and SF-M22 line attribution to 3753-3754 (F-1, F-2) — cosmetic evidence-index precision.
2. In the semantic phase, reclassify PRF-6 as definitional/validation or reformulate it over a domain that makes membership non-trivial (F-3).
3. Reconcile the manifest `initial_formalization_unit` metadata with the `mov.b32` run (F-4) — orchestrator-level, not architecture-level.
4. Obtain explicit human confirmation of the bounded base scope (register/immediate only) for Gate A (F-5).

## 8. Residual open questions

- Is the value-domain membership obligation (PRF-6) meaningful under the eventual Lean state representation, or should it be a definitional well-formedness check (F-3)?
- Will the human Gate A reviewer confirm that the bounded base unit (register/immediate sources only) is the intended `mov.b32` unit, or should the `sreg` source category be included in the base unit (F-5, OQ-1)?
- The exact Lean encoding of the 1-bit predicate register domain (OQ-5) and the exact bit-size compatibility formulation for operand typing (OQ-7) remain deferred to the semantic phase; both were re-confirmed as genuinely open in the official text read.
- The guard-false "no state update" interpretation (A-4, OQ-3) remains an assumption based on the "controls conditional execution" wording; it requires human approval and re-verification at the semantic phase.

## 9. Gate A readiness assessment

Ready for presentation to Human Gate A. The draft is a disciplined, source-faithful architecture with all citations verified, correct classification discipline, honest ambiguity/open-question records, and an accurate Gate A checklist. The MINOR findings (F-1, F-2) are cosmetic; F-3 is a candidate-obligation refinement for the semantic phase; F-4 and F-5 are notes requiring orchestrator/human attention, not artifact revision. This assessment is not a Gate A approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md`. No Lean code was written, and no `mov.b32` copy semantics were extracted during this review. No gates were approved and nothing was promoted to `accepted/`.
