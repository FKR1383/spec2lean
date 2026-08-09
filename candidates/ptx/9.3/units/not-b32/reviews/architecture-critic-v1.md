# Independent Architecture Critique — not-b32-foundation-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/not-b32/architecture/foundation-v1.md` (DRAFT — NOT HUMAN APPROVED), 271 lines.
- This critique is an independent semantic-critic review. It does not approve Gate A and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines).
- Source metadata consulted: `documents/sources/nvidia/ptx/9.3/source-manifest.json` and `documents/sources/nvidia/ptx/9.3/SHA256SUMS`.
- Run metadata consulted: `runs/ptx-9.3-not.b32-c454d1bc/run.json` (unit `not.b32`, stage ARCHITECTURE_CRITIQUE, revision 2).
- Prior critiques consulted as context: `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md` (findings F-1..F-10) and `candidates/ptx/9.3/units/mov-b32/reviews/architecture-critic-v1.md` (findings F-1..F-5), used to check that the not.b32 artifact applied those lessons.

## 2. Overall verdict

**REVISE (one MAJOR taxonomy-discipline defect; all source evidence verified accurate).**

The artifact is a careful, source-faithful architecture draft. All 22 source facts (SF-N1..SF-N22), all six literal-search claims (E-26), all evidence-index line ranges, and all document hashes were independently re-verified against the official HTML and are accurate. The scope bounding to the scalar `.b32` form of `not` (9.7.8.4) is documented transparently. Register/value/state foundations are grounded in actual register-chapter reads. Guard/predication is stated uniformly via the complete guard expression, avoiding the negated-guard phrasing defect found in the add.u32 foundation v1. Validation obligations are distinguished from proof obligations, and proof-obligation families are relational and non-vacuous by design.

One substantive defect requires reconciliation before the artifact may be presented for human Gate A: the artifact claims to use exactly four labels (SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION) in Section 15 and in its own Gate A checklist (Section 16), yet Section 12 introduces a fifth label `AMBIGUITY (AMB-1..AMB-3)`. This is the same class of taxonomy drift the add.u32 F-2 lesson was created to prevent, and it makes the artifact's own checklist item literally unsatisfied. The fix is narrow (see F-1), but it is required for the artifact to be self-consistent.

All other findings are MINOR or NOTE level and do not require changes before Gate A.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/not-b32/architecture/foundation-v1.md` — complete candidate read (271/271 lines).
- `runs/ptx-9.3-not.b32-c454d1bc/run.json` — read in full (61 lines).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` — read in full (38 lines).
- `documents/sources/nvidia/ptx/9.3/SHA256SUMS` — read in full (3 lines).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools:
  - anchor `logic-and-shift-instructions-not` (line 14358) with lines 14353-14403 (section 9.7.8.4, full `not` section);
  - anchor `logic-and-shift-instructions` (line 14236) with lines 14231-14261 (section 9.7.8 intro and instruction list);
  - anchor `logic-and-shift-instructions-or` (line 14290) with lines 14288-14325 (section 9.7.8.2; immediate example at 14319);
  - anchor `logic-and-shift-instructions-xor` (line 14324) with lines 14322-14362 (section 9.7.8.3; immediate example at 14354);
  - anchor `logic-and-shift-instructions-cnot` (line 14392) with lines 14390-14422 (section 9.7.8.5; `cnot.b32 d,a;` at 14420);
  - anchor `instructions` (line 8718) with lines 8715-8728 (section 9.7 intro, predicability);
  - anchor `predicated-execution` (line 7537) with lines 7532-7577 (section 9.3);
  - anchor `ptx-instructions` (line 7513) with lines 7508-7543 (section 9.2);
  - anchor `format-and-semantics-of-instruction-descriptions` (line 7505) with lines 7502-7515 (section 9.1);
  - anchor `fundamental-types` (line 3015) with lines 3012-3070 (section 5.2.1);
  - anchor `fundamental-types-fundamental-type-specifiers` (line 3025) with lines 3025-3061 (Table 8);
  - anchor `register-state-space` (line 2613) with lines 2610-2638 (section 5.1.1);
  - anchor `special-register-state-space` (line 2633) with lines 2630-2643 (section 5.1.2);
  - anchor `variables` (line 3741) with lines 3738-3759 (section 5.4);
  - anchor `parameterized-variable-names` (line 3933) with lines 3930-3949 (section 5.4.6);
  - anchor `restricted-use-of-sub-word-sizes` (line 3070) with lines 3067-3080 (section 5.2.2);
  - anchor `function-declarations-and-definitions` (line 6139) with spans 6160-6265 (section 7.1, parameter-passing restrictions);
  - span 6190-6265 (`st.param`/`ld.param` predication exception at 6260-6261);
  - literal search `@p not` (0 matches), `not.b64` (0), `not.b16` (0), `not.b32 %` (0), `not.pred` (1 match, line 14388), `not.b32` (2 matches, lines 14387 and 14420).
