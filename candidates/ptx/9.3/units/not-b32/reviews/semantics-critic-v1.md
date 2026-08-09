# Independent Semantic Critique — not-b32-semantics-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/not-b32/semantics/semantics-v1.json` (interpretation_id `ptx-9.3-not-b32-semantics-v1`, schema_version 2, status `READY_FOR_CRITIQUE`, 337 lines), the first semantic interpretation for the bounded `not.b32` unit.
- This critique is an independent semantic-critic review. It does not approve Gate B and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines), via the restricted specification tools.
- Source bundle consulted: `candidates/ptx/9.3/units/not-b32/source-bundles/source-bundle-v1.json` (bundle_id `ptx-9.3-not-b32-source-bundle-v1`, 33 fragments `PTX-9.3-NOT-001..033`, status `DRAFT_SOURCE_BUNDLE_NOT_SEMANTICALLY_INTERPRETED`).
- Architecture consulted: `candidates/ptx/9.3/units/not-b32/architecture/foundation-v2.md` (SHA-256 `84726b1b98120a036e1a1dc32934e71ac1af3eb08cfde4c58c760e4b1ad55db7`), approved at Human Gate A per `reviews/ptx-not-b32/gate-a/ptx-not-b32-a-approval-v1.json` (decision `approved`, `humanConfirmationRecorded: true`, submittedAtUtc `2026-08-09T12:23:43.550Z`).
- Human Gate B lesson consulted: `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-rejection-v1.json` (decision `rejected`, directive to source-resolve the guard-false consequence rather than present it as a human assumption) and its implementation precedent in `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md`.
- Run metadata consulted: `runs/ptx-9.3-not.b32-5e83de43/run.json` (unit `not.b32`, stage SEMANTIC_CRITIQUE attempt 1, revision 8, Gate A approved, Gate B pending).

## 2. Overall verdict

**SUITABLE for Human Gate B presentation (no substantive revision required; Gate B not approved).**

The semantic interpretation is faithful to the bounded source bundle and to the human-approved architecture scope. All 73 semantic claims (`PTX-NOT-SEM1-001..073`) reference only bundle fragment IDs `PTX-9.3-NOT-001..033`; the claim counts (31 SOURCE_FACT, 23 DERIVED_INTERPRETATION, 6 DESIGN_DEPENDENCY, 0 ASSUMPTION, 13 OPEN_QUESTION = 73) are accurate and were verified by exhaustive scan.

Key correctness checks, all independently confirmed:

- **Core semantics.** `not.b32 d, a;` with `d = ~a;` over the 32-bit untyped bit-value domain is correctly derived from the verbatim Semantics line (HTML line 14375), the description "Bitwise negation; one's complement." (line 14363) / "Invert the bits in `a`." (line 14372), and the `.b32` "Bits (untyped)" type (Table 8, lines 3053-3054; register width 32-bit at lines 2622-2624). Claims PTX-NOT-SEM1-004/007/008/013/032/033 are accurate.
- **Operand order and roles.** `d` destination, `a` source, matching section 9.2 ("the `d` operand is the destination operand, while `a`, `b`, and `c` are source operands", lines 7526-7527) and the official example `not.b32  mask,mask;` (line 14387). Claims PTX-NOT-SEM1-006/009/061 are accurate.
- **Guard predication.** The guard-false consequence ("instruction does not execute and no state component changes") is correctly classified DERIVED_INTERPRETATION (PTX-NOT-SEM1-035, confidence medium), grounded in the verbatim official clause of section 9.7.13.2: "Threads with a False guard predicate do nothing." (lines 21838-21839) with Semantics "If {!}p then instruction" (line 21841), combined with the general predicability rule (lines 8722-8723) and guard-syntax rule (lines 7547-7550). The official clause itself is SOURCE_FACT (PTX-NOT-SEM1-028); the state-level reading is explicitly identified as an interpretation subject to Gate B confirmation. Zero ASSUMPTION-classified claims exist, implementing the mov.b32 Gate B lesson.
- **State reads/writes.** Reads of source `a` and guard predicate `p`; single destination write; no invented memory/special-register/carry/status writes (claims 036-039). The locality claim is derived and consistent with the two-operand syntax.
- **No invented exceptional behavior.** Error/UB/implementation-defined absence is recorded as OPEN_QUESTION (052/053/054), never as a positive source fact (bundle GAP-4, coverage area 15 NOT_FOUND).
- **Version/target.** Base `not.b32`: introduced in PTX ISA 1.0 and supported on all target architectures, directly from the not-family notes in the not section itself (lines 14382/14384; fragments NOT-007/008). No target-set gap exists for this unit (contrast with the scalar mov.b32 case), and the semantics correctly records this.
- **Honest gap handling.** Immediate source (OQ-1/GAP-1), bit-bucket destination (OQ-2/GAP-2), determinism non-statement (GAP-3), operand-typing formulation (OQ-7/GAP-5), and negative literal-search results (GAP-8) are OPEN_QUESTION or honest DERIVED items with explicit non-statement notes, never fabricated source facts.

