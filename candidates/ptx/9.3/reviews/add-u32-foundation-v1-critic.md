# Independent Architecture Critique — add-u32-foundation-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/architecture/add-u32-foundation-v1.md` (DRAFT — NOT HUMAN APPROVED), 198 lines, SHA-256 `5696d3f470bc55b20c76f34dd10eaf43e329691f1f0e861c3a74aef2efc6ac00`.
- This critique is an independent semantic-critic review. It does not approve Gate A and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`.
- Source metadata consulted: `documents/sources/nvidia/ptx/9.3/source-manifest.json`.

## 2. Overall verdict

**BLOCKED**

The artifact is a disciplined draft with accurate source-fact citations (all SF-1..SF-18 claims were re-verified against the official HTML), but it contains one BLOCKER (project-internal status and scope are labeled as official SOURCE FACTs, corrupting the classification discipline the artifact itself asserts), six MAJOR findings (label-system self-contradiction, insufficiently supported register/value architecture while the register chapter is unread, incorrect negated-guard description in TO-6, vacuity risk in the theorem-obligation families, inaccurate Gate A checklist items, and missing official evidence required before human review), and three MINOR findings. The artifact must be revised and re-critiqued before it can be presented for Gate A.

## 3. Inputs reviewed

- `candidates/ptx/9.3/architecture/add-u32-foundation-v1.md` — complete candidate read (198/198 lines).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` — read in full (lines 1-39).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified spans and anchors via restricted tools:
  - anchor `integer-arithmetic-instructions-add` (line 8757) with lines 8752-8857;
  - anchor `predicated-execution` (line 7537) with lines 7529-7552;
  - anchor `fundamental-types` (line 3015) with lines 3012-3075;
  - lines 8716-8726 (section 9.7 intro);
  - lines 2896-2906 (example with `add.u32 %r, %r, 4;`);
  - lines 6166-6178 (`.func` example with `add.u32 %res, %ptr, %inc;`);
  - lines 6255-6267 (`st.param`/`ld.param` predication exception);
  - literal search for "Target ISA Version" (0 matches).
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is an architecture candidate only. No semantic interpretation, source bundle, or Lean mapping was reviewed because none was provided.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | BLOCKER | Lines 5, 7 (Section 1) | Project status and bounded scope labeled as SOURCE FACT |
| F-2 | MAJOR | Lines 39-40; line 180 | OBSERVATION label contradicts the artifact's own four-label rule |
| F-3 | MAJOR | D-4 (49), D-5 (50), D-12 (127); OQ-4 (136), E-22 (167) | Register/value and minimal-state architecture insufficiently supported while register chapter unread |
| F-4 | MINOR | D-8 (53), TO-8 (114), A-3 (123), line 40 | Negative evidence slightly overreaches in two places |
| F-5 | MAJOR | TO-6 (line 112) | Negated-guard no-op condition described incorrectly |
| F-6 | MINOR | D-6 (51), A-4 (124) | Guard-false behavior not stated precisely for `@!p` |
| F-7 | MAJOR | TO-5 (111), TO-8 (114), TO-9 (115), TO-10 (116) | Theorem-obligation families risk vacuity/triviality |
| F-8 | MAJOR | Section 13, lines 180-181; E-11 (156), E-18 (163) | Gate A checklist items inaccurate or insufficient |
| F-9 | MAJOR | OQ-1 (133), OQ-2 (134), OQ-4 (136), E-22 (167) | Missing official evidence required before human review |
| F-10 | MINOR | Line 193 | Cross-reference to "sub, mul, etc. in Section 3" does not exist |

## 5. Findings detail

### F-1 — BLOCKER — Project status and bounded scope mislabeled as SOURCE FACT

