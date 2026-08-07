# Independent Semantic Critique — mov-b32-semantics-v2

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json` (interpretation_id `ptx-9.3-mov-b32-semantics-v2`, status `READY_FOR_CRITIQUE`, 374 lines), the second semantic interpretation for the bounded `mov.b32` unit, regenerated after Human Gate B rejection of semantics-v1.
- This critique is an independent semantic-critic review. It does not approve Gate B and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines), via the restricted specification tools.
- Source bundle consulted: `candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v2.json` (bundle_id `ptx-9.3-mov-b32-source-bundle-v2`, 38 fragments `PTX-9.3-MOV-001..038`; new fragments 033-038 from section 9.7.13 Control Flow Instructions).
- Architecture consulted: `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md` (human-approved at Gate A per `reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json`, decision `approved`, submittedAtUtc `2026-08-07T11:09:53.469Z`).
- Prior reviews consulted: `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v1.md` (findings F-1..F-5) and `candidates/ptx/9.3/units/mov-b32/reviews/architecture-critic-v1.md`.
- Human Gate B decision consulted: `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-rejection-v1.json` (decision `rejected`, submittedAtUtc `2026-08-07T11:45:19.034Z`, directive to source-resolve the guard-false consequence before human assumption approval; claims `PTX-MOV-SEM1-034`/`PTX-MOV-SEM1-038` blocking-if-wrong).
- Run metadata consulted: `runs/ptx-9.3-mov.b32-f910feea/run.json` (unit `mov.b32`, stage SEMANTIC_CRITIQUE attempt 2, revision 12, Gate A approved, Gate B rejected).

## 2. Overall verdict

**SUITABLE for Human Gate B presentation (no substantive revision required).**

The semantic interpretation is faithful to the supplemented bounded source bundle and to the human-approved architecture scope. All 76 semantic claims (`PTX-MOV-SEM2-001..076`) reference only bundle fragment IDs `PTX-9.3-MOV-001..038`; the claim counts (35 SOURCE_FACT, 21 DERIVED_INTERPRETATION, 6 DESIGN_DEPENDENCY, 0 ASSUMPTION, 14 OPEN_QUESTION = 76) are accurate. The v2 supplement's new guard-false evidence (section 9.7.13.2 "Threads with a False guard predicate do nothing.", Semantics "If {!}p then instruction") was independently re-verified verbatim against the official HTML, and the reclassification of the mov.b32 guard-false consequence from ASSUMPTION to DERIVED_INTERPRETATION (PTX-MOV-SEM2-034/038) is sound: the official clause is correctly recorded as SOURCE_FACT (PTX-MOV-SEM2-072), the derivation chain is explicit and consolidated (PTX-MOV-SEM2-076), and the state-level reading ("no state component changes") is honestly identified as the interpretation of "do nothing", not as a quoted source fact. This directly implements the Gate B rejection directive.

Findings are limited to one MINOR classification-hygiene recurrence (interpretive tails embedded in the statements of the NEW SOURCE_FACT claims 070-075, i.e. an incomplete carry-through of v1 F-1), one MINOR confidence-calibration note on the derived guard-false claims (SEM2-034/038 "high" confidence despite an explicit interpretive step), and three NOTE-level observations (bundle-level SHA-256 still null; PDF page references verified by the source curator rather than re-verified here; bounded base scope reconfirmation point for the Gate B reviewer). None of these change the semantic content, and none require revision before Gate B presentation. The artifact is ready to be presented to Human Gate B; Gate B is not approved by this review.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json` — complete candidate read (374/374 lines); all 76 claims, syntax, operands, types, modifiers, preconditions, state reads/writes, guard semantics, behavior, exceptional behavior, determinism, version/target, assumptions (empty), ambiguities (AMB-1..AMB-6), open questions (14), resolved open questions, blocking issues (none), future theorem obligation topics (PRF-1..PRF-7), revision delta, and traceability summary inspected.
- `candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v2.json` — complete read (1077/1077 lines); all 38 fragments (001-038), the predication-evidence search log, all 25 coverage areas, and all 8 evidence gaps (GAP-1..GAP-8) cross-checked against the claims.
- `candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v1.json` — read (858 lines) for delta comparison of carried fragments 001-032.
- `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v1.json` — read (1055 lines) for the revision-delta mapping of SEM1-001..070 to SEM2.
- `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md` — full read; all architecture cross-references used by the semantics (D-0c, D-1, D-3, D-5, D-8, D-11, D-14, D-16, D-25, A-3, A-8, OQ-1..OQ-9, AMB-1..AMB-3, PRF-1..PRF-7) confirmed present.
- `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v1.md` — full read (F-1..F-5).
- `reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json` — read; decision `approved`, `humanConfirmationRecorded: true`.
- `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-rejection-v1.json` — read; decision `rejected`, directive recorded verbatim.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools:
  - anchor `control-flow-instructions-at` (line 21826), lines 21816-21861: Description "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." (21838-21839), Semantics "If {!}p then instruction" (21841), PTX ISA Notes "Introduced in PTX ISA version 1.0." (21843), Target ISA Notes "Supported on all target architectures." (21845), Examples (21848-21851). Matches fragments PTX-9.3-MOV-035/036/037.
  - anchor `control-flow-instructions` (line 21788), lines 21783-21806: section 9.7.13 intro and construct list `{} @ bra call ret exit`. Matches fragment PTX-9.3-MOV-033.
  - anchor `control-flow-instructions-curly-braces` (line 21801), lines 21796-21831: instruction grouping, braces, example `{ add.s32 a,b,c; mov.s32 d,a; }`. Matches fragment PTX-9.3-MOV-034.
  - anchor `control-flow-instructions-bra` (line 21855), lines 21850-21877: bra syntax and Semantics `if (p) { pc = tgt; }` (21874-21876). Matches fragment PTX-9.3-MOV-038.
  - anchor `data-movement-and-conversion-instructions-mov` (line 14999), lines 14995-15077: scalar mov Description, Syntax, Semantics `d = a;` (15039), Notes, PTX ISA Notes, Target ISA Notes, Examples. Matches fragments PTX-9.3-MOV-001..010.
  - anchor `data-movement-and-conversion-instructions-mov-2` (line 15075), lines 15073-15093 and span 15132-15142: vector pack/unpack description, sink `_`, PTX ISA/Target ISA Notes including "Supported on all target architectures." (15139). Matches fragments PTX-9.3-MOV-011..014 and confirms claim PTX-MOV-SEM2-046's reading that the vector-section target note is separate from the scalar base form.
  - anchor `predicated-execution` (line 7537), lines 7531-7567: `.pred` type, guard syntax `@{!}p`, unconditional execution, examples `@p add.s32` (7562). Matches fragments PTX-9.3-MOV-020/021/022.
  - anchor `fundamental-types` (line 3015), lines 3011-3027: fundamental-type definition and Table 8 location. Matches fragments PTX-9.3-MOV-023/024.
  - anchor `register-state-space` (line 2613), lines 2611-2631: register widths (8/16/32/64/128), 1-bit predicates, not fully addressable, spilling/ABI notes. Matches fragment PTX-9.3-MOV-026.
  - literal search `does not execute`: 0 matches.
  - literal search `do nothing`: exactly 1 match, at line 21839 (the section 9.7.13.2 false-guard clause). Confirms the bundle's negative-evidence notes and the uniqueness of the explicit clause.
  - literal search `guard predicate True`: 2 matches (lines 15196, 15334, both in shfl/sync warp-level semantics) — these are unrelated instruction-specific contexts; the 9.7.13.2 clause uses "guard predicate True" inside HTML tags and was verified via the anchor context read above.
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is a semantic interpretation candidate only. No Lean review was performed because none was provided at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | SOURCE_FACT claims PTX-MOV-SEM2-070..075 (statements) | v1 F-1 recurrence: the new SOURCE_FACT claims embed interpretive/derivation tails in their statements (e.g., SEM2-072's "by the general predicability rule it is the applicable evidence for predicated instructions including mov.b32"; SEM2-075's "mov.b32 guard behavior is governed by the general @ predication clause"); the revision-delta claims F-1 "addressed" but only for SEM2-002/049/053/054 |
| F-2 | MINOR | PTX-MOV-SEM2-034/038 (`confidence: high`) | Confidence calibration: the mov.b32 guard-false consequence is a DERIVED claim that explicitly includes an interpretive step ("no state component changes" is the state-level reading of "do nothing"); "high" is defensible but slightly optimistic — recommend "medium" or an explicit note that the confidence applies to the derivation, not to a quoted source fact |
| F-3 | NOTE | `source_bundle_references[0].sha256` (line 41) | Bundle-level SHA-256 remains null with an honest `sha256_note`; carried from v1 F-4; fragment-level hashes and source-document hashes are recorded, so traceability is not broken |
| F-4 | NOTE | fragments PTX-9.3-MOV-033..038 `pdf_page` (399-401) | PDF page references were verified by the source curator in the curation pass; this critique re-verifies against the official HTML (the primary source); PDF pages were not independently re-checked here (no PDF tool in the critic toolset) |
| F-5 | NOTE | `PTX-MOV-SEM2-004/-013`, AMB-2, traceability summary | Bounded base scope covers only register/immediate sources of scalar `mov.b32`; proper subset of the official form, human-confirmed at Gate A; the Gate B reviewer should reconfirm the carried scope |