Findings are limited to one MINOR classification-hygiene item (an interpretive tail embedded in the statement of SOURCE_FACT claim PTX-NOT-SEM1-015, the same pattern the mov.b32 critique flagged as F-1) and three NOTE-level observations. None changes the semantic content and none requires revision before Gate B presentation. The artifact is ready to be presented to Human Gate B; Gate B is not approved by this review.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/not-b32/semantics/semantics-v1.json` — complete candidate read (337/337 lines); all 73 claims, syntax, operands, types, modifiers, preconditions, state reads/writes, guard semantics, behavior, exceptional/undefined/implementation-defined behavior, determinism, version/target, ambiguities (AMB-1..AMB-5), open questions (13), resolved open questions (OQ-3), blocking issues (none), future theorem obligation topics (PRF-1..PRF-7), and traceability summary inspected.
- `candidates/ptx/9.3/units/not-b32/source-bundles/source-bundle-v1.json` — complete read (956/956 lines); all 33 fragments (001-033), the predication-evidence search log, all 22 coverage areas, and all 8 evidence gaps (GAP-1..GAP-8) cross-checked against the claims.
- `candidates/ptx/9.3/units/not-b32/architecture/foundation-v2.md` — full read (298 lines); all architecture cross-references used by the semantics (D-0c, D-1, D-3, D-5, D-8, D-11, D-14, D-16, D-25, A-3, A-8, OQ-1..OQ-8, PRF-1..PRF-7) confirmed present.
- `candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md` — read in full as the process precedent for the Gate B lesson (F-1 interpretive-tail pattern, F-2 confidence calibration, F-3/F-4/F-5 notes).
- `reviews/ptx-not-b32/gate-a/ptx-not-b32-a-approval-v1.json` — verified (decision `approved`, `humanConfirmationRecorded: true`).
- `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-rejection-v1.json` — verified (decision `rejected`, directive recorded).
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools (see Section 6).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` — read in full (39 lines); HTML SHA-256 `e2095c4a...`, PDF SHA-256 `769cc12e...` match the bundle records.
- `documents/sources/nvidia/ptx/9.3/SHA256SUMS` — read in full (2 lines; HTML and PDF hashes match the bundle records).
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is a semantic interpretation candidate only. No Lean review was performed because none was provided at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | SOURCE_FACT claim PTX-NOT-SEM1-015 (statement) | Interpretive tail "(32-bit width is therefore possible for .b32 registers)" embedded inside a SOURCE_FACT statement, against the artifact's own stated policy ("interpretive tails are kept out of SOURCE_FACT statements"); content is accurate and the tail is acknowledged in the interpretation_note |
| F-2 | NOTE | `source_bundle_references[0].sha256` (line 41) | Bundle-level SHA-256 remains null with an honest `sha256_note`; fragment-level hashes and source-document hashes are recorded, so traceability is not broken |
| F-3 | NOTE | bundle fragments `pdf_page` fields; claim line ranges | PDF page references were verified by the source curator during curation; this critique re-verifies against the official HTML (the primary source) — PDF pages were not independently re-checked here (no PDF tool in the critic toolset) |
| F-4 | NOTE | `PTX-NOT-SEM1-003`, AMB-1, traceability summary | Bounded base scope covers only the scalar 32-bit `.b32` form of `not` (`.pred`/`.b16`/`.b64` deferred), human-confirmed at Gate A (D-0c); the Gate B reviewer should reconfirm the carried scope and the DERIVED state-level reading of "do nothing" |

