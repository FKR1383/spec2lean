# Independent Architecture Critique — add-u32-foundation-v2

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md` (DRAFT — NOT HUMAN APPROVED), 243 lines. Its SHA-256 could not be independently computed with the available read-only tools (no hash utility); the file was read completely and its hashes should be recorded from the filesystem at Gate A.
- Prior artifacts reviewed for comparison and preserved unchanged: `candidates/ptx/9.3/architecture/add-u32-foundation-v1.md` (197 lines; SHA-256 `5696d3f470bc55b20c76f34dd10eaf43e329691f1f0e861c3a74aef2efc6ac00` as recorded in the v1 critique) and `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md` (194 lines; SHA-256 `7f52da1f4aee741edc3f063c00c7d6cb294d4d6ef6e591d21276d5c283821db7` as cited in v2 Section 2 — not independently verifiable with the available read-only tools).
- This critique is an independent semantic-critic review. It does not approve Gate A, does not edit or repair v1, v2, or the previous critique, and does not write Lean.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines — confirmed by tool metadata).
- Source metadata consulted: `documents/sources/nvidia/ptx/9.3/source-manifest.json` (38 lines; SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2` as recorded in the v1 critique).
- Restricted source-tool calls used: 11 of 12 allowed.

## 2. Overall verdict

**READY_FOR_HUMAN_REVIEW**

v2 resolves F-1 through F-8 and F-10 (VERIFIED_RESOLVED) and legitimately keeps only the residual of F-9 open (ACCEPTABLY_DEFERRED). Every newly introduced SOURCE FACT (SF-19..SF-25) and the revised evidence-index entries (E-22..E-27) were independently re-verified against the official HTML and are accurate; the manifest line-count claim ("38 lines") is correct. The classification-integrity BLOCKER that stopped v1 (F-1) is genuinely fixed: project status and bounded scope are no longer labeled SOURCE FACT. The register/value/state architecture is now grounded in official register text, and the operand architecture is supported by section 9.1/9.2 evidence. Predication is expressed uniformly through evaluation of the complete guard expression, with correct `@!p` handling and no residual "negated guard true means no-op" phrasing. Validation obligations are clearly distinguished from theorem obligations, and the TO-5/TO-8-style vacuity problems are addressed (totality dropped; determinism stated over a relation; near-trivial gating obligations reclassified as explicit conformance checks). The Gate A checklist is now accurate, including all cited anchors, which I re-verified.

Two MINOR and three NOTE observations are recorded (Section 5); none blocks presentation to a human reviewer. READY_FOR_HUMAN_REVIEW means only that a human may now perform Gate A; it is not Gate A approval.

## 3. Inputs and hashes

| Artifact | Lines | SHA-256 | Verification |
|---|---|---|---|
| `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md` | 243 | not independently computable with available tools | complete read (243/243) |
| `candidates/ptx/9.3/architecture/add-u32-foundation-v1.md` | 197 | `5696d3f470bc55b20c76f34dd10eaf43e329691f1f0e861c3a74aef2efc6ac00` (as recorded in v1 critique) | complete read |
| `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md` | 194 | `7f52da1f4aee741edc3f063c00c7d6cb294d4d6ef6e591d21276d5c283821db7` (as cited in v2 Section 2; not independently verifiable with available tools) | complete read |
| `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` | 47,743 | `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856` | confirmed by tool metadata |
| `documents/sources/nvidia/ptx/9.3/source-manifest.json` | 38 | `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2` (as recorded in v1 critique) | complete read |

## 4. F-1 through F-10 resolution verification table