## 5. Findings detail

### F-1 — MINOR — v1 F-1 recurrence: interpretive tails inside the NEW SOURCE_FACT claims

- **Exact location:** `semantic_claims`:
  - PTX-MOV-SEM2-070: "…The @ construct is listed among the control-flow constructs; section 9.7.13.2 defines the general predication form."
  - PTX-MOV-SEM2-071: "…This establishes the 'instruction or instruction block' notion referenced by the general predication clause of section 9.7.13.2."
  - PTX-MOV-SEM2-072: "…This is the explicit official false-guard no-op clause requested by the Gate B rejection; by the general predicability rule it is the applicable evidence for predicated instructions including mov.b32."
  - PTX-MOV-SEM2-073: "…The target note concerns the general predication form, not the scalar mov.b32 value-copy target set (see PTX-MOV-SEM2-046)."
  - PTX-MOV-SEM2-074: "…These illustrate the general guard syntax that applies to predicated instructions."
  - PTX-MOV-SEM2-075: "…This is bra-specific neighboring control-flow context; it is not asserted to govern mov.b32 directly. mov.b32 guard behavior is governed by the general @ predication clause (PTX-9.3-MOV-035/036; PTX-MOV-SEM2-072/073)."
- **Relevant official evidence:** The source-quoted portions of all six claims are accurate and were verified against the HTML (fragments 033-038 at lines 21788-21876). The issue is classification hygiene, not content.
- **Description:** The revision-delta states that semantic-critic v1 F-1 was addressed by moving interpretive/scope clauses into `interpretation_note` fields on claims 002/049/053/054. That fix is genuine for those four claims (verified: their SOURCE_FACT statements now contain only source-quoted content, with interpretation notes separated). However, the six NEW SOURCE_FACT claims (070-075) embed derivation/scope conclusions directly in their statements — most notably SEM2-072, which asserts in a SOURCE_FACT claim that the clause is "the applicable evidence for predicated instructions including mov.b32" (a derived conclusion, not a quoted source fact), and SEM2-075, which asserts the governing rule for mov.b32 inside a SOURCE_FACT. The correct placement of the mov.b32-applicability conclusion is already provided separately in the DERIVED claims SEM2-034/038 and SEM2-076; the tails in the SOURCE_FACT statements duplicate that conclusion at the wrong classification level.
- **Consequence:** Downstream traceability tooling that treats SOURCE_FACT statements as verbatim source content could pick up derivation conclusions as if they were official text. No semantic content is wrong; the risk is the same classification-purity issue that v1 F-1 identified, and the fix was applied incompletely (old claims fixed, new claims not).
- **Required owner:** Semantic Extractor.
- **Required revision:** In a future revision, move the interpretive/derivation tails out of the SOURCE_FACT statements of claims 070-075 (into `interpretation_note` fields or leave them to the existing DERIVED claims). Not required before Gate B; content is accurate and the same conclusions exist at the correct classification level elsewhere.
- **Human review required:** No.