- **Exact location:** Section 1, line 5 (`STATUS: SOURCE FACT — This artifact is a DRAFT architecture candidate ... not promoted to accepted/`) and line 7 (`SOURCE FACT — The bounded scope of this artifact is ...`).
- **Relevant official evidence:** `source-manifest.json` lines 9-15 (initial formalization unit). No official-source citation supports line 5 or line 7.
- **Description:** Line 5 uses a composite label `STATUS: SOURCE FACT` that is outside the artifact's own four-label taxonomy and asserts the artifact's draft/approval status — project-internal metadata, not a statement from the PTX ISA. Line 7 labels the artifact's self-defined bounded scope as a SOURCE FACT; scope is a design decision of this artifact. Only line 6 (unit identity) is genuinely grounded in manifest lines 9-15. This is exactly the "project status and project scope labeled as official SOURCE FACTs" hazard.
- **Consequence:** A human Gate A reviewer could mistake project-internal framing for official specification evidence, corrupting source traceability; line 5 also violates the artifact's own claim (line 180) that all statements use only the four permitted labels.
- **Required owner:** Semantic Extractor.
- **Required revision:** Reclassify line 5 as a non-source status/metadata note (not SOURCE FACT) and line 7 as DESIGN CHOICE (bounded scope); keep SOURCE FACT only for manifest-grounded identity facts such as line 6. Re-run the critique after revision.
- **Human review required:** Yes.

### F-2 — MAJOR — OBSERVATION label contradicts the artifact's own four-label rule

- **Exact location:** Section 3, lines 39-40 (two `OBSERVATION (negative evidence, not a source fact)` entries); Section 13, line 180 ("All statements are labeled SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION").
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 8757-8842 (add section); literal search "Target ISA Version" returned 0 matches.
- **Description:** The artifact uses OBSERVATION as a fifth statement label, while its own Gate A checklist asserts that every statement uses exactly four labels. The observation content itself is appropriate and honestly flagged as not-a-source-fact, but the taxonomy is inconsistent, and the checklist item is false as written.
- **Consequence:** Self-contradiction between Sections 3 and 13 undermines confidence in the classification discipline and makes the Gate A checklist inaccurate.
- **Required owner:** Semantic Extractor.
- **Required revision:** Reconcile the taxonomy — either admit OBSERVATION (and update line 180) or re-label both observations as ASSUMPTION/OPEN QUESTION.
- **Human review required:** Yes.

### F-3 — MAJOR — Register/value and minimal-state architecture insufficiently supported while register chapter unread

- **Exact location:** D-4 (line 49), D-5 (line 50), D-12 (line 127); acknowledged gap at OQ-4 (line 136) and E-22 (line 167); Section 13 checklist item line 181.
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 3019-3022 (register variables of fundamental type), lines 2902 and 6172 (example snippets). The register chapter (naming grammar, `.reg` state-space rules) was not read.
- **Description:** D-4/D-12 fix the register model (register file mapping names to typed values; predicate registers boolean-valued) and D-5 fixes the minimal state (value-register file plus predicate-register file). The only grounding is SF-14 plus two examples; the register naming grammar, `.reg` declaration rules, and the boolean-valued reading of `.pred` are unverified. The artifact documents the gap but still presents D-4/D-5/D-12 as architecture commitments, and the Gate A checklist treats documenting the gap (E-22) as sufficient.
- **Consequence:** A human reviewer cannot confirm the core register/state model without the register chapter; approving D-4/D-5/D-12 now risks semantic drift in the later Lean-mapping stage.
- **Required owner:** Semantic Extractor, with a Source Curator read of the register chapter.
- **Required revision:** Read the register chapter before Gate A, or explicitly mark D-4/D-5/D-12 as conditional design choices pending that read; update E-22 status and the Section 13 checklist item.
- **Human review required:** Yes.

### F-4 — MINOR — Negative evidence is used carefully but slightly overreaches in two places