## 5. Findings detail

### F-1 — MINOR — Interpretive tail inside SOURCE_FACT claim PTX-NOT-SEM1-015

- **Exact location:** `semantic_claims` PTX-NOT-SEM1-015 (line 195 of the artifact): statement "Registers (.reg state space) are fast storage locations; aside from 1-bit predicate registers, scalar registers have a width of 8-, 16-, 32-, 64-, or 128-bits (32-bit width is therefore possible for .b32 registers); registers are not fully addressable."
- **Relevant official evidence:** Section 5.1.1 Register State Space, lines 2617-2627 (verified): register widths and 1-bit predicate registers at lines 2622-2624; "not fully addressable" at lines 2626-2627. The quoted content is accurate.
- **Description:** The claim is classified SOURCE_FACT, but its statement embeds the interpretive tail "(32-bit width is therefore possible for .b32 registers)", which is a derived reading of the listed widths rather than source text. This is the same classification-hygiene pattern the mov.b32 semantic critique flagged as F-1 (interpretive/derivation tails inside SOURCE_FACT statements). The artifact's own claim PTX-NOT-SEM1-002 records the policy "interpretive tails are kept out of SOURCE_FACT statements" (claim 002's interpretation_note, applying the mov.b32 lesson), so claim 015 is inconsistent with the artifact's stated policy. The tail is harmless and correctly acknowledged in the interpretation_note; the issue is classification purity only.
- **Consequence:** Downstream traceability tooling that treats SOURCE_FACT statements as verbatim source content could pick up the parenthetical as if it were official text. No semantic content is wrong.
- **Required owner:** Semantic Extractor (future revision; not required before Gate B).
- **Required revision:** In a future revision, move the parenthetical out of the SOURCE_FACT statement (into the interpretation_note, or into a DERIVED claim). Not required before Gate B; content is accurate.
- **Human review required:** No.

### F-2 — NOTE — Bundle-level SHA-256 still null

- **Exact location:** `source_bundle_references[0].sha256` (line 41), with honest `sha256_note` stating no value was fabricated.
- **Relevant official evidence:** The bundle records fragment-level `fragment_sha256` for all 33 fragments (helper files exist under `source-bundles/.hash-material/PTX-9.3-NOT-001..033.json`) and source-document hashes (HTML `e2095c4a...`, PDF `769cc12e...`), which match the source manifest and SHA256SUMS.
- **Description:** The semantics does not fabricate a bundle hash. Traceability to the bundle is by path and bundle_id; bundle content was verified at SOURCE_CURATION (run.json history, 12:35:07).
- **Consequence:** Minor traceability soft spot only.
- **Required owner:** Semantic Extractor / Orchestrator (optional).
- **Required revision:** None required.
- **Human review required:** No.

### F-3 — NOTE — PDF page references verified by the source curator, not re-verified here

- **Exact location:** bundle fragments `pdf_page` fields (e.g., 257/258 for the not section, 400 for section 9.7.13.2) and the PDF page references inside claims (e.g., PTX-NOT-SEM1-001 "PDF page 257", PTX-NOT-SEM1-028 "PDF page 400").
- **Relevant official evidence:** The source curator's pass recorded that all PDF page references were verified against the official PDF (pages 254-258, 399-400, plus targeted searches) and that the HTML is the primary source. The critic toolset exposes only the whitelisted HTML; this critique re-verified every fragment quote and HTML line range (all match), not the PDF pages.
- **Description:** No discrepancy found; HTML line ranges in claims (14358-14361, 14362-14363, 14365-14370, 14371-14372, 14373-14377, 14378-14380, 14381-14382, 14383-14384, 14385-14390, 21826-21839, 21840-21845, 21846-21853) all match the verified anchors.
- **Consequence:** None.
- **Required owner:** None.
- **Required revision:** None.
- **Human review required:** No.