### F-2 — MINOR — Confidence calibration on the derived guard-false consequence

- **Exact location:** `semantic_claims` PTX-MOV-SEM2-034 and PTX-MOV-SEM2-038 (`"confidence": "high"`), and the parallel text in `state_writes[2]` and `guard_false_consequence`.
- **Relevant official evidence:** Section 9.7.13.2 (verified at HTML lines 21838-21841): "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing."; Semantics "If {!}p then instruction".
- **Description:** The claims correctly distinguish the official clause (SOURCE_FACT, SEM2-072) from its application to mov.b32 (DERIVED, SEM2-034/038). The application involves (1) the general predicability rule (MOV-016), (2) the guard-syntax rule (MOV-021), (3) the general @-form semantics (MOV-035/036), and (4) an interpretive step: "do nothing" is read at the instruction-local state level as "no state component changes". Steps 1-3 are direct source facts; step 4 is an interpretation, explicitly acknowledged in claim 034's own text ("the state-level reading 'no state component changes' is the semantic interpretation of 'do nothing'"). Assigning "high" to a claim containing an acknowledged interpretive step is defensible because the step is natural and the claim text is transparent, but it is slightly optimistic compared with the "medium" used for the similarly-derived determinism claim (SEM2-039).
- **Consequence:** A reader could over-weight the derived consequence as if it were as certain as a quoted source fact. The risk is contained because the claim text itself flags the interpretive step.
- **Required owner:** Semantic Extractor.
- **Required revision:** Either downgrade SEM2-034/038 to `confidence: medium`, or add an explicit confidence note stating that "high" applies to the derivation chain while the state-level reading of "do nothing" is an interpretation subject to Gate B confirmation. Not required before Gate B.
- **Human review required:** Yes (Gate B confirmation of the state-level reading of "do nothing").

