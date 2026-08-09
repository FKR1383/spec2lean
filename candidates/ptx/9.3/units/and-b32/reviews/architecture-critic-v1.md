# Independent Architecture Critique — and-b32-foundation-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/and-b32/architecture/foundation-v1.md` (DRAFT — NOT HUMAN APPROVED), 275 lines.
- This critique is an independent semantic-critic review. It does not approve Gate A and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines).
- Source metadata consulted: `documents/sources/nvidia/ptx/9.3/source-manifest.json` (SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`, 38 content lines) and `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`, 3 lines).
- Run metadata consulted: `runs/ptx-9.3-and.b32-d33dfec2/run.json` (unit `and.b32`, stage ARCHITECTURE_CRITIQUE, revision 2, active execution `ses_01864dce8ffeHfIbsr9K31tLmk`).
- Prior critiques consulted as context: `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md` (findings F-1..F-10) and `candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v1.md` (findings F-1..F-5) and `architecture-critic-v2.md`, used to check that the and.b32 artifact applied those lessons.

## 2. Overall verdict

**READY FOR HUMAN GATE A (no substantive defects; all source evidence verified accurate; findings are MINOR/NOTE level and do not require revision before Gate A).**

The artifact is a disciplined, source-faithful architecture draft. All 22 source facts (SF-A1..SF-A22), all evidence-index line ranges, all six literal-search claims (E-A27), the program-context `and.b32` example (E-A26), and all document hashes were independently re-verified against the official HTML, manifest, and SHA256SUMS and are accurate. The scope bounding to the scalar `.b32` form of `and` (9.7.8.1) is documented transparently, with the `.pred`/`.b16`/`.b64` forms and sibling instructions explicitly excluded (D-0c, OQ-4). The four-label taxonomy (SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION) is respected throughout, including in Section 12, which correctly records ambiguity points as OPEN QUESTION entries with no fifth `AMBIGUITY` label family — the not.b32 F-1 defect is not present. Register/value/state foundations are grounded in actual register-chapter reads. Guard-false behavior is stated uniformly via the complete guard expression, avoiding the negated-guard phrasing defect. Validation obligations are distinguished from proof obligations, and proof-obligation families are relational and non-vacuous by design, with the PRF-6 vacuity risk recorded (A-10). The manifest/run unit discrepancy (`initial_formalization_unit` = `add.u32` vs. run unit `and.b32`) is handled correctly as project metadata. The artifact makes no claim that Gate A is ready and no gate was approved.

The findings below are all MINOR or NOTE level. None requires a change before the artifact is presented for human Gate A; F-3 is a recommended wording tightening for a later revision.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/and-b32/architecture/foundation-v1.md` — complete candidate read (275/275 lines, in two reads: lines 1-253 and 254-275).
- `runs/ptx-9.3-and.b32-d33dfec2/run.json` — read in full (61 lines).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` — read in full (38 lines).
- `documents/sources/nvidia/ptx/9.3/SHA256SUMS` — read in full (3 lines).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools:
  - `spec_fast_context(and.b32)` — `and` section 14256-14289 (anchor `logic-and-shift-instructions-and`), shared sections 9.3 (7537-7584), 5.1.1 (2613-2632), 5.2.1 (3015-3062), 5.4 (3741-3788), 9.1 (7505-7512), 5.2.2 (3070-3084);
  - anchor `logic-and-shift-instructions` (line 14236) with lines 14234-14256 (section 9.7.8 intro and instruction list);
  - anchor `logic-and-shift-instructions-or` (line 14290) with lines 14290-14324 (section 9.7.8.2; immediate example at 14319);
  - anchor `logic-and-shift-instructions-xor` (line 14324) with lines 14324-14359 (section 9.7.8.3; immediate example at 14354);
  - anchor `ptx-instructions` (line 7513) with lines 7513-7537 (section 9.2);
  - anchor `special-register-state-space` (line 2633) with lines 2633-2641 (section 5.1.2);
  - anchor `parameterized-variable-names` (line 3933) with lines 3933-3950 (section 5.4.6);
  - anchor `function-declarations-and-definitions` (line 6139) with lines 6139-6142 (section 7.1);
  - span 6255-6265 (`st.param`/`ld.param` predication exception at 6260-6261);
  - span 3062-3068 (type-compatibility rules at 3062-3066);
  - span 24941-24962 (mbarrier example region; `and.b32 parArg, i, 1;` at 24954);
  - anchor `parallel-synchronization-and-communication-instructions-mbarrier-test-wait-try-wait` (line 24774);
  - anchor `instructions` (line 8718) with lines 8718-8724 (section 9.7 intro, predicability);
  - literal search `and.b32` (6 matches: lines 14285, 14286, 14616, 16780, 23245, 24954);
  - literal search `@p and.b32` (0 matches).
- Accepted artifacts cited by the candidate as structural templates were confirmed to exist: `accepted/ptx/9.3/not-b32/architecture/foundation-v2.md`, `accepted/ptx/9.3/mov-b32/architecture/foundation-v1.md`, `accepted/ptx/9.3/xor-b32/architecture/foundation-v1.md`.
- Prior critique files cited by the candidate were confirmed to exist: `candidates/ptx/9.3/reviews/add-u32-foundation-v1-critic.md`, `candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v1.md`, `candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v2.md`.
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is an architecture candidate only. No semantic interpretation, source bundle, or Lean mapping was reviewed because none was provided at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | NOTE | E-A18 (Section 14, line 218), SF-A16 (line 41) | Evidence-index span for section 5.1.1 is 2613-2631 but the section (including closing tag) spans 2613-2632; one-line span-boundary imprecision with no semantic impact |
| F-2 | NOTE | E-A24 (Section 14, line 224), SF-A22 (line 47), A-8 (line 170) | Read span 3070-3076 for section 5.2.2 is a subset of the full section (3070-3084); the quoted restriction list (3074-3075) is correct, but the section tail (3077-3084, wider-operand note for `ld`/`st`/`cvt`) was not read; A-8 honestly scopes the negative evidence to "the sections read" |
| F-3 | MINOR | D-17 (line 111), OQ-1 (line 186), OQ-7 (line 192) | D-17's opening sentence "Source operands `a` and `b` may be register variables or constant immediates" can be read as asserting immediates in both source positions; the read evidence supports immediates only in position `b` (SF-A8, E-A26). The same entry and OQ-1 immediately qualify this, so the risk is low, but tightening the wording would remove downstream drift risk |
| F-4 | NOTE | run.json execution record (line 51); foundation-v1.md length | Spec-architect's recorded summary reports "276 lines" for the artifact, which contains 275 lines; trivial metadata off-by-one in the execution record |
| F-5 | NOTE | Section 1 metadata note (line 11); manifest lines 9-15; run.json line 7 | Source manifest records `initial_formalization_unit` = `add.u32` while this run formalizes `and.b32`; the architecture handles this correctly as project metadata (run metadata authoritative per orchestrator contract) but the manifest record should eventually be reconciled |

## 5. Findings detail

### F-1 — NOTE — E-A18 span excludes the section closing tag

- **Exact location:** Section 14, evidence index entry E-A18 (line 218) records `register-state-space` as lines 2613-2631; Section 3, SF-A16 (line 41) cites content at 2617, 2621-2624, 2626-2627, 2627-2630, 2630-2631.
- **Relevant official evidence:** `ptx_isa_9.3.html` — section 5.1.1 (anchor `register-state-space`) begins at line 2613 and its closing `</section>` tag is at line 2632 (`spec_fast_context` reports startLine 2613, sectionEndLine 2632).
- **Description:** The evidence-index span 2613-2631 covers all content lines but excludes the closing tag at line 2632. All quoted content is within the recorded span; no quoted fact is affected.
- **Consequence:** None beyond a one-line span-boundary imprecision in the evidence index.
- **Required owner:** Spec Architect (optional).
- **Required revision:** Optionally record E-A18 as 2613-2632 in the next revision; not required before Gate A.
- **Human review required:** No.

### F-2 — NOTE — E-A24 read span is a subset of section 5.2.2

- **Exact location:** Section 14, evidence index entry E-A24 (line 224) records `restricted-use-of-sub-word-sizes` as lines 3070-3076; Section 3, SF-A22 (line 47) quotes the restriction list at 3074-3075; ASSUMPTION A-8 (line 170) states "no `.b32`-specific restriction for `and` was found in the sections read".
- **Relevant official evidence:** `ptx_isa_9.3.html` — section 5.2.2 (anchor `restricted-use-of-sub-word-sizes`) spans lines 3070-3084; the `.u8`/`.s8`/`.b8` restriction list is at 3074-3075; lines 3077-3084 discuss the wider-operand convenience rule for `ld`, `st`, and `cvt`.
- **Description:** The recorded read span 3070-3076 covers the restriction list but not the section tail (3077-3084). The negative-evidence claim in A-8 is explicitly scoped to "the sections read", so it is honest and remains valid: the tail discusses `ld`/`st`/`cvt` wider operands and introduces no `.b32`-specific restriction for `and`. If a later phase needs the full section, the read span should be widened.
- **Consequence:** None for the architecture; the negative-evidence conclusion is unaffected.
- **Required owner:** Spec Architect / Semantic Extractor (optional).
- **Required revision:** Optionally widen E-A24 to 3070-3084 in a later revision; not required before Gate A.
- **Human review required:** No.

### F-3 — MINOR — D-17 opening sentence slightly overstates immediate support for source `a`

- **Exact location:** Section 7, DESIGN CHOICE (D-17) (line 111): "Source operands `a` and `b` may be register variables or constant immediates."; the same entry immediately continues "Whether source `a` (as opposed to `b`) may be an immediate, and how immediate constants are typed, are semantic-phase questions (OQ-1, OQ-7)."; OPEN QUESTION OQ-1 (line 186) and OQ-7 (line 192).
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 14285-14286 (`and.b32  x,q,r;` and `and.b32  sign,fpvalue,0x80000000;` — the immediate `0x80000000` is in position `b`); line 24954 (`and.b32 parArg, i, 1;` — the immediate `1` is in position `b`). Every read example uses a register in position `a`.
- **Description:** Read literally, D-17's first sentence claims that both source positions accept immediates. The verified evidence demonstrates immediates only in position `b`. The same design-choice entry and OQ-1/OQ-7 immediately qualify the claim, and D-17's grounding (SF-A8, E-A26, SF-A10) is accurate, so the practical risk of downstream semantic drift is low. However, because the architecture is the traceability backbone for the semantic phase, an unqualified sentence like this could be mistaken for an evidenced design commitment if read in isolation.
- **Consequence:** Low risk that the semantic extractor encodes `a`-immediates without evidence; OQ-1 already requires VAL-2 and D-17 to be revisited at the semantic phase.
- **Required owner:** Spec Architect.
- **Required revision:** Recommended (not required before Gate A): rephrase D-17 to "Source operand `b` may be a register variable or a constant immediate (SF-A8, E-A26); whether source operand `a` may also be an immediate is unresolved (OQ-1)" — or otherwise make the `b`-only evidence explicit in the first sentence.
- **Human review required:** No (visible in the artifact text; no Gate A impact).

### F-4 — NOTE — run.json records a 276-line count; artifact has 275 lines

- **Exact location:** `runs/ptx-9.3-and.b32-d33dfec2/run.json`, execution record line 51 (spec-architect summary: "foundation-v1.md (276 lines)"); artifact file length is 275 lines per the read tool.
- **Relevant official evidence:** None required — internal run-metadata consistency.
- **Description:** The architect's recorded summary states the artifact has 276 lines; the file actually contains 275 lines. This is a one-line counting discrepancy in the execution record (possibly counting a trailing newline).
- **Consequence:** None; no semantic or traceability impact.
- **Required owner:** Orchestrator (optional record correction).
- **Required revision:** None required.
- **Human review required:** No.

### F-5 — NOTE — Manifest/run unit discrepancy is documented but should be reconciled

- **Exact location:** Section 1 metadata note (line 11); `documents/sources/nvidia/ptx/9.3/source-manifest.json` lines 9-15; `runs/ptx-9.3-and.b32-d33dfec2/run.json` line 7.
- **Relevant official evidence:** Manifest `initial_formalization_unit` = `add.u32` (lines 9-15); run metadata `unit` = `and.b32`.
- **Description:** The source manifest still records `add.u32` as the initial formalization unit while this run formalizes `and.b32`. The architecture correctly identifies this as project metadata (not specification evidence), correctly notes that the orchestrator contract makes run metadata authoritative, and does not treat the manifest record as evidence about `and`. The handling is correct.
- **Consequence:** No semantic impact; a residual project-metadata inconsistency that could confuse future traceability queries if left unaddressed.
- **Required owner:** Orchestrator / Source Curator.
- **Required revision:** Update the manifest `initial_formalization_unit` record (or add a per-run override) when convenient; not an architecture defect.
- **Human review required:** No.

## 6. Source-verification notes

Specification-tool calls used in this critique: 17 restricted reads/searches (all verified directly).

All explicit SOURCE FACT claims (SF-A1..SF-A22) were re-verified and are accurate against the official HTML and manifest:

- SF-A1: anchor `logic-and-shift-instructions-and` at line 14256; section 9.7.8.1 spans 14256-14289. Confirmed.
- SF-A2: syntax `and.type d, a, b;` at lines 14264-14266; type set `{ .pred, .b16, .b32, .b64 }` at line 14266. Confirmed.
- SF-A3: "Bitwise AND." at line 14261; "Compute the bit-wise and operation for the bits in `a` and `b`." at line 14270. Confirmed.
- SF-A4: Semantics block `d = a & b;` at lines 14271-14275 (code line 14273). Confirmed.
- SF-A5: Notes at lines 14276-14278 ("The size of the operands must match, but not necessarily the type." at 14277; "Allowed types include predicate registers." at 14278). Confirmed.
- SF-A6: "Introduced in PTX ISA version 1.0." at line 14280. Confirmed.
- SF-A7: "Supported on all target architectures." at line 14282. Confirmed.
- SF-A8: Examples `and.b32  x,q,r;` at 14285 and `and.b32  sign,fpvalue,0x80000000;` at 14286; immediate `0x80000000` is in source position `b`. Confirmed.
- SF-A9: family intro at lines 14240-14243; instruction list (and, or, xor, not, cnot, lop3, shf, shl, shr) at 14244-14255. Confirmed.
- SF-A10: `or` section 14290-14323 with example at 14319 (printed without comma between the `mask` tokens and without terminating semicolon — both anomalies recorded faithfully); `xor` section 14324-14357 with examples `xor.b32  d,q,r;` at 14353 and `xor.b16  d,x,0x0001;` at 14354. Confirmed.
- SF-A11: anchor `instructions` at 8718; "All PTX instructions may be predicated." at lines 8722-8723. Confirmed.
- SF-A12: anchor `predicated-execution` at 7537; predicate registers virtual/`.pred` at 7541-7542; guard syntax `@{!}p` and unconditional-execution rule at 7547-7550; setp note at 7551-7552; examples `@p add.s32 j, j, 1;` at 7562 and `@!p bra L1;` at 7570. Confirmed.
- SF-A13: anchor `ptx-instructions` at 7513; 0-4 operands plus guard at 7517-7518; destination/source roles at 7526-7527; bit bucket at 7534-7535. Confirmed.
- SF-A14: anchor `fundamental-types` at 3015; register variables always of a fundamental type at 3019-3022; Table 8 anchor at 3025; `.b32` under "Bits (untyped)" at 3053-3054; `.pred` at 3057-3058. Confirmed.
- SF-A15: compatibility rules at lines 3062-3066 ("The bit-size type is compatible with any fundamental type having the same size."). Confirmed.
- SF-A16: anchor `register-state-space` at 2613; fast storage at 2617; typed/untyped and widths and 1-bit predicate at 2621-2624; not fully addressable at 2626-2627; ABI/function-scope and legacy notes at 2627-2630; alignment at 2630-2631. Confirmed.
- SF-A17: anchor `special-register-state-space` at 2633; `.sreg` predefined, platform-specific at 2637-2639. Confirmed.
- SF-A18: anchor `variables` at 3741; declaration rule at 3753-3754; predicate-only-in-register at 3755. Confirmed.
- SF-A19: anchor `parameterized-variable-names` at 3933; `%r<100>` declares `%r0`-`%r99` at 3940-3943; shorthand rule at 3946-3947. Confirmed.
- SF-A20: anchor `format-and-semantics-of-instruction-descriptions` at 7505; quoted text at 7509-7511. Confirmed.
- SF-A21: `st.param`/`ld.param` predication exception at lines 6260-6261 (inside section 7.1, anchor `function-declarations-and-definitions`). Content confirmed; anchor recorded correctly (not.b32 F-2 lesson applied).
- SF-A22: anchor `restricted-use-of-sub-word-sizes` at 3070; restriction list at 3074-3075; `.b32` not in the list. Confirmed; read-span caveat in F-2.
- Negative searches: `and.b32` 6 matches (14285, 14286 — this section's own examples; 14616 — `lop3.and.b32 _|p, a, b, c, 0x3f, q;`; 16780 — `multimem.ld_reduce.and.b32 val1_b32, [addr1];`; 23245 — `@p red.global.and.b32 [p],my_val;`; 24954 — logic `and.b32 parArg, i, 1;` in the mbarrier example). `@p and.b32` 0 matches. All confirmed exactly as recorded.
- E-A26: mbarrier example region lines 24941-24962 (section 9.7.14.16.19, anchor `parallel-synchronization-and-communication-instructions-mbarrier-test-wait-try-wait` at line 24774); `and.b32 parArg, i, 1;` at 24954. Confirmed.
- Document hashes and line counts match the tool metadata and manifest: HTML SHA-256 `e2095c4a...`, 47,743 lines; manifest SHA-256 `622e6ce0...`, 38 content lines (39 total source lines including a trailing empty line); SHA256SUMS SHA-256 `e02f4fea...`, 3 lines (HTML and PDF hashes recorded); PDF SHA-256 `769cc12e...` as recorded in the manifest. Confirmed.

No SOURCE FACT mislabeling, phantom cross-references, or source-faithfulness problems were found. The project-status/scope classification as metadata/DESIGN CHOICE (add.u32 F-1 lesson) is correct. The four-label taxonomy is respected with no fifth label (add F-2 / not F-1 lesson applied). Register/value/state foundations are grounded in actual register-chapter reads (add F-3/F-9 lesson applied). Guard-false behavior is stated uniformly via the complete guard expression with no "negated guard true means no-op" phrasing (add F-5/F-6 lessons applied). Validation vs. proof obligations are distinguished; proof obligations are relational and non-vacuous (add F-7 lesson applied); PRF-6 vacuity risk is recorded (mov/not F-3 lesson applied). Anchors are verified and recorded in the evidence index (add F-8 lesson applied). Cross-references only point to sections and anchors actually present; unrelated `lop3`/`multimem`/`red` matches are identified and excluded (add F-10 lesson applied). The official `or.b32  mask mask,0x00010001` example's two printed anomalies (missing comma; missing semicolon) are recorded faithfully (not F-4 lesson applied). The `function-declarations-and-definitions` anchor is recorded for the predication exception (not F-2 lesson applied). The manifest/run discrepancy is labeled metadata (not F-5 lesson applied).

## 7. Required revisions (consolidated)

No substantive revision is required before Gate A.

Optional refinements (recommended, not blocking):

1. Tighten D-17's first sentence so that the immediate-source support is explicitly scoped to position `b` (F-3).
2. Optionally record E-A18 as 2613-2632 (F-1) and widen E-A24 to 3070-3084 (F-2) for evidence-index precision.
3. Reconcile the manifest `initial_formalization_unit` metadata with the `and.b32` run (F-5) — orchestrator-level, not architecture-level.
4. Correct the 276 vs 275 line-count note in the run execution record (F-4) — cosmetic.

## 8. Residual open questions

- Is the value-domain membership obligation (PRF-6) meaningful under the eventual Lean state representation, or should it be a definitional well-formedness check (A-10, mov/not F-3)?
- Is the exact operand-typing formulation for `and.b32` (size-based, per SF-A5/SF-A15) to be settled in the semantic phase as OQ-7 anticipates, including whether a register declared `.u32`, `.s32`, or `.f32` is an acceptable operand for instruction type `.b32`, and how immediate values (evidenced for position `b`, SF-A8/E-A26) are typed?
- Will the human Gate A reviewer confirm the bounded base scope (scalar `.b32`; `.pred`/`.b16`/`.b64` forms out of scope) as the intended `and.b32` unit (D-0c, OQ-4)?
- The guard-false "no state update" interpretation (A-4, OQ-3) remains an assumption based on the "controls conditional execution" wording; it requires human approval and re-verification at the semantic phase.
- Whether source operand `a` may be a constant immediate (OQ-1) and whether the bit bucket `_` is a permitted destination for `and.b32` (OQ-2) remain unresolved and must be resolved in the semantic-interpretation phase before PRF-3 and the full operand-typing rule are treated as faithful.

## 9. Gate A readiness assessment

Ready for presentation to Human Gate A. All source facts, evidence-index entries, search claims, and document hashes were independently re-verified and are accurate. The four-label taxonomy is respected with no fifth label family. Scope bounding, predication architecture, register/value/state foundations, validation/proof obligation families, and version/target representation are disciplined and grounded in official reads. The findings in this critique (F-1, F-2, F-4, F-5 NOTE; F-3 MINOR) are cosmetic or wording-level and do not require changes before the artifact is presented for human review. This assessment is not a Gate A approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/and-b32/architecture/foundation-v1.md`. No Lean code was written, and no `and.b32` bitwise-and semantics were extracted during this review. No gates were approved and nothing was promoted to `accepted/`.