- **Exact location:** D-8 (line 53) and Section 8 (line 96) — no error constructor based on absence of evidence; A-3 (line 123) and TO-8 (line 114) — determinism based on absence of nondeterminism; line 40 — generalization from a zero-match search.
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 8757-8842; literal search "Target ISA Version" (0 matches).
- **Description:** (a) D-8 and TO-8 rest on absence of evidence in a single section; this is acceptable only because the artifact labels them as observations/assumptions and requires semantic-phase re-verification (line 96). (b) Line 40 generalizes to "version/target information is expressed per instruction via 'PTX ISA Notes' and 'Target ISA Notes' rubrics"; the zero-match search only proves the literal is absent, and while the add section indeed uses those rubrics, the document-wide generalization slightly overreaches the evidence.
- **Consequence:** If hardened into source facts later, these could become unsupported semantic claims; the current labeling mitigates the risk.
- **Required owner:** Semantic Extractor.
- **Required revision:** Keep negative-evidence items as ASSUMPTION/OPEN QUESTION; re-verify in the semantic phase; soften line 40's generalization.
- **Human review required:** No (monitored at the semantic phase).

### F-5 — MAJOR — TO-6 incorrectly describes negated guards

- **Exact location:** TO-6 (line 112): "Guard-false no-op: when the guard predicate evaluates false (or negated guard true), the state is unchanged."
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 7547-7550 (guard syntax `@{!}p`; predicate "optionally negated"; instructions without a guard execute unconditionally).
- **Description:** For a negated guard `@!p`, the guard expression `!p` evaluates true exactly when `p` is false — that is the execution condition, not a no-op condition. Under the natural reading of "negated guard true" (= the negated guard expression is true), TO-6 asserts the instruction does not execute precisely when the negated guard is satisfied, which is backwards for `@!p`. The only correct reading ("the guard is negated and the underlying predicate p is true") is not what the phrasing states, so the obligation is either wrong or ambiguous.
- **Consequence:** If this candidate obligation were adopted, the guard-false theorem for `@!p` would be false, forcing a later proof engineer to weaken it or allowing semantics to drift from PTX.
- **Required owner:** Proof Engineer, with Semantic Extractor for the underlying guard semantics.
- **Required revision:** Restate TO-6 uniformly in terms of the guard expression's boolean value (no-op iff the guard expression evaluates false), covering both `@p` and `@!p`; delete the ambiguous "negated guard true" phrasing.
- **Human review required:** Yes.

### F-6 — MINOR — Guard-false behavior is not stated precisely in the design sections

- **Exact location:** D-6 (line 51) and A-4 (line 124): "guard false" / "no state update" wording; OQ-5 (line 137) defers the interpretation.
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 7547-7550.
- **Description:** D-6 and A-4 phrase the no-op condition as "guard false," which is only well-defined for non-negated guards; the negated case is silently folded in. OQ-5 honestly flags this as pending human approval, so it is an imprecision rather than a silent defect, but since D-7 already distinguishes `@!p`, D-6/A-4 should state the condition uniformly.
- **Consequence:** The ambiguity is a seed for TO-6-style errors and leaves the Gate A reviewer without a precise predication rule to confirm.
- **Required owner:** Semantic Extractor.
- **Required revision:** Restate the no-op condition as "guard expression evaluates false" for both `@p` and `@!p`.
- **Human review required:** Yes.

### F-7 — MAJOR — Theorem-obligation families risk vacuity or triviality

- **Exact location:** Section 9, TO-1..TO-11 (lines 107-117), especially TO-5 (line 111), TO-8 (line 114), TO-9 (line 115), TO-10 (line 116).
- **Relevant official evidence:** None directly (design-level concern); the risk follows from the proposed representations in D-3/D-4/D-12 and the official target notes (lines 8822, 8827).
- **Description:** TO-5 ("state totality: the updated state is a total function over the register domain") is definitionally true if the state is represented as a total function, making it vacuous. TO-8 ("determinism: resulting state is unique") is trivially satisfied by any functional Lean semantics and is grounded in negative evidence. TO-9/TO-10 for base `add.u32` ("introduced in PTX ISA 1.0", "supported on all target architectures") are near-trivial unless version and target are modeled with actual constraints. TO-1 is definitional. Only TO-2/TO-3/TO-4/TO-6/TO-7/TO-11 are substantive as stated.
- **Consequence:** If carried forward unchanged, the obligations would not establish meaningful properties, violating the project's non-vacuous-theorem rule.
- **Required owner:** Proof Engineer.
- **Required revision:** Specify non-vacuous formulations (e.g., totality as a property of an update relation rather than of a function; determinism over an execution relation); mark TO-1 as a well-formedness/definitional obligation rather than a theorem.
- **Human review required:** Yes.

