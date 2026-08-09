# Independent Architecture Critique — xor-b32-foundation-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/xor-b32/architecture/foundation-v1.md` (DRAFT — NOT HUMAN APPROVED), 273 lines read in full.
- This critique is an independent semantic-critic review. It does not approve Gate A and does not edit or repair the reviewed artifact.
- Run metadata consulted: `runs/ptx-9.3-xor.b32-23b2e519/run.json` (unit `xor.b32`, stage ARCHITECTURE_CRITIQUE, revision 2, attempt 1, expected artifact `candidates/ptx/9.3/units/xor-b32/reviews/architecture-critic-v1.md`).
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines), via the restricted specification tools in this run.
- Source metadata consulted: `documents/sources/nvidia/ptx/9.3/source-manifest.json` (SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`) and `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`).
- Prior critiques consulted as context: `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md` (findings F-1..F-10) and `candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v1.md` (findings F-1..F-5), used to check that this artifact applied those lessons and does not regress into the not-b32 F-1 taxonomy defect.
- Missing-input declaration: this is an architecture-stage critique. No semantic interpretation, source bundle, Lean definitions, theorem obligations, or proofs were provided or expected at this stage; none are claimed to have been reviewed.

## 2. Overall verdict

**SUITABLE FOR GATE A (no substantive changes required; only MINOR/NOTE findings).**

The artifact is a careful, source-faithful architecture draft. I independently re-verified, in this run, all 22 source facts (SF-X1..SF-X22), all six literal-search claims (E-26), all evidence-index anchors and line ranges, and all document hashes against the official PTX 9.3 HTML and metadata. Every quoted fact matches the source:

- The `xor` section (anchor `logic-and-shift-instructions-xor`, lines 14324-14357): syntax `xor.type d, a, b;`, `.type = { .pred, .b16, .b32, .b64 }`, description, Semantics `d = a ^ b;`, Notes (size matching; predicates), PTX ISA Notes (1.0), Target ISA Notes (all architectures), Examples `xor.b32  d,q,r;` and `xor.b16  d,x,0x0001;` — all accurate.
- Family intro (anchor `logic-and-shift-instructions`, lines 14236-14255): "fundamentally untyped ... operands of the same size", `and`/`or`/`xor`/`not` operate on predicates, instruction list — accurate.
- Sibling `or` section (anchor `logic-and-shift-instructions-or`, lines 14290-14323): same notes/version/target, immediate example `or.b32  mask mask,0x00010001` printed without comma between `mask` tokens and without terminating semicolon, `or.pred  p,q,r;` — accurate, including the faithful reporting of the source's two anomalies.
- Shared sections (9.7 intro predicability at 8718; 9.3 predicated execution at 7537; 9.2 operand format and bit bucket at 7513; 9.1 format at 7505; 5.2.1 fundamental types and compatibility at 3015/3062-3066; 5.2.2 sub-word restriction at 3070; 5.1.1 register state space at 2613; 5.1.2 special register at 2633; 5.4 variables at 3741; 5.4.6 parameterized names at 3933; 7.1 `st.param`/`ld.param` predication exception at 6260-6261): all quoted facts accurate.
- Negative searches: `@p xor` = 0 matches; `xor.b32` = 2 matches (line 14353, the section's own example; line 23754, `redux.sync.xor.b32 dst, src, mask;` inside the `redux.sync` section, correctly identified as a different instruction and excluded from scope).
- Hashes: HTML, manifest, and SHA256SUMS hashes all match the actual source files as read through the restricted tools.

The four-label taxonomy discipline (SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION) is correctly applied: the not.b32 foundation v1 MAJOR defect (a fifth `AMBIGUITY` label contradicting the artifact's own four-label claims) does not recur here. Section 12 carries no `AMBIGUITY` labels; ambiguity points are recorded solely as OPEN QUESTION entries. Negative evidence is labeled ASSUMPTION (A-8, A-9); deferred interpretation points are labeled OPEN QUESTION (OQ-1..OQ-8). The guard-false consequence is stated uniformly via the complete guard expression (D-19, D-20, PRF-4, PRF-5) without the negated-guard phrasing defect found in add.u32 foundation v1. Validation obligations are separated from proof obligations, and proof-obligation families are relational and non-vacuous by design (D-25, D-26, Section 10); the PRF-6 vacuity risk is recorded (A-10).

The artifact correctly stays within architecture scope: it records `d = a ^ b;` as a source fact (SF-X4) but does not extract instruction-level semantics, write Lean code, or construct a source bundle (D-0b, D-27..D-33). Scope is bounded to the scalar `.b32` form with the `.pred`/`.b16`/`.b64` forms and sibling instructions explicitly out of scope (D-0c, OQ-4). Cross-references to prior critiques and accepted templates are resolvable (no phantom references): `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md` exists; the not.b32 critique (findings F-1..F-5) exists at `candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v1.md`; `accepted/ptx/9.3/not-b32/architecture/foundation-v2.md` and `accepted/ptx/9.3/mov-b32/architecture/foundation-v1.md` exist.

Findings F-1..F-3 below are MINOR/NOTE and do not require changes before Gate A. I am marking the artifact ready for Human Gate A review; I do not approve Gate A myself.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/xor-b32/architecture/foundation-v1.md` — complete candidate read (273/273 lines).
- `runs/ptx-9.3-xor.b32-23b2e519/run.json` — read in full (61 lines).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` — read in full (38 lines).
- `documents/sources/nvidia/ptx/9.3/SHA256SUMS` — read in full (3 lines).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools:
  - anchor `logic-and-shift-instructions-xor` (line 14324), span 14320-14360 (section 9.7.8.3, full `xor` section);
  - anchor `logic-and-shift-instructions` (line 14236), span 14234-14256 (section 9.7.8 intro and instruction list);
  - anchor `logic-and-shift-instructions-or` (line 14290), span 14288-14324 (section 9.7.8.2; immediate example at 14319);
  - anchor `instructions` (line 8718), span 8716-8726 (section 9.7 intro, predicability);
  - anchor `predicated-execution` (line 7537), span 7537-7584 (section 9.3; guard examples);
  - anchor `ptx-instructions` (line 7513), span 7511-7538 (section 9.2; operand format, bit bucket);
  - anchor `format-and-semantics-of-instruction-descriptions` (line 7505), span 7505-7512 (section 9.1);
  - anchor `fundamental-types` (line 3015), span 3015-3070 (section 5.2.1; compatibility at 3062-3066);
  - anchor `fundamental-types-fundamental-type-specifiers` (line 3025), span 3025-3061 (Table 8);
  - anchor `register-state-space` (line 2613), span 2613-2632 (section 5.1.1);
  - anchor `special-register-state-space` (line 2633), span 2631-2641 (section 5.1.2);
  - anchor `variables` (line 3741), span 3741-3788 (section 5.4);
  - anchor `parameterized-variable-names` (line 3933), span 3931-3951 (section 5.4.6);
  - anchor `restricted-use-of-sub-word-sizes` (line 3070), span 3070-3084 (section 5.2.2);
  - anchor `function-declarations-and-definitions` (line 6139), span 6138-6143; span 6255-6263 (`st.param`/`ld.param` predication exception at 6260-6261);
  - literal search `@p xor` (0 matches); literal search `xor.b32` (2 matches: line 14353 and line 23754 `redux.sync.xor.b32 dst, src, mask;`).
- Prior critiques consulted as context (listed in Section 1).
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is an architecture candidate only. No semantic interpretation, source bundle, or Lean mapping was reviewed because none was provided at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | Section 12 (lines 174-183) | The Section 12 cross-reference table lists only OQ-1, OQ-2, OQ-4 as ambiguity points, while the sentence above it claims "Points of ambiguity ... are cross-referenced below"; OQ-3 (guard-false consequence), OQ-7 (operand typing), and OQ-8 (exclusive-or fidelity statement) are also ambiguity-type entries deferred to later phases and are not cross-referenced |
| F-2 | NOTE | Section 1/Section 2 references to "the not.b32 foundation v1 critique (findings F-1..F-5)" | The reference gives no path; the path is resolvable (`candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v1.md`, which indeed contains findings F-1..F-5), but a path would complete traceability |
| F-3 | NOTE | Run metadata (run.json execution response) vs artifact | Spec-architect execution log states the artifact is 274 lines; the file is 273 lines (trailing-newline counting). No semantic impact |

## 5. Findings detail

### F-1 — MINOR — Section 12 ambiguity cross-reference table is partial

- **Exact location:** Section 12 "Ambiguity points" (lines 174-183). The section states "Points of ambiguity are therefore recorded as OPEN QUESTION entries (Section 13) and are cross-referenced below" and then lists only OQ-1 (immediates), OQ-2 (bit bucket), and OQ-4 (other forms) in the table.
- **Relevant official evidence:** None required — this is an internal-consistency/traceability finding about the artifact's own classification structure.
- **Description:** The four-label discipline is correctly applied (no `AMBIGUITY` label; the not.b32 F-1 defect does not recur). However, the "cross-referenced below" claim is incomplete: OQ-3 (the exact consequence of a false guard, an interpretation pending human approval), OQ-7 (how the operand-typing rule is formulated), and OQ-8 (the exact statement of exclusive-or fidelity) are likewise ambiguity-type OPEN QUESTION entries that are not cross-referenced in the Section 12 table.
- **Consequence:** None for semantic content. Minor traceability gap: a Gate A reader scanning Section 12 would not see all deferred ambiguity points in one place.
- **Required owner:** Spec Architect.
- **Required revision:** Optional before Gate A; in the next revision, either complete the Section 12 table with OQ-3, OQ-7, OQ-8 (and decide whether OQ-5/OQ-6 are ambiguity points or merely deferred Lean-mapping/compilation questions), or reword the lead-in to state that the table cross-references a representative subset.
- **Human review required:** No.

### F-2 — NOTE — Not.b32 critique reference lacks a path

- **Exact location:** Section 2 (line 20) and Section 15 (line 230): "the not.b32 foundation v1 critique (findings F-1..F-5)".
- **Relevant official evidence:** None; project-artifact reference.
- **Description:** The path is not given. I resolved it to `candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v1.md`, which exists and contains findings F-1..F-5 as cited. No phantom reference; the cited findings match.
- **Consequence:** None beyond a one-line traceability convenience.
- **Required owner:** Spec Architect.
- **Required revision:** Optional; add the path in the next revision.
- **Human review required:** No.

### F-3 — NOTE — Line-count metadata discrepancy in run log

- **Exact location:** `runs/ptx-9.3-xor.b32-23b2e519/run.json` execution response ("274 lines") vs the artifact file (273 lines as read).
- **Relevant official evidence:** None; run metadata.
- **Description:** The spec-architect's stage summary reports the artifact as 274 lines; the artifact as read contains 273 lines. This is almost certainly a trailing-newline counting convention difference (`wc -l` vs content lines). It does not affect any content.
- **Consequence:** None.
- **Required owner:** Spec Architect.
- **Required revision:** None required.
- **Human review required:** No.

## 6. Confirmed strengths (no action required)

- All source facts, anchors, line ranges, and hashes verified accurate against the official PTX 9.3 evidence (Section 2, Section 3).
- Four-label discipline correctly applied; not.b32 F-1 defect (fifth `AMBIGUITY` label) does not recur.
- add.u32 foundation v1 lessons applied: project status/scope classified as metadata/DESIGN CHOICE, register-chapter evidence read, uniform guard-false phrasing, relational non-vacuous obligations, verified anchors, negative evidence labeled ASSUMPTION, no phantom cross-references.
- PRF-6 vacuity risk explicitly recorded (A-10) and deferred to the semantic phase, per the mov/not F-3 lesson.
- Version/target representation bounded to base `xor.b32` (PTX ISA 1.0; all target architectures); unrelated `redux.sync.xor` correctly identified and excluded.
- Scope discipline: no instruction-level semantics beyond SF-X4, no Lean code, no source bundle (D-0b, D-27..D-33).

## 7. Gate A readiness statement

- This critique determines that the architecture candidate is suitable to be presented for Human Gate A review.
- I do not approve Gate A; approval is a human decision.
- Findings F-1..F-3 do not require changes before Gate A. If the Spec Architect wishes, F-1 and F-2 may be incorporated into the next revision for fuller traceability.

## 8. Required owners and human-review flags

- F-1 (MINOR): Spec Architect; human review not required.
- F-2 (NOTE): Spec Architect; human review not required.
- F-3 (NOTE): Spec Architect; human review not required.
- No BLOCKER or MAJOR findings.