- Prior critiques consulted as context (listed in Section 1).
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is an architecture candidate only. No semantic interpretation, source bundle, or Lean mapping was reviewed because none was provided at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MAJOR | Section 12 (AMB-1..AMB-3), Section 15 (line 231), Section 16 checklist (line 247) | Artifact uses a fifth label `AMBIGUITY` while claiming "Only four labels are used" and a checklist item requiring "exactly one of SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION" |
| F-2 | MINOR | E-23 (Section 14), SF-N21 (line 46) | The `st.param`/`ld.param` predication-exception anchor is determinable as `function-declarations-and-definitions` (7.1); E-23 records "anchor not captured" |
| F-3 | MINOR | PRF-6 (line 158), A-10 (line 172), D-4/D-11 (Section 6) | Result-domain-membership obligation is likely definitionally vacuous under the proposed typed register-file representation; reclassification deferred to the semantic phase |
| F-4 | NOTE | SF-N10 (line 35), E-11 | The official `or.b32 mask mask,0x00010001` example is printed without a comma between the two `mask` tokens and without a terminating semicolon; the artifact flags the missing comma correctly |
| F-5 | NOTE | Section 1 metadata note (line 11), E-1 | Source manifest records `initial_formalization_unit` as `add.u32` while the run designates `not.b32`; handled correctly as metadata but should be reconciled |

## 5. Findings detail

### F-1 — MAJOR — Fifth label `AMBIGUITY` contradicts the artifact's own four-label claims

- **Exact location:** Section 12 "Ambiguities" (lines 174-178) introduces `AMBIGUITY (AMB-1)`, `AMBIGUITY (AMB-2)`, `AMBIGUITY (AMB-3)` as labeled statements in the same format as the other label families; Section 15 (line 231) claims "Only four labels are used: SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION; negative evidence is labeled ASSUMPTION (A-8, A-9)"; Section 16 checklist (line 247) requires "Every architectural/semantic statement uses exactly one of SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION; plain metadata notes are identified as such."
- **Relevant official evidence:** None required — this is an internal-consistency finding about the artifact's own classification discipline.
- **Description:** The artifact states, in two places, that it uses exactly four labels and claims to have applied the add.u32 F-2 lesson (no fifth label). In fact, the three AMBIGUITY entries in Section 12 use a distinct fifth label. Moreover, each AMB entry duplicates an OPEN QUESTION entry that already exists: AMB-1 duplicates OQ-4, AMB-2 duplicates OQ-1, and AMB-3 duplicates OQ-2. Consequently, the Section 15 claim is literally false and the Section 16 checklist item is not satisfied by the artifact's own statements.
- **Consequence:** The artifact fails its own Gate A checklist as written. A human Gate A reviewer would flag the contradiction, and the project's taxonomy discipline (add.u32 F-2 lesson) is undermined by a claim of compliance that does not hold. Downstream stages relying on the four-label taxonomy to distinguish facts from choices from assumptions from open questions would find an undocumented fifth category.
- **Required owner:** Spec Architect.
- **Required revision (narrow):** Either (a) fold AMB-1..AMB-3 into the OPEN QUESTION family (they are exact duplicates of OQ-4, OQ-1, OQ-2; delete Section 12 or convert it into a cross-reference table that labels each ambiguity as an OPEN QUESTION), or (b) explicitly amend the Section 15 claim and the Section 16 checklist item to document AMBIGUITY as a permitted fifth label whose entries are refinements of the OPEN QUESTION family. Option (a) is preferred because it restores exact compliance with the add.u32 F-2 lesson and the stated four-label discipline.
- **Human review required:** Yes (the revised taxonomy must be visible at Gate A).