### F-4 — NOTE — Bounded base scope and DERIVED guard-false reading to be reconfirmed at Gate B

- **Exact location:** `PTX-NOT-SEM1-003` (DESIGN_DEPENDENCY), `PTX-NOT-SEM1-005` (DERIVED), AMB-1, traceability summary; correspondingly architecture D-0c / OQ-4.
- **Relevant official evidence:** Section 9.7.8.4 (verified): `not.type d, a;` with `.type = { .pred, .b16, .b32, .b64 };` (lines 14366-14368); examples `not.b32 mask,mask;` and `not.pred p,q;` (lines 14387-14388).
- **Description:** The unit name `not.b32` is narrower than the full `not` type set. The scope reduction (scalar `.b32` only; `.pred`/`.b16`/`.b64` deferred to future units) was explicitly human-approved at Gate A (D-0c) and the semantics inherits it correctly without re-interpreting the out-of-scope forms. Similarly, the state-level reading "no state component changes" of the official "do nothing" clause is a DERIVED interpretation (PTX-NOT-SEM1-035, confidence medium) that the Gate B reviewer should explicitly confirm.
- **Consequence:** None if the Gate B reviewer reconfirms the bounded scope and the DERIVED guard-false reading.
- **Required owner:** Human Gate B reviewer (scope and interpretation confirmation); Semantic Extractor for future `.pred`/`.b16`/`.b64` units.
- **Required revision:** No artifact change required.
- **Human review required:** Yes (Gate B scope and interpretation confirmation).

## 6. Source-verification notes

Specification-tool calls used in this critique: 15 restricted context reads, 2 restricted span reads, and 1 literal-search verification set (all against the official HTML via the restricted spec tools), plus candidate read/grep checks on the artifacts.

All load-bearing source facts were re-verified and remain accurate against the official HTML:

- **not section 9.7.8.4** (anchor `logic-and-shift-instructions-not`, line 14358; section 14358-14391): Description "Bitwise negation; one's complement." (14363); Syntax `not.type d, a;` / `.type = { .pred, .b16, .b32, .b64 };` (14366-14368); Description "Invert the bits in `a`." (14372); Semantics `d = ~a;` (14375); Notes "The size of the operands must match, but not necessarily the type." / "Allowed types include predicates." (14379-14380); PTX ISA Notes "Introduced in PTX ISA version 1.0." (14382); Target ISA Notes "Supported on all target architectures." (14384); Examples `not.b32  mask,mask;` and `not.pred  p,q;` (14387-14388). Confirmed. All match fragments NOT-001..009.
- **Family intro 9.7.8** (anchor `logic-and-shift-instructions`, line 14236): untyped bit-wise operations on operands of the same size; `and`, `or`, `xor`, `not` also operate on predicates; instruction list includes `not` (14240-14255). Confirmed (NOT-010).
- **Sibling immediates** (anchors `logic-and-shift-instructions-or` line 14290; `logic-and-shift-instructions-xor` line 14324): `or.b32  mask mask,0x00010001` at 14319 (both printed anomalies — missing comma between the `mask` tokens and missing terminating semicolon — faithfully recorded); `xor.b16  d,x,0x0001;` at 14354. Confirmed (NOT-011/012).
- **Predication applicability** (anchor `instructions`, line 8718): "All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax." (8722-8723). Confirmed (NOT-013).
- **Section 9.2 PTX Instructions** (anchor `ptx-instructions`, line 7513): 0-4 operands plus optional guard; `@p opcode d, a;` form; `d` destination / `a, b, c` sources (7517-7527); bit bucket `_` (7534-7535). Confirmed (NOT-015/016).
- **Section 9.3 Predicated Execution** (anchor `predicated-execution`, line 7537): predicate registers virtual with `.pred` type (7541-7542); guard syntax `@{!}p` and unconditional execution without guard (7547-7550); examples `@p add.s32 j, j, 1;` (7562) and `@!p bra L1;` (7570). Confirmed (NOT-017/018/019).
- **Section 9.7.13 / 9.7.13.1 / 9.7.13.2** (anchors `control-flow-instructions` line 21788, `control-flow-instructions-curly-braces` line 21801, `control-flow-instructions-at` line 21826): construct list `{} @ bra call ret exit` (21794-21799); `{}` instruction grouping (21809-21815); `@` predication with Description "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." (21838-21839), Semantics "If {!}p then instruction" (21841), PTX ISA/Target ISA Notes (21843/21845), Examples (21848-21851). Confirmed (NOT-029..033).
- **Section 5.2.1 Fundamental Types** (anchor `fundamental-types`, line 3015): fundamental type = basic type + size; register variables always of a fundamental type (3019-3022); Table 8 lists `.b32` under "Bits (untyped)" (3053-3054); compatibility rules "The bit-size type is compatible with any fundamental type having the same size." (3062-3066). Confirmed (NOT-020/021/022).
- **Section 5.1.1 Register State Space** (anchor `register-state-space`, line 2613): registers fast storage (2617); widths 8/16/32/64/128, predicate 1-bit (2622-2624); not fully addressable (2626-2627). Confirmed (NOT-023).
- **Section 5.1.2 Special Register State Space** (anchor `special-register-state-space`, line 2633): `.sreg` predefined, platform-specific (2637-2639). Confirmed (NOT-024).
- **Section 5.4.1 Variable Declarations** (anchor `variable-declarations`, line 3747): declaration names state space/type/size/name/optional array/initializer/fixed address; predicate variables only in register state space (3751-3755). Confirmed (NOT-025).
- **Section 5.4.6 Parameterized Variable Names** (anchor `parameterized-variable-names`, line 3933): `.reg .b32 %r<100>;` declares `%r0`..`%r99`; shorthand with any fundamental type and any state space (3940-3948). Confirmed (NOT-026).
- **Section 5.2.2 Restricted Use of Sub-Word Sizes** (anchor `restricted-use-of-sub-word-sizes`, line 3070): `.u8`, `.s8`, `.b8` restricted to ld/st/add/sub/min/max/neg/cvt (3074-3075); `.b32` not in the list. Confirmed (NOT-027).
- **Section 7.1 predication exception** (anchor `function-declarations-and-definitions`, line 6139; span 6257-6262): "st.param and ld.param instructions used for argument passing cannot be predicated." (6260-6261). Confirmed (NOT-028).
- **Section 9.1 Format and Semantics** (anchor `format-and-semantics-of-instruction-descriptions`, line 7505): instruction descriptions include name, format, semantics, examples (7509-7511). Confirmed (NOT-014).
- **cnot example** (line 14420): `cnot.b32 d,a;` — a different instruction than `not`; confirms claim PTX-NOT-SEM1-073's reading that the second `not.b32` literal match is the cnot example.
- **Document hashes:** HTML SHA-256 `e2095c4a...` (47,743 lines), PDF SHA-256 `769cc12e...` — match source-manifest.json and SHA256SUMS. Confirmed.
- **Literal searches (bundle log):** `@p not` (0), `not.b64` (0), `not.b16` (0), `not.b32 %` (0), `not.b32` (2: lines 14387 and 14420), `not.pred` (1: line 14388) — consistent with the fragment evidence; GAP-8 handling (OPEN_QUESTION, negative results support no claims) is correct.

Claim-level verification:

- Claim IDs are sequential 001..073 with no gaps or duplicates; `traceability_summary.claim_counts` (31/23/6/0/13 = 73) matches an exhaustive scan.
- Every claim's `evidence_fragment_ids` reference only `PTX-9.3-NOT-001..033`; `fragment_ids_used` lists exactly those 33 IDs; no out-of-bundle references and no add.u32/mov.b32 semantic evidence imported (the mov.b32 Gate B rejection is used only as a process lesson, per the evidence_interface_note).
- All architecture cross-references used by the semantics exist in foundation-v2.md (D-0c, D-1, D-3, D-5, D-8, D-11, D-14, D-16, D-25, OQ-1..OQ-8, PRF-1..PRF-7).
- Honest gap handling verified: determinism remains DERIVED with explicit non-statement note (GAP-3); immediate source remains OPEN_QUESTION (GAP-1) and sibling immediates are NOT used to infer not's operand forms (do_not_infer honored, claim 010/066); bit-bucket applicability remains OPEN_QUESTION (GAP-2); error/UB/implementation-defined absence remains OPEN_QUESTION (GAP-4); operand-typing formulation remains OPEN_QUESTION (GAP-5); negative literal-search results remain OPEN_QUESTION (GAP-8).
- Gate A record verified (decision `approved`); Gate B lesson directive verified (decision `rejected`, directive recorded); run history confirms source-bundle-v1 creation at 12:35:07 and semantics-v1 creation at 12:43:32.

No SOURCE_FACT mislabeling of interpretation as fact in the load-bearing claims; the guard-false consequence is correctly classified DERIVED (not SOURCE_FACT, not ASSUMPTION); no phantom fragment IDs; no invented error/UB behavior; no use of `sorry`/`admit`/axioms/`unsafe` (no Lean exists); no vacuous theorem statements (no theorems exist). The four-label taxonomy is used consistently except for the F-1 interpretive tail in claim 015.

## 7. Required revisions (consolidated)

No substantive revisions are required before Gate B. Optional refinements:

1. Move the interpretive tail out of the SOURCE_FACT statement of claim PTX-NOT-SEM1-015 (F-1) — classification hygiene; align with the policy stated in claim 002's interpretation_note.
2. Optionally record the bundle SHA-256 when a hash tool is available (F-2).
3. Gate B reviewer to reconfirm the bounded base scope (scalar `.b32` only) and the DERIVED state-level reading of "do nothing" (F-4).

## 8. Residual open questions

- Will the Gate B reviewer accept the DERIVED_INTERPRETATION classification of the `not.b32` guard-false consequence, including the state-level reading of "do nothing" as "no state component changes" (PTX-NOT-SEM1-035, PRF-4)? This is now evidence-backed by section 9.7.13.2; the reviewer's confirmation is the intended gate.
- Will the Gate B reviewer approve determinism as a DERIVED interpretation (PTX-NOT-SEM1-047, GAP-3) and the derived no-other-write locality reading (PTX-NOT-SEM1-039)?
- Is PRF-6's disposition (possible reclassification as a VAL-style definitional obligation) confirmed at the theorem-design stage (Gate C / theorem-strength gate)?
- Does the Gate B reviewer reconfirm that the bounded base unit (scalar `.b32` form only) is the intended `not.b32` unit (F-4)?

## 9. Gate B readiness assessment

Ready for presentation to Human Gate B. The semantic interpretation is source-faithful, traceable (73 claims, all to bundle fragment IDs 001-033), honest about all evidence gaps (GAP-1/GAP-2/GAP-4/GAP-5/GAP-8 handled as OPEN_QUESTION; GAP-3 determinism handled as an explicitly non-stated DERIVED item; never as invented source facts), and consistent with the human-approved architecture scope (foundation-v2, Gate A approved). The mov.b32 Gate B lesson is fully implemented: explicit false-guard no-op evidence from section 9.7.13.2 is part of the bundle, the guard-false consequence is classified DERIVED (not ASSUMPTION), and zero ASSUMPTION-classified claims remain. The core `not.b32` semantics (`d = ~a;` over the 32-bit untyped bit-value domain), operand order/roles, predication behavior, version (PTX ISA 1.0), and target set (all architectures) are all directly evidenced and correctly interpreted. The single MINOR finding (F-1 classification tail in claim 015) is a wording/classification refinement; F-2/F-3/F-4 are notes. The artifact itself correctly records `gate_b_status: NOT READY`, the proper state for a candidate awaiting human approval. This assessment is not a Gate B approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/not-b32/semantics/semantics-v1.json`. No semantic claims were rewritten, no source evidence was fabricated, no Lean code was written, and no `not.b32` complement or guard semantics were altered during this review. No gates were approved and nothing was promoted to `accepted/`.