### F-8 — MAJOR — Gate A checklist claims are inaccurate or insufficient

- **Exact location:** Section 13, item at line 180 and item at line 181; evidence-index entries E-11 (line 156) and E-18 (line 163).
- **Relevant official evidence:** `ptx_isa_9.3.html` line 8718 (section 9.7 anchor is `instructions`, available), lines 7534-7535 (bit bucket text).
- **Description:** (a) Line 180 asserts all statements use only four labels; this is false given lines 5, 39-40 (see F-1, F-2). (b) Line 181 treats documenting the register-chapter gap as sufficient for Gate A, but D-4/D-5/D-12 cannot be confirmed without reading that chapter (see F-3). (c) E-11 marks the 9.7 anchor as "not captured" although the anchor `instructions` exists at line 8718; E-18 cites `ptx-instructions` "(from TOC)" without body verification.
- **Consequence:** The human reviewer would check against an inaccurate checklist, weakening the gate.
- **Required owner:** Semantic Extractor.
- **Required revision:** Fix the four-label item; change the register-gap item to require the chapter read (or conditional D-4/D-5); capture/verify the anchors for E-11 and E-18.
- **Human review required:** Yes.

### F-9 — MAJOR — Missing official evidence required before human review

- **Exact location:** OQ-1 (line 133), OQ-2 (line 134), OQ-4 (line 136), E-22 (line 167); also the guard semantics question behind OQ-5 (line 137).
- **Relevant official evidence:** Chapters/sections not read in this pass.
- **Description:** Before Gate A the following official-source reads are required: (a) the register chapter (register naming grammar, `.reg` state-space rules) for D-4/D-5/D-12; (b) section 9.1 "Format and Semantics of Instruction Descriptions" for the operand grammar underlying OQ-1 (immediate operands); (c) the target-architecture/sm-family text behind "`sm_120f` or higher in the same family" for OQ-2/TO-10; (d) any additional predication text pinning down the no-op semantics of a false guard for `@!p`.
- **Consequence:** Without these reads, the register, operand, and target-gating components of the architecture remain unverified and the human reviewer would be asked to approve unverified foundations.
- **Required owner:** Source Curator (bounded reads) with Semantic Extractor.
- **Required revision:** Perform the listed reads and update the affected design choices and open questions before Gate A.
- **Human review required:** Yes.

### F-10 — MINOR — Inaccurate internal cross-reference to "sub, mul, etc." in Section 3