### F-2 — MINOR — E-23 anchor is determinable; record it for full traceability

- **Exact location:** Section 14, evidence index entry E-23 (line 219): "st.param/ld.param predication exception | (anchor not captured) | 6260-6261"; Section 3, SF-N21 (line 46).
- **Relevant official evidence:** `ptx_isa_9.3.html` — the predication exception text is at lines 6260-6261; it is a list item under the parameter-passing restrictions of section 7.1 "Function Declarations and Definitions" (anchor `function-declarations-and-definitions`, line 6139; restrictions span lines 6243-6265). The artifact's "anchor not captured" is honest and does not affect the quoted fact.
- **Description:** The anchor for the exception is determinable. Recording `function-declarations-and-definitions` (with the exact list-item lines 6260-6261) would complete the traceability chain that every other evidence-index entry has.
- **Consequence:** None beyond a traceability gap; no semantic claim is affected.
- **Required owner:** Semantic Extractor.
- **Required revision:** Optionally add the anchor to E-23 in the next revision; not required before Gate A.
- **Human review required:** No.

### F-3 — MINOR — PRF-6 (result-domain membership) is likely vacuous under the proposed representation

- **Exact location:** Section 10, PRF-6 (line 158): "Result-domain membership: when the instruction executes, the value written to the destination lies in the 32-bit bit-size value domain of `.b32`."; related design choices D-4 (line 57) and D-11 (line 102); assumption A-10 (line 172) already records the vacuity risk.
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 3019-3022 (register variables always of a fundamental type), lines 3053-3054 (`.b32` is "Bits (untyped)").
- **Description:** Under D-4/D-11, the register file maps register names to values of their declared type, so a `.b32` register by construction holds a value in the 32-bit bit-value domain. An execution relation over well-formed states (VAL-1/VAL-2) cannot produce an out-of-domain result, making PRF-6 hold definitionally rather than as a meaningful property. The artifact itself flags this (A-10) and defers reclassification to the semantic phase. This matches the mov.b32 critique F-3 treatment.
- **Consequence:** If PRF-6 survives unchanged into the theorem stage, it could violate the project's non-vacuous-theorem rule or force a later weakening.
- **Required owner:** Proof Engineer, with Semantic Extractor for the state-representation decision.
- **Required revision:** In the semantic phase, reclassify PRF-6 as a definitional/validation-style well-formedness obligation or state it over a representation in which membership is non-trivial. Not required before Gate A because Section 10 already records PRF-6 as a candidate family with the vacuity note.
- **Human review required:** Yes (at the semantic/theorem-strength gate).

### F-4 — NOTE — Official `or` example has two printed anomalies; the artifact flags one

- **Exact location:** SF-N10 (line 35), E-11 (line 207).
- **Relevant official evidence:** `ptx_isa_9.3.html` line 14319: `or.b32  mask mask,0x00010001` — printed without a comma between the two `mask` tokens and without a terminating semicolon.
- **Description:** The artifact correctly flags the missing comma ("without a comma between the two `mask` tokens as printed") and correctly uses the sibling examples only as candidate evidence for immediates (AMB-2, OQ-1). The also-missing terminating semicolon is not mentioned; this is a trivial, faithful-to-source detail and requires no change.
- **Consequence:** None.
- **Required owner:** None.
- **Required revision:** None.
- **Human review required:** No.

### F-5 — NOTE — Manifest/run unit discrepancy is documented but should be reconciled

