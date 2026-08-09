# Independent Architecture Critique — not-b32-foundation-v2

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/not-b32/architecture/foundation-v2.md` (DRAFT — NOT HUMAN APPROVED), 299 lines, SHA-256 `84726b1b98120a036e1a1dc32934e71ac1af3eb08cfde4c58c760e4b1ad55db7`.
- This critique is an independent semantic-critic review. It does not approve Gate A and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines).
- Source metadata consulted: `documents/sources/nvidia/ptx/9.3/source-manifest.json` (SHA-256 `622e6ce0d3114a909a62726530955993b5f2b98d2f60e45ae1ceb429512208f2`, 38 content lines) and `documents/sources/nvidia/ptx/9.3/SHA256SUMS` (SHA-256 `e02f4feadfce614282d3d4774ed21dd87985202d4ea9ad84ead60c688a6c0ecd`, 3 lines).
- Run metadata consulted: `runs/ptx-9.3-not.b32-c454d1bc/run.json` (unit `not.b32`, stage ARCHITECTURE_CRITIQUE, attempt 2, run revision 4; history entries for foundation-v1, architecture-critic-v1, and foundation-v2).
- Prior review consulted: `candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v1.md` (verdict REVISE; findings F-1..F-5) — the revision driver for foundation-v2.
- Prior artifact consulted for diff verification: `candidates/ptx/9.3/units/not-b32/architecture/foundation-v1.md` (immutable prior revision).

## 2. Overall verdict

**SUITABLE FOR PRESENTATION TO HUMAN GATE A (no substantive revision required; Gate A not approved).**

The v1 MAJOR finding (F-1: fifth `AMBIGUITY` label) has been fully and correctly resolved. Independent re-verification confirms:

- No active fifth label remains anywhere in the artifact. The only remaining `AMB`/`AMBIGUITY` text occurs in six places, all of which are historical/descriptive mentions inside the revision narrative (Section 1 status note, Section 2 critique-addressed list, Section 12 revision note, Section 15 finding-resolution table, the add.u32 lesson row, and the Section 16 checklist item). None is a labeled architectural statement, and each explicitly states that the label family was removed.
- Section 12 is now an ambiguity-point cross-reference table in which every entry is labeled OPEN QUESTION and maps to exactly one OPEN QUESTION entry (OQ-1, OQ-2, OQ-4). The mapping matches the v1 critique's preferred option (a).
- Section 15 (line 257) and Section 16 (checklist items at lines 273 and 282) now consistently claim and enforce the four-label taxonomy SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION. The artifact's own Gate A checklist is therefore self-consistent.
- The optional F-2 evidence-index fix was applied: E-23 and SF-N21 now record the determinable anchor `function-declarations-and-definitions` (line 6139) with the exception list item at lines 6260-6261. Independently verified.
- F-3 remains appropriately deferred to the semantic phase (vacuity note retained in A-10 and in the PRF-6 non-vacuity note).
- F-4 is now recorded faithfully (both printed anomalies of the official `or` example at line 14319: missing comma between the `mask` tokens and missing terminating semicolon). Independently verified.
- F-5 remains handled correctly as project metadata.

All 22 source facts (SF-N1..SF-N22), all six literal-search claims (E-26), all evidence-index anchors and line ranges (E-2..E-25), and all document hashes were re-verified against the official HTML and metadata sources in this pass and are accurate. No new MAJOR or MINOR defects were found. Two NOTE-level metadata observations (N-1, N-2) are recorded for completeness; neither requires a revision before Gate A.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/not-b32/architecture/foundation-v2.md` — complete candidate read (299/299 lines) plus a full structural diff against foundation-v1 (103 line changes reviewed).
- `candidates/ptx/9.3/units/not-b32/architecture/foundation-v1.md` — read in full (271 lines per read tool; 272 lines per candidate/diff tool — see N-1).
- `candidates/ptx/9.3/units/not-b32/reviews/architecture-critic-v1.md` — read in full (171 lines).
- `runs/ptx-9.3-not.b32-c454d1bc/run.json` — read in full (91 lines).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` — read in full (38 content lines; tool metadata reports 39 total source lines including a trailing empty line).
- `documents/sources/nvidia/ptx/9.3/SHA256SUMS` — read in full (3 lines).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools:
  - anchor `logic-and-shift-instructions-not` (line 14358) with lines 14355-14398 (section 9.7.8.4, full `not` section, plus `cnot` section start at 14392);
  - anchor `logic-and-shift-instructions` (line 14236) with lines 14234-14261 (section 9.7.8 intro and instruction list);
  - anchor `logic-and-shift-instructions-or` (line 14290) with lines 14288-14325 (section 9.7.8.2; immediate example at 14319);
  - anchor `logic-and-shift-instructions-xor` (line 14324) with lines 14322-14360 (section 9.7.8.3; immediate example at 14354);
  - anchor `instructions` (line 8718) with lines 8716-8728 (section 9.7 intro, predicability);
  - anchor `predicated-execution` (line 7537) with lines 7535-7577 (section 9.3);
  - anchor `ptx-instructions` (line 7513) with lines 7511-7539 (section 9.2);
  - anchor `format-and-semantics-of-instruction-descriptions` (line 7505) with lines 7503-7515 (section 9.1);
  - anchor `fundamental-types` (line 3015) with lines 3013-3070 (section 5.2.1; includes Table 8 at 3025 and the compatibility rules at 3062-3066);
  - anchor `register-state-space` (line 2613) with lines 2611-2635 (section 5.1.1);
  - anchor `special-register-state-space` (line 2633) with lines 2631-2643 (section 5.1.2);
  - anchor `variables` (line 3741) with lines 3739-3759 (section 5.4 and 5.4.1 start);
  - anchor `parameterized-variable-names` (line 3933) with lines 3931-3951 (section 5.4.6);
  - anchor `restricted-use-of-sub-word-sizes` (line 3070) with lines 3068-3080 (section 5.2.2);
  - anchor `function-declarations-and-definitions` (line 6139) with lines 6137-6147 (section 7.1 heading) and span 6255-6265 (parameter-passing restrictions; predication exception at 6260-6261);
  - literal search `@p not` (0 matches), `not.b64` (0), `not.b16` (0), `not.b32 %` (0), `not.pred` (1 match, line 14388), `not.b32` (2 matches, lines 14387 and 14420).
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is an architecture candidate only. No semantic interpretation, source bundle, or Lean mapping was reviewed because none was provided at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MAJOR (v1; verified RESOLVED in v2) | Section 12; Sections 15-16 | Fifth `AMBIGUITY` label removed; ambiguity points now OPEN QUESTIONs OQ-1/OQ-2/OQ-4; cross-reference table labels every entry OPEN QUESTION; Sections 15 and 16 consistently claim the four-label taxonomy |
| F-2 | MINOR (v1; verified APPLIED in v2) | E-23, SF-N21 | Anchor `function-declarations-and-definitions` recorded (line 6139; exception item 6260-6261) |
| F-3 | MINOR (v1; verified DEFERRED) | PRF-6, A-10 | Vacuity risk retained; reclassification deferred to the semantic phase |
| F-4 | NOTE (v1; verified RECORDED) | SF-N10, E-11 | Both printed anomalies of the official `or` example recorded faithfully |
| F-5 | NOTE (v1; verified RECORDED) | Section 1 metadata note, E-1 | Manifest/run unit discrepancy handled correctly as project metadata |
| N-1 | NOTE (new) | Section 2 (line 18) | foundation-v1 described as "271 lines"; run history and candidate/diff tools report 272 lines. Tool-counting discrepancy on a prior artifact (trailing-line convention); no effect on the architecture |
| N-2 | NOTE (new) | Section 2 (line 17) | run.json cited as "revision 3; stage ARCHITECTURE" — accurate as-of-write (before the ARCHITECTURE→ARCHITECTURE_CRITIQUE transition that raised run revision to 4); no effect on the architecture |

## 5. Findings detail

### F-1 — MAJOR (v1) — Verified resolved in v2

- **Resolution verified:** foundation-v1's Section 12 `AMBIGUITY (AMB-1..AMB-3)` entries (deleted lines 176-178 of v1) are replaced by an ambiguity-point cross-reference table whose three rows map to OQ-1 (immediate source), OQ-2 (bit bucket), OQ-4 (other `not` forms as future units), with every row labeled OPEN QUESTION and the status column deferring or bounding them. This matches the mapping documented in the v1 critique and the architect's Section 2 note.
- **No residual active label:** a search of the v2 artifact for `AMB` returns six occurrences, all in the revision narrative (Section 1 status note, Section 2 F-1 bullet, Section 12 revision note, Section 15 finding-resolution row, the add.u32 F-2 lesson row, and the Section 16 checklist item). Each occurrence refers to the removed label historically; none labels a live architectural statement. The Section 16 checklist item (line 273) explicitly records the resolution.
- **Self-consistency restored:** Section 15 (line 257) claims "Only four labels are used: SOURCE FACT / DESIGN CHOICE / ASSUMPTION / OPEN QUESTION"; Section 16 checklist items (lines 273, 282) enforce the same four-label discipline and cross-reference OQ-1/OQ-2/OQ-4. The artifact's own Gate A checklist is now satisfied by its own statements.
- **Relevant official evidence:** none required — internal-consistency finding.
- **Consequence of resolution:** the taxonomy-drift defect identified in v1 is eliminated; downstream stages can rely on the four-label classification.
- **Required owner (was):** Spec Architect. **Status:** resolved; no further action before Gate A.
- **Human review required:** Yes (the resolution must be visible at Gate A; it is documented in Sections 2, 12, 15, 16).

### F-2 — MINOR (v1) — Verified applied in v2

- **Resolution verified:** E-23 (Section 14) now records `function-declarations-and-definitions` (section 7.1, line 6139; exception list item at lines 6260-6261); SF-N21 (Section 3) now carries the anchor context. Independently verified against the official HTML: anchor at line 6139, exception text "`st.param` and `ld.param` instructions used for argument passing cannot be predicated." spanning lines 6260-6261.
- **Consequence:** traceability chain completed; no semantic impact.
- **Human review required:** No.

### F-3 — MINOR (v1) — Verified deferred as recommended

- **Status verified:** PRF-6 (result-domain membership) retains the vacuity-risk note ("Vacuity risk noted: ... this obligation may need reclassification in the semantic phase (A-10; critique F-3).") and A-10 records the assumption about the eventual Lean representation. Reclassification is deferred to the semantic phase, matching the v1 critic's recommendation and the mov.b32 precedent.
- **Consequence:** none for Gate A; must be revisited before the theorem-strength gate.
- **Human review required:** Yes (at the semantic/theorem-strength gate, not Gate A).

### F-4 — NOTE (v1) — Verified recorded in v2

- **Status verified:** SF-N10 and E-11 now record both printed anomalies of the official example at line 14319: missing comma between the two `mask` tokens and missing terminating semicolon. Independently verified at line 14319 (`or.b32  mask mask,0x00010001`).
- **Consequence:** none.
- **Human review required:** No.

### F-5 — NOTE (v1) — Verified recorded in v2

- **Status verified:** Section 1 metadata note retains the manifest/run unit discrepancy (`add.u32` vs `not.b32`) as project metadata, cites the orchestrator contract, and flags reconciliation as an orchestrator-level action. Handling is correct; run metadata is authoritative for this run.
- **Consequence:** no semantic impact; residual project-metadata inconsistency for the orchestrator/Source Curator to reconcile when convenient.
- **Human review required:** No.

### N-1 — NOTE (new) — foundation-v1 line-count metadata

- **Exact location:** Section 2, line 18: "`candidates/ptx/9.3/units/not-b32/architecture/foundation-v1.md` (immutable prior revision, 271 lines)".
- **Description:** The v2 artifact (and the v1 critique) describe foundation-v1 as 271 lines, while the run history and the candidate/diff tools report 272 lines. Direct reads show the last content line is 271 (D-33) with a trailing empty line counted as line 272 by some tools. This is a tool line-counting convention difference on a prior, immutable artifact.
- **Consequence:** none for the architecture; cosmetic metadata only. No revision requested.
- **Required owner:** None (or Spec Architect if a later revision wishes to align the count).
- **Human review required:** No.

### N-2 — NOTE (new) — run.json citation is as-of-write

- **Exact location:** Section 2, line 17: "`runs/ptx-9.3-not.b32-c454d1bc/run.json` (run metadata; unit `not.b32`; stage ARCHITECTURE; revision 3; ...)".
- **Description:** The run.json now reports stage ARCHITECTURE_CRITIQUE and revision 4 because the ARCHITECTURE→ARCHITECTURE_CRITIQUE transition at 16:23:22Z (history entry) occurred after the architect read the file. The citation reflects the state at the time the revision was written and is accurate as-of-write.
- **Consequence:** none. No revision requested.
- **Human review required:** No.

## 6. Source-verification notes

Specification-tool calls used in this critique: 16 restricted reads/searches (all verified directly), plus candidate diff/read checks on the artifacts.

All explicit SOURCE FACT claims (SF-N1..SF-N22) were re-verified and remain accurate against the official HTML and manifest:

- SF-N1: anchor `logic-and-shift-instructions-not` at line 14358; section 9.7.8.4 spans 14358-14391. Confirmed.
- SF-N2: `not.type d, a;` at lines 14366-14367; type set `{ .pred, .b16, .b32, .b64 }` at line 14368. Confirmed (v2 line-range correction 14366-14368 is the precise content range; v1's 14366-14369 included the closing HTML tag).
- SF-N3: "Bitwise negation; one's complement." at line 14363; "Invert the bits in `a`." at line 14372. Confirmed.
- SF-N4: Semantics block `d = ~a;` at lines 14374-14377. Confirmed.
- SF-N5: Notes at lines 14378-14380 ("The size of the operands must match, but not necessarily the type." at 14379; "Allowed types include predicates." at 14380). Confirmed.
- SF-N6: "Introduced in PTX ISA version 1.0." at line 14382. Confirmed.
- SF-N7: "Supported on all target architectures." at line 14384. Confirmed.
- SF-N8: Examples `not.b32 mask,mask;` at 14387 and `not.pred p,q;` at 14388. Confirmed (v2 faithfully preserves the double-space between mnemonic and operands as printed).
- SF-N9: family intro at lines 14240-14243; instruction list (and, or, xor, not, cnot, lop3, shf, shl, shr) at 14244-14255. Confirmed.
- SF-N10: `or` section 14290-14323 with example at 14319 (printed without comma between the `mask` tokens and without terminating semicolon — both anomalies now recorded); `xor` section 14324-14357 with example `xor.b16 d,x,0x0001;` at 14354. Confirmed.
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
- SF-N21: `st.param`/`ld.param` predication exception at lines 6260-6261 (list item inside section 7.1, anchor `function-declarations-and-definitions`, line 6139). Content and anchor confirmed.
- SF-N22: anchor `restricted-use-of-sub-word-sizes` at 3070; restriction list at 3074-3075; `.b32` not in the list. Confirmed.
- Negative searches: `@p not` (0), `not.b64` (0), `not.b16` (0), `not.b32 %` (0), `not.pred` (1 match at 14388), `not.b32` (2 matches: 14387 `not.b32 mask,mask;` and 14420 `cnot.b32 d,a;`). All confirmed.
- Document hashes and line counts match the tool metadata and manifest: HTML SHA-256 `e2095c4a...`, 47,743 lines; manifest SHA-256 `622e6ce0...`, 38 content lines (tool reports 39 total source lines including a trailing empty line); SHA256SUMS SHA-256 `e02f4fead...`, 3 lines (HTML and PDF hashes recorded); PDF SHA-256 `769cc12e...` as recorded in the manifest and SHA256SUMS. Confirmed.

No SOURCE FACT mislabeling, phantom cross-references, source-faithfulness problems, or residual fifth-label usage were found. The F-1 fix is complete and self-consistent. The F-2 fix is accurate. F-3..F-5 are handled as recorded. The revision did not alter any substantive source-fact or design content other than the taxonomy reconciliation and evidence-index precision fixes; the full v1→v2 diff (103 line changes) was reviewed and is consistent with the architect's stated resolution list.

## 7. Required revisions (consolidated)

None. No substantive revision is required before presentation to Human Gate A.

Optional, non-blocking metadata notes for a future revision (not required for Gate A):

1. Align the foundation-v1 line-count metadata (271 vs 272) with the project's canonical counting convention (N-1).
2. Optionally re-record the run.json citation as "revision 3 as-of-write" to avoid confusion with the current run revision 4 (N-2).
3. Continue to defer PRF-6 reclassification (F-3) to the semantic phase, and reconcile the manifest `initial_formalization_unit` metadata (F-5) at the orchestrator level when convenient.

## 8. Residual open questions

- Is the value-domain membership obligation (PRF-6) meaningful under the eventual Lean state representation, or should it be a definitional well-formedness check (F-3)?
- Is the exact operand-typing formulation for `not.b32` (size-based, per SF-N5/SF-N15) to be settled in the semantic phase as OQ-7 anticipates, including how immediate values (if adopted per OQ-1) are typed?
- Will the human Gate A reviewer confirm the bounded base scope (scalar `.b32`; `.pred`/`.b16`/`.b64` forms out of scope) as the intended `not.b32` unit (D-0c, OQ-4)?
- The guard-false "no state update" interpretation (A-4, OQ-3) remains an assumption based on the "controls conditional execution" wording; it requires human approval and re-verification at the semantic phase.

## 9. Gate A readiness assessment

Ready for presentation to Human Gate A. The v1 taxonomy defect (F-1) is fully resolved and the artifact is now self-consistent with its own four-label discipline and Gate A checklist. All source evidence, evidence-index anchors and line ranges, literal-search claims, and document hashes were independently re-verified and are accurate. The optional F-2 evidence-index fix was applied correctly. F-3 is appropriately deferred to the semantic phase with the vacuity risk documented; F-4 and F-5 are recorded faithfully. The remaining items are NOTE-level metadata observations with no revision requirement.

This assessment is a determination that the review material is ready for the human Gate A review; it is not a Gate A approval. Approval of Gate A is a human decision. This artifact remains a DRAFT under `candidates/`, not promoted to `accepted/`, and the run's Gate A status remains pending.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/not-b32/architecture/foundation-v2.md`. No Lean code was written, and no `not.b32` bit-complement semantics were extracted during this review. No gates were approved and nothing was promoted to `accepted/`.