| ID | Severity (v1) | Status in this critique | Verification basis |
|---|---|---|---|
| F-1 | BLOCKER | VERIFIED_RESOLVED | v2 Section 1 line 5 is a plain "Status note (project metadata, not specification evidence)" with no SOURCE FACT label; bounded scope is DESIGN CHOICE (D-0); line 10 states unit identity is the only official-source fact in the section and records it as SF-1. A full scan found no project-internal statement labeled SOURCE FACT anywhere in v2. The classification hazard is genuinely removed. |
| F-2 | MAJOR | VERIFIED_RESOLVED | The OBSERVATION label is absent from v2. Negative evidence is re-expressed as ASSUMPTION (A-6 no-error; A-8 zero-match search) and OPEN QUESTION (OQ-3). Gate A checklist item (line 220) scopes the four-label rule to architectural/semantic statements and identifies plain metadata notes as such. The self-contradiction is gone. |
| F-3 | MAJOR | VERIFIED_RESOLVED | The register chapter reads claimed by v2 are real and verified: SF-21 (anchor `register-state-space` line 2613; 1-bit predicates; scalar widths; not addressable; ABI/function-scope notes), SF-22 (line 3755 declaration rule and predicate-variables-only-in-register rule), SF-23 (anchor `parameterized-variable-names` line 3933; `%r<100>` at 3943). D-4/D-5/D-12/D-13/D-14 are now grounded in that evidence; residual encoding/compilation questions are explicit OQ-5/OQ-6, not guesses. |
| F-4 | MINOR | VERIFIED_RESOLVED | A-3, A-6, A-8 are labeled ASSUMPTION with semantic-phase re-verification requirements; A-8 explicitly confines the version/target-rubric claim to the add section and the negative search result, removing v1's document-wide overgeneralization. |
| F-5 | MAJOR | VERIFIED_RESOLVED | TO-6's erroneous "negated guard true" no-op wording is deleted. D-19/D-20 and PRF-4/PRF-5 are stated uniformly in terms of the complete guard expression: executes iff the guard expression evaluates true; no update iff it evaluates false, covering `@p` (p false) and `@!p` (not p false, i.e., p true). PRF-5 explicitly records the (F-5) correction. |
| F-6 | MINOR | VERIFIED_RESOLVED | D-6 and A-4 now phrase the no-op condition as "when the complete guard expression evaluates false" for both `@p` and `@!p`; the pending human approval of the interpretation is recorded in OQ-3. |
| F-7 | MAJOR | VERIFIED_RESOLVED | Section 10 distinguishes validation obligations (VAL-1..VAL-6, definitional, D-26) from proof obligations over a future execution relation (PRF-1..PRF-6, D-25). Vacuity risks are addressed: state totality (TO-5) is dropped rather than stated vacuously; determinism (PRF-1) is stated over a relation; near-trivial gating obligations (VAL-5/VAL-6) are honestly reclassified as conformance checks with explicit non-vacuity notes. Remaining candidate-level nuances are recorded as NOTE findings NF-2/NF-3. |
| F-8 | MAJOR | VERIFIED_RESOLVED | Gate A checklist items corrected; four-label item scoped; register-gap item replaced by a register-evidence-complete item. All anchors cited in the checklist and evidence index were re-verified: `instructions` (8718), `ptx-instructions` (7513), `register-state-space` (2613), `parameterized-variable-names` (3933), `format-and-semantics-of-instruction-descriptions` (7505). |
| F-9 | MAJOR | ACCEPTABLY_DEFERRED | All four missing-evidence reads demanded by F-9 were performed and verified: section 9.1/9.2 operand format (SF-19, SF-20, E-18, E-25), the register chapter (SF-21, SF-22, SF-23), additional predication text for the false-guard case (SF-24 examples), and the `sm_120f` occurrences (SF-25, 57 matches confirmed). Two residual items remain by design: (a) the exact no-op consequence of a false guard (A-4/OQ-3) is an interpretation pending human approval; (b) the formal meaning of "same family" (OQ-1) concerns only future saturating/packed forms and is deferred to that future unit. Both are out of the base `add.u32` evidence scope, are honestly flagged, and are precisely the kinds of decisions Gate A exists to consider. PARTIALLY_RESOLVED is therefore acceptable for Gate A (see Sections 7 and 8). |
| F-10 | MINOR | VERIFIED_RESOLVED | The phantom cross-reference to "sub, mul, etc. in Section 3" is removed. Section 16 (D-30) refers only to saturating/packed `add` forms that do appear in Section 3 (SF-3, SF-6, SF-8, SF-25) and states they are not modeled. |

## 5. New findings

### NF-1 — MINOR — Two substantive Section 8 statements are unlabeled prose

- **Affected artifact:** `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md`.
- **Exact location:** Section 8, line 100 ("Predication is expressed uniformly by evaluation of the complete guard expression. The complete guard expression is: ...") and line 105 ("Predication is applicable to add: ...").
- **Evidence references:** The artifact's own checklist (line 220) requires every architectural/semantic statement to use exactly one of SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION. In v1, the equivalent predication-applicability claim was explicitly labeled SOURCE FACT (v1 Section 7); in v2 it is unlabeled.
- **Description:** Line 100 asserts the guard-expression evaluation design (an architectural claim that is subsequently labeled in D-19/D-20), and line 105 asserts predication applicability to `add` with inline grounding (SF-10, SF-9, SF-24) but without a statement label. The content of both statements is accurate and source-supported; only the labels are missing.
- **Consequence:** Minor classification incompleteness; a strict reading of the checklist item is slightly inaccurate, although the substance is grounded and traceability is not corrupted.
- **Required owner:** Semantic Extractor.
- **Human review required:** No.