### F-3 — NOTE — Bundle-level SHA-256 still null

- **Exact location:** `source_bundle_references[0].sha256` (line 41), with honest `sha256_note`.
- **Relevant official evidence:** The bundle records fragment-level `fragment_sha256` for all 38 fragments and source-document hashes (HTML `e2095c4a…`, PDF `769cc12e…`).
- **Description:** Carried forward from v1 F-4; the semantics does not fabricate a bundle hash. Traceability to the bundle is by path and bundle_id; bundle content was verified at SOURCE_CURATION (run.json history, 12:00:37).
- **Consequence:** Minor traceability soft spot only.
- **Required owner:** Semantic Extractor / Orchestrator (optional).
- **Required revision:** None required.
- **Human review required:** No.

### F-4 — NOTE — PDF page references verified by the source curator, not re-verified here

- **Exact location:** bundle fragments PTX-9.3-MOV-033..038 `pdf_page` fields (399, 399, 400, 400, 400, 401) and the claim line ranges in SEM2-070..075.
- **Relevant official evidence:** The source curator's pass recorded that all PDF page references were verified against the official PDF (pages 399-401) and that the HTML is the primary source. The critic toolset exposes only the whitelisted HTML; this critique re-verified every fragment quote and line range against the HTML, not the PDF pages.
- **Description:** No discrepancy found; the HTML line ranges in claims 070-075 (21788-21800, 21801-21824, 21826-21839, 21840-21845, 21846-21853, 21859-21876) all match the verified anchors.
- **Consequence:** None.
- **Required owner:** None.
- **Required revision:** None.
- **Human review required:** No.

### F-5 — NOTE — Bounded base scope reconfirmation point for Gate B

- **Exact location:** `PTX-MOV-SEM2-004` (DESIGN_DEPENDENCY), `PTX-MOV-SEM2-013` (DERIVED_INTERPRETATION), AMB-2, traceability summary; correspondingly architecture D-0c.
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 15008-15021 (scalar mov syntax incl. `sreg`, `avar`, `avar+imm`, `fname`, `kernel` forms), line 1663 (`mov.b32 r1, %tid.x;` with special-register source).
- **Description:** Carried from v1 F-5. The unit name `mov.b32` is broader than the interpreted base unit (register/immediate sources only). The scope reduction was explicitly human-approved at Gate A; the semantics inherits it correctly and does not re-interpret the out-of-scope source categories. The v2 supplement (control-flow predication evidence) does not change this scope.
- **Consequence:** None if the Gate B reviewer reconfirms the bounded scope.
- **Required owner:** Human Gate B reviewer (scope confirmation); Semantic Extractor for future `sreg`-form units.
- **Required revision:** No artifact change required.
- **Human review required:** Yes (Gate B scope confirmation).

## 6. Gate B rejection handling verification

The Human Gate B rejection (reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-rejection-v1.json) directed: "Do not accept guard-false unchanged-state behavior as a human assumption yet. Search the official PTX ISA 9.3 general predication/control-flow sections for explicit false-guard no-op evidence, add any applicable official evidence to a new source-bundle revision, then regenerate and re-critique the semantics. PTX-MOV-SEM1-034 and PTX-MOV-SEM1-038 are blocking-if-wrong and should be source-resolved before human assumption approval if possible."