- **Exact location:** Section 1 metadata note (line 11); `documents/sources/nvidia/ptx/9.3/source-manifest.json` lines 9-15; `runs/ptx-9.3-not.b32-c454d1bc/run.json` line 7.
- **Relevant official evidence:** Manifest `initial_formalization_unit` = `add.u32` (lines 9-15); run metadata `unit` = `not.b32`.
- **Description:** The source manifest still records `add.u32` as the initial formalization unit while this run formalizes `not.b32`. The architecture correctly identifies this as project metadata (not specification evidence), notes that the orchestrator contract makes run metadata authoritative, and does not treat the manifest record as evidence about `not`. The handling is correct.
- **Consequence:** No semantic impact; a residual project-metadata inconsistency that could confuse future traceability queries if left unaddressed.
- **Required owner:** Orchestrator / Source Curator.
- **Required revision:** Update the manifest `initial_formalization_unit` record (or add a per-run override) when convenient; not an architecture defect.
- **Human review required:** No.

## 6. Source-verification notes

Specification-tool calls used in this critique: 16 restricted reads/searches (all verified directly).

All explicit SOURCE FACT claims (SF-N1..SF-N22) were re-verified and are accurate against the official HTML and manifest:

- SF-N1: anchor `logic-and-shift-instructions-not` at line 14358; section 9.7.8.4 spans 14358-14391. Confirmed.
- SF-N2: `not.type d, a;` at lines 14366-14367; type set `{ .pred, .b16, .b32, .b64 }` at line 14368. Confirmed.
- SF-N3: "Bitwise negation; one's complement." at line 14363; "Invert the bits in `a`." at line 14372. Confirmed.
- SF-N4: Semantics block `d = ~a;` at lines 14374-14377. Confirmed.
- SF-N5: Notes at lines 14378-14380 ("The size of the operands must match, but not necessarily the type." at 14379; "Allowed types include predicates." at 14380). Confirmed.
- SF-N6: "Introduced in PTX ISA version 1.0." at line 14382. Confirmed.
- SF-N7: "Supported on all target architectures." at line 14384. Confirmed.
- SF-N8: Examples `not.b32 mask,mask;` at 14387 and `not.pred p,q;` at 14388. Confirmed.
- SF-N9: family intro at lines 14240-14243; instruction list (and, or, xor, not, cnot, lop3, shf, shl, shr) at 14244-14255. Confirmed.
- SF-N10: `or` section 14290-14323 with example at 14319 (printed without comma between the `mask` tokens); `xor` section 14324-14357 with example `xor.b16 d,x,0x0001;` at 14354. Confirmed.
- SF-N11: anchor `instructions` at 8718; "All PTX instructions may be predicated." at lines 8722-8723. Confirmed.
- SF-N12: anchor `predicated-execution` at 7537; predicate registers virtual/`.pred` at 7541-7542; guard syntax `@{!}p` and unconditional-execution rule at 7547-7550; setp note at 7551-7552; examples `@p add.s32 j, j, 1;` at 7562 and `@!p bra L1;` at 7570. Confirmed.
- SF-N13: anchor `ptx-instructions` at 7513; 0-4 operands plus guard at 7517-7518; destination/source roles at 7526-7527; bit bucket at 7534-7535. Confirmed.
- SF-N14: anchor `fundamental-types` at 3015; register variables always of a fundamental type at 3019-3022; Table 8 anchor at 3025; `.b32` under "Bits (untyped)" at 3053-3054; `.pred` at 3057-3058. Confirmed.
- SF-N15: compatibility rules at lines 3062-3066 ("The bit-size type is compatible with any fundamental type having the same size."). Confirmed.
- SF-N16: anchor `register-state-space` at 2613; fast storage at 2617; widths and 1-bit predicate at 2621-2624; not fully addressable at 2626-2627; ABI/function-scope and legacy notes at 2627-2631. Confirmed.
- SF-N17: anchor `special-register-state-space` at 2633; `.sreg` predefined, platform-specific at 2637-2639. Confirmed.
- SF-N18: anchor `variables` at 3741; declaration rule at 3753-3754; predicate-only-in-register at 3755. Confirmed.
- SF-N19: anchor `parameterized-variable-names` at 3933; `%r<100>` declares `%r0`-`%r99` at 3940-3943; shorthand rule at 3946-3947. Confirmed.
- SF-N20: anchor `format-and-semantics-of-instruction-descriptions` at 7505; quoted text at 7509-7511. Confirmed.
- SF-N21: `st.param`/`ld.param` predication exception at lines 6260-6261 (inside section 7.1, anchor `function-declarations-and-definitions`). Content confirmed; anchor precision noted in F-2.
- SF-N22: anchor `restricted-use-of-sub-word-sizes` at 3070; restriction list at 3074-3075; `.b32` not in the list. Confirmed.
- Negative searches: `@p not` (0), `not.b64` (0), `not.b16` (0), `not.b32 %` (0), `not.pred` (1 match at 14388), `not.b32` (2 matches: 14387 `not.b32 mask,mask;` and 14420 `cnot.b32 d,a;`). All confirmed.
- Document hashes and line counts match the tool metadata and manifest: HTML SHA-256 `e2095c4a...`, 47,743 lines; manifest SHA-256 `622e6ce0...`, 38 lines; SHA256SUMS SHA-256 `e02f4fead...`, 3 lines (HTML and PDF hashes recorded); PDF SHA-256 `769cc12e...` as recorded in the manifest. Confirmed.