- **Exact location:** Section 14, line 193 ("mentions of `sub`, `mul`, etc. in Section 3 are source-list facts only, not models").
- **Relevant official evidence:** Section 3 of the reviewed artifact (lines 21-40) contains no mention of `sub` or `mul`.
- **Description:** Line 193 references non-existent content: Section 3 never mentions `sub` or `mul`. (`sub` appears only in the source file at line 8843+ and in the example at line 2903, and in the candidate's Section 3 the packed/sat forms cited are `add.sat.u32`, `add.u16x2`, etc.)
- **Consequence:** Minor internal inconsistency; does not affect semantics but could mislead readers of the non-goals.
- **Required owner:** Semantic Extractor.
- **Required revision:** Remove or correct the reference.
- **Human review required:** No.

## 6. Source-verification notes

Source-tool calls used: 9 of the 10 allowed.

All explicit SOURCE FACT claims (SF-1..SF-18) were re-verified and are accurate against the official HTML and manifest:

- SF-1/SF-2: anchor `integer-arithmetic-instructions-add` at line 8757; section 9.7.1.1 spans 8757-8842; manifest unit identity matches lines 9-15. Confirmed.
- SF-3 (syntax lines 8765-8772), SF-4 (lines 8762, 8776), SF-5 (lines 8783-8784), SF-6 (lines 8817-8818), SF-7 (lines 8822-8825), SF-8 (lines 8827-8832), SF-9 (line 8836 `@p  add.u32     x,y,z;`). Confirmed.
- SF-10 (line 8722; section 9.7 anchor is `instructions` at line 8718). Confirmed.
- SF-11/SF-12 (anchor `predicated-execution` at line 7537; guard text 7547-7550; setp note 7551-7552). Confirmed.
- SF-13 (line 6261). Confirmed.
- SF-14/SF-15 (anchor `fundamental-types` at 3015; Table 8 anchor at 3025; compatibility text 3064-3066). Confirmed.
- SF-16 (bit bucket text at lines 7534-7535). Confirmed.
- SF-17 (line 2902 `add.u32      %r, %r, 4;`) and SF-18 (line 6172 `add.u32 %res, %ptr, %inc;`). Confirmed.
- Negative observation on lines 8757-8842 (no error/trap/UB text for `add`). Confirmed.
- Literal search "Target ISA Version" returned 0 matches. Confirmed.
- Document hashes and line counts in Section 2 match the manifest and tool metadata (HTML SHA-256 `e2095c4a...`, 47,743 lines; manifest SHA-256 `622e6ce0...`, 39 lines; PDF SHA-256 `769cc12e...`). Confirmed.

Not verified (and not needed for this critique): the enclosing section heading for line 2902 and the exact body anchor for the bit-bucket section.

## 7. Required revisions (consolidated)

1. Reclassify lines 5 and 7 (Section 1) out of SOURCE FACT (F-1).
2. Reconcile the statement-label taxonomy with the Section 13 four-label claim (F-2, F-8).
3. Read the register chapter and either confirm or make conditional D-4/D-5/D-12 before Gate A (F-3, F-9).
4. Correct TO-6 and restate guard-false behavior uniformly for `@p` and `@!p` (F-5, F-6).
5. Specify non-vacuous formulations for TO-5/TO-8 and reclassify TO-1 as definitional (F-7).
6. Fix Gate A checklist items (four-label claim; register-gap item) and complete anchors for E-11/E-18 (F-8).
7. Perform the missing source reads for section 9.1 and the sm-family/target text (F-9).
8. Remove the phantom `sub`/`mul` reference in line 193 (F-10).
9. Keep negative-evidence items flagged for semantic-phase re-verification (F-4).

## 8. Residual open questions

- Is the boolean-valued reading of `.pred` predicate registers stated in the register chapter or is it an interpretation?
- Does section 9.1's operand grammar permit immediates in all source-operand positions of `add`, or only in some?
- Is the no-op semantics of a false guard (including `@!p`) spelled out anywhere beyond the section 9.3 excerpt read?
- Is overflow/wrap behavior for non-saturating `add.u32` stated anywhere else in the ISA (the "Semantics" block only shows `d = a + b;`)? This remains deferred to the semantic phase per the artifact.
- What is the formal meaning of "`sm_120f` or higher in the same family" for target-gating obligations?

## 9. Gate A readiness assessment

Not ready. The draft is a strong, honest foundation with fully verified source citations, but it is BLOCKED by F-1 (classification integrity), and the MAJOR findings F-2, F-3, F-5, F-7, F-8, and F-9 must be resolved before a human Gate A reviewer should consider it. In particular, the register chapter and section 9.1 reads are prerequisite evidence, and TO-6's negated-guard description must be corrected. This assessment is not a Gate A approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/architecture/add-u32-foundation-v1.md`. Its SHA-256 remains `5696d3f470bc55b20c76f34dd10eaf43e329691f1f0e861c3a74aef2efc6ac00`. No Lean code was written, and no `add.u32` arithmetic semantics were extracted during this review.