This critique verifies the end-to-end resolution:

1. **Search was real and complete.** The bundle records a 9-query search log (`predication_evidence_search`), including negative results for "does not execute" (0), "not executed" (1, unrelated setmaxnreg), "no-op" (0), "predicated off" (0), "guard predicate is false" (0), "if the predicate is false" (0), "predicate is false" (0), and "conditional execution" (4, non-state-effect wording). This critic independently re-ran the key searches: "does not execute" = 0 matches; "do nothing" = exactly 1 match at line 21839, which is the section 9.7.13.2 clause. The search log is accurate and complete for the recorded queries.

2. **The evidence added is genuine and applicable.** Section 9.7.13.2 (anchor `control-flow-instructions-at`, lines 21826-21853) is the official general predication form `@{!}p instruction;`. Its Description states "Threads with a False guard predicate do nothing." and its Semantics is "If {!}p then instruction". This critic verified the text verbatim. Combined with "All PTX instructions may be predicated" (MOV-016) and "All instructions have an optional guard predicate … prefix an instruction with @{!}p" (MOV-021), the clause applies to predicated mov.b32. The applicability chain is explicit and consolidated in DERIVED claim PTX-MOV-SEM2-076.

3. **The reclassification is honest.** The official clause itself is SOURCE_FACT (SEM2-072). The mov.b32 consequence ("instruction does not execute and no state component changes") is DERIVED_INTERPRETATION (SEM2-034/038), with the state-level reading of "do nothing" explicitly identified as the interpretation. The artifact no longer presents guard-false behavior as a human assumption (assumptions: []), which is exactly what the rejection required. The classification choice (DERIVED rather than SOURCE_FACT for the mov.b32 application) is conservative and appropriate: it does not overstate the clause as a mov-specific statement.

4. **PRF-4's previous block is correctly lifted with a caveat.** The future-theorem topic PRF-4 is recorded as UNBLOCKED because the consequence is now evidence-backed; the artifact itself notes it "remains subject to the ordinary Gate B review of this semantics." This is accurate — the unblocking is contingent on the Gate B reviewer accepting the DERIVED reading.

No remaining assumption-level gap exists for the guard-false consequence. The Gate B directive is satisfied.

## 7. Source-verification notes

Specification-tool calls used in this critique: 7 restricted context reads, 1 restricted span read, and 3 restricted literal searches (all verified directly against the official HTML).

Verification results:

- All six new fragments (PTX-9.3-MOV-033..038) verified verbatim against the official HTML: section 9.7.13 intro and construct list (033), section 9.7.13.1 instruction grouping and `mov.s32` example (034), section 9.7.13.2 Description do-nothing clause (035), Semantics/Notes/Target Notes (036), Examples (037), and section 9.7.13.3 bra Semantics `if (p) { pc = tgt; }` (038). All quotes and line ranges match.
- All carried fragments 001-032 were re-checked against the bundle and the load-bearing ones re-verified against the HTML (scalar mov section 9.7.9.3, vector section 9.7.9.4, 9.7.9 intro, 9.7 predicability, 9.1, 9.2, 9.3, 5.2.1, 5.1.1, 5.1.2, 5.4.1, 5.4.6, 4.3, 5.2.2, 7.1). All match.
- Claim counts verified by exhaustive scan: 35 SOURCE_FACT, 21 DERIVED_INTERPRETATION, 6 DESIGN_DEPENDENCY, 0 ASSUMPTION, 14 OPEN_QUESTION = 76 claims; IDs unique and sequential 001..076; traceability_summary counts match.
- Every claim's `evidence_fragment_ids` reference only `PTX-9.3-MOV-001..038`; `fragment_ids_used` lists exactly those 38 IDs. No out-of-bundle references and no add.u32/other-unit evidence.
- All architecture cross-references used by the semantics exist in foundation-v1.md.
- Gate A record verified (decision `approved`); Gate B rejection record verified (decision `rejected`); run history confirms the v2 bundle curation at 12:00:37 and semantics-v2 creation at 12:07:36.
- Honest gap handling verified: determinism remains DERIVED with explicit non-statement note (GAP-2); scalar target set remains OPEN_QUESTION (GAP-7) and the new @-form target note (MOV-036) is correctly NOT treated as resolving it (SEM2-046); error/UB/implementation-defined absence remains OPEN_QUESTION (GAP-3); bit-bucket applicability remains OPEN_QUESTION (GAP-6); immediate range/encoding remains OPEN_QUESTION (GAP-5).
- The v1 findings were addressed as follows: F-1 partially (old claims 002/049/053/054 fixed; new claims 070-075 recur — this critique's F-1); F-2 fully (guarded_form reworded to "(alternatively @!p mov.b32 d, a;)" with an explanatory syntax_note); F-3 fully as recorded disposition (PRF-6 reclassified as VAL-style definitional obligation, final adoption deferred to the theorem-design stage); F-4 carried honestly; F-5 carried as a Gate B confirmation point.

No SOURCE_FACT mislabeling of interpretation as fact in the carried core claims; the guard-false consequence is correctly classified DERIVED (not SOURCE_FACT, not ASSUMPTION); no phantom fragment IDs; no invented error/UB behavior; no use of `sorry`/`admit`/axioms/unsafe (no Lean exists); no vacuous theorem statements (no theorems exist). The four-label taxonomy is used consistently except for the F-1 tails in the new SOURCE_FACT claims 070-075.

## 8. Required revisions (consolidated)

No substantive revisions are required before Gate B. Optional refinements:

1. Move interpretive/derivation tails out of the SOURCE_FACT statements of claims 070-075 (F-1) — classification hygiene.
2. Downgrade or annotate the confidence of SEM2-034/038 (F-2) — confidence calibration.
3. Optionally record the bundle SHA-256 when a hash tool is available (F-3).
4. Gate B reviewer to reconfirm the bounded base scope (register/immediate only) (F-5).

## 9. Residual open questions

- Will the Gate B reviewer accept the DERIVED_INTERPRETATION classification of the mov.b32 guard-false consequence, including the state-level reading of "do nothing" as "no state component changes" (SEM2-034/038, PRF-4)? This is the direct subject of the rejection and is now evidence-backed; the reviewer's confirmation is the intended gate.
- Will the Gate B reviewer approve determinism as a DERIVED interpretation (SEM2-039, GAP-2)?
- Is PRF-6's VAL-style reclassification confirmed at the theorem-design stage (Gate C / theorem-strength gate)?
- Does the Gate B reviewer reconfirm that the bounded base unit (register/immediate sources only) is the intended `mov.b32` unit (F-5)?

## 10. Gate B readiness assessment

Ready for presentation to Human Gate B. The semantic interpretation is source-faithful, traceable (76 claims, all to bundle fragment IDs 001-038), honest about all evidence gaps (GAP-1 source-resolved by the v2 supplement and reclassified as DERIVED; GAP-2/GAP-3/GAP-5/GAP-6/GAP-7 handled as DERIVED/OPEN_QUESTION, never as invented source facts), and consistent with the human-approved architecture scope. The Gate B rejection directive was fully implemented: explicit false-guard no-op evidence was found in the official control-flow section 9.7.13.2, added to the source bundle, and the semantics regenerated so that the guard-false consequence is no longer a human assumption. The MINOR findings (F-1 classification tails in new claims; F-2 confidence calibration) are wording/classification refinements; F-3/F-4/F-5 are notes. The artifact itself correctly records `gate_b_status: NOT READY`, the proper state for a candidate awaiting human approval. This assessment is not a Gate B approval; approval is a human decision.

## 11. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json`. No semantic claims were rewritten, no source evidence was fabricated, no Lean code was written, and no `mov.b32` copy or guard semantics were altered during this review. No gates were approved and nothing was promoted to `accepted/`.

SPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"WAITING_GATE_B","summary":"Created candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md: semantics-v2 independently critiqued against source-bundle-v2 and official PTX ISA 9.3 HTML; all 76 claims (35 SOURCE_FACT/21 DERIVED/6 DESIGN/0 ASSUMPTION/14 OPEN) re-verified, including verbatim re-verification of new fragments 033-038 (section 9.7.13.2 do-nothing clause); Gate B rejection directive confirmed implemented (guard-false reclassified ASSUMPTION->DERIVED with explicit derivation chain); 2 MINOR (F-1 classification tails in new SOURCE_FACT claims 070-075; F-2 confidence calibration on SEM2-034/038) and 3 NOTE findings, no blockers; suitable for Human Gate B presentation (gate not approved)."}