No SOURCE FACT mislabeling, phantom cross-references, or source-faithfulness problems were found. The project-status/scope classification as metadata/DESIGN CHOICE (add.u32 F-1 lesson) is correct. Guard-false behavior is stated uniformly via the complete guard expression with no "negated guard true means no-op" phrasing (add.u32 F-5/F-6 lessons applied). Register/value/state foundations are grounded in actual register-chapter reads (add.u32 F-3/F-9 lesson applied). The one taxonomy defect is F-1.

## 7. Required revisions (consolidated)

One substantive revision is required before Gate A:

1. Reconcile the `AMBIGUITY` label with the stated four-label taxonomy (F-1): fold AMB-1..AMB-3 into OPEN QUESTION (preferred; each already has an exact OQ counterpart) or explicitly document AMBIGUITY as a permitted fifth label, and update Section 15 and the Section 16 checklist item accordingly.

Optional refinements (not required before Gate A):

2. Record the `function-declarations-and-definitions` anchor in E-23 (F-2) — cosmetic evidence-index precision.
3. In the semantic phase, reclassify PRF-6 as definitional/validation or reformulate it over a domain that makes membership non-trivial (F-3).
4. Reconcile the manifest `initial_formalization_unit` metadata with the `not.b32` run (F-5) — orchestrator-level, not architecture-level.

## 8. Residual open questions

- Is the value-domain membership obligation (PRF-6) meaningful under the eventual Lean state representation, or should it be a definitional well-formedness check (F-3)?
- Is the exact operand-typing formulation for `not.b32` (size-based, per SF-N5/SF-N15) to be settled in the semantic phase as OQ-7 anticipates, including how immediate values (if adopted per AMB-2/OQ-1) are typed?
- Will the human Gate A reviewer confirm the bounded base scope (scalar `.b32`; `.pred`/`.b16`/`.b64` forms out of scope) as the intended `not.b32` unit (D-0c, AMB-1, OQ-4)?
- The guard-false "no state update" interpretation (A-4, OQ-3) remains an assumption based on the "controls conditional execution" wording; it requires human approval and re-verification at the semantic phase.

## 9. Gate A readiness assessment

Not ready for presentation to Human Gate A until F-1 is reconciled. The artifact is otherwise a disciplined, source-faithful architecture: all citations verified, correct project-status classification, honest ambiguity/open-question records, relational non-vacuous obligation families, and an evidence index that is accurate apart from the F-2 anchor gap. F-3 is a candidate-obligation refinement for the semantic phase; F-4 and F-5 are notes. Once the architect resolves the F-1 taxonomy inconsistency (a narrow, mechanical edit), the artifact should be re-critiqued briefly and may then be presented for human Gate A. This assessment is not a Gate A approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/not-b32/architecture/foundation-v1.md`. No Lean code was written, and no `not.b32` bit-complement semantics were extracted during this review. No gates were approved and nothing was promoted to `accepted/`.