### NF-2 — NOTE — PRF-5 guard-behavior could become definitional if the execution relation is defined via D-19

- **Affected artifact:** `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md`.
- **Exact location:** Section 10, PRF-5 (line 141).
- **Evidence references:** D-19 (line 102), D-25 (line 119).
- **Description:** PRF-5 states "the instruction executes if and only if the complete guard expression evaluates true." If the future Lean semantics defines the execution relation directly using the D-19 guard rule, PRF-5 would hold definitionally. To preserve the non-vacuity achieved in F-7, the Proof Engineer must define the execution relation independently of the guard rule or prove PRF-5 as a derived property.
- **Consequence:** Without care, PRF-5 could re-introduce a definitionally-true obligation of the TO-1/TO-5 kind that v2 otherwise eliminated.
- **Required owner:** Proof Engineer.
- **Human review required:** No.

### NF-3 — NOTE — State-totality obligation dropped rather than reformulated

- **Affected artifact:** `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md`.
- **Exact location:** Section 10 (no entry for the former TO-5); cf. v1 TO-5 (line 111).
- **Evidence references:** v1 critique F-7 (suggested totality "as a property of an update relation rather than of a function").
- **Description:** v1's TO-5 (state totality) is absent from both the VAL and PRF families. Dropping a vacuous obligation is a defensible resolution of F-7, but the critic's suggested non-vacuous reformulation was not adopted. The bounded unit can proceed without it; the Proof Engineer should decide whether a totality/well-formedness invariant on the register file is needed to support PRF-2/PRF-4.
- **Consequence:** No vacuous obligation remains; the only risk is a missing invariant in the later proof phase.
- **Required owner:** Proof Engineer.
- **Human review required:** No.

### NF-4 — NOTE — Gate A checklist phrasing "validated in Section 10" is loose

- **Affected artifact:** `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md`.
- **Exact location:** Section 15, line 233.
- **Evidence references:** Section 10 (obligation families); Section 4/5/6/7 (design choices representing dependencies).
- **Description:** "Dependencies required before `add.u32` formalization are represented in the design choices and validated in Section 10" — Section 10 contains obligation families, not a dependency validation per se. The dependencies are represented in the design choices; "validated" overstates Section 10's role.
- **Consequence:** Minor checklist phrasing inaccuracy; does not affect the substance of the checklist.
- **Required owner:** Semantic Extractor.
- **Human review required:** No.

## 6. Source-verification notes

Source-tool calls used: 11 of 12 allowed (all `spec_get_context` / `spec_search` against the official HTML). Every important revised claim in v2 was re-verified:

- SF-21 (Section 5.1.1 Register State Space): anchor `register-state-space` at line 2613; "Registers (`.reg` state space) are fast storage locations" (2617); typed/untyped and 1-bit predicate, scalar widths 8/16/32/64/128 (2621-2624); not fully addressable (2626-2627); ABI function-scope restriction and legacy module-scope handling (2627-2630); alignment for multi-word loads/stores (2630-2631). Confirmed.
- SF-16/SF-19 (Section 9.2): anchor `ptx-instructions` at line 7513; zero-to-four operands plus optional guard after `@` left of opcode (7517-7518); `d` destination and `a`, `b`, `c` sources (7526-7527); bit bucket at 7534-7535. Confirmed. E-18 range 7513-7536 confirmed.
- SF-20 (Section 9.7.1 intro): literal text "Integer arithmetic instructions operate on the integer types in register and constant immediate forms." at line 8728; section 9.7.1 heading at 8724-8726. Confirmed.
- SF-24 (Section 9.3 examples): `@p    add.s32      j, j, 1;    // if i < n, add 1 to j` at line 7562 and `@!p   bra  L1;                 // if False, branch over` at line 7570, within 7553-7574. Confirmed. The false-guard no-op reading ("if i < n, add 1 to j") is directly supported by the example, strengthening A-4 beyond bare "conditional execution" wording.
- SF-23 (Section 5.4.6): anchor `parameterized-variable-names` at line 3933; `.reg .b32 %r<100>;    // declare %r0, %r1, ..., %r99` at 3943; shorthand usable with any fundamental type and any state space (3946-3948). Confirmed.
- SF-22 (Section 5.4): literal text "Predicate variables may only be declared in the register state space." and the declaration-rule sentence at line 3755. Confirmed; the missing subsection anchor is honestly flagged.
- SF-25 (`sm_120f`): totalMatches = 57; matches at lines 8832 (add Target ISA Notes), 8901 (sub), 9340, 9419, 9500, 17681 (rename note to `sm_110f` from PTX ISA 9.0), and further. Confirmed. No formal definition of "same family" appeared in the 12 matches returned; the claim as stated (no formal definition found in matches read) is fair.
- SF-10 (Section 9.7 intro): anchor `instructions` at line 8718; "All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax." at 8722-8723. Confirmed. E-11 is now accurate.
- E-25 (Section 9.1): anchor `format-and-semantics-of-instruction-descriptions` at line 7505, section 7505-7512. Confirmed.
- SF-14/SF-15 (Section 5.2.1): anchor `fundamental-types` at 3015; prose 3019-3022; Table 8 at 3025-3061; compatibility text at 3062-3066 (v2's range is correct; v1's "3062-3065" was slightly short). Confirmed.
- SF-2..SF-9 (add section): anchor `integer-arithmetic-instructions-add` at 8757; heading 8757-8760; "Add two values." 8762; syntax 8763-8774; description 8776; operand typing 8783-8784; .sat notes 8813-8819; PTX ISA Notes 8821-8825; Target ISA Notes 8826-8833; examples 8834-8841 with `@p  add.u32     x,y,z;` at 8836. Confirmed.
- Manifest line count: 38 lines; v2's "38 lines" claim is correct (v1's "lines 1-39" was inaccurate; corrected in v2).
- Hashes: HTML SHA-256 and line count confirmed by tool metadata. The manifest SHA-256 and the v1 artifact SHA-256 are as recorded in the v1 critique. The SHA-256 of the v2 artifact and of the v1 critique file could not be independently computed with the available read-only tools.

## 7. Residual open questions

- OQ-3 (v2) — The exact no-op consequence of a false guard beyond "controls conditional execution" (SF-11) remains an interpretation (A-4) pending human approval. The SF-24 examples now provide direct supporting evidence ("if i < n, add 1 to j" implies no add otherwise), but the human Gate A reviewer should explicitly confirm A-4/OQ-3 before the guard-false obligations (PRF-4) are treated as faithful. This is the acceptable residual of F-9.
- OQ-1 (v2) — The formal meaning of "`sm_120f` or higher in the same family" is deferred to the future saturating/packed unit; it is genuinely out of the base `add.u32` scope because base `add` is "Supported on all target architectures".
- OQ-5 (v2) — The exact Lean encoding of the 1-bit predicate register value domain remains a Lean-mapping decision for the mapping phase.
- OQ-6 (v2) — Compilation-level register notes (spilling, ABI/function-scope, legacy module-scope) may constrain a future program-level semantics; excluded from the instruction-local unit.
- OQ-2 (v2) — Overflow/wrap behavior of non-saturating `add.u32` is deliberately deferred to the semantic-interpretation phase; not an architecture question.
- NF-2 — PRF-5's non-vacuity depends on the execution relation not being defined via D-19; must be managed by the Proof Engineer.
- Hash bookkeeping — The SHA-256 of the v2 artifact (and the v1 critique file, as cited by v2) should be recorded from the filesystem at Gate A; not computable with the available read-only tools.

## 8. Gate A readiness assessment

Ready to be presented to a human for Gate A review (this is not approval). F-1's BLOCKER is genuinely resolved, and every MAJOR finding from v1 (F-2, F-3, F-5, F-7, F-8, F-9) has been resolved or acceptably deferred. The remaining F-9 residual is acceptable for Gate A: the required official reads have all been performed and verified, and the two residual items (A-4/OQ-3 interpretation; OQ-1 future-unit meaning) are flagged and within the human's remit at this gate. The Gate A checklist in v2 Section 15 is now accurate, including all verified anchors.

The human reviewer should specifically:
1. Confirm the A-4/OQ-3 interpretation ("no state update" when the complete guard expression evaluates false) as the predication consequence, using the SF-24 examples as supporting evidence.
2. Note the NF-1 labeling nit (two unlabeled Section 8 statements) and the NF-2/NF-3 proof-phase notes.
3. Record the v2 artifact SHA-256 from the filesystem.

No Gate A approval is granted by this critique.

## 9. Critic independence statement

The critic did not edit, replace, or repair `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md`, `candidates/ptx/9.3/architecture/add-u32-foundation-v1.md`, or `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md`. No Lean code was written, no `add.u32` source bundle was created, no arithmetic or overflow semantics of `add.u32` were extracted, and no human gate was approved. All source verification was performed with the restricted read-only specification tools.
