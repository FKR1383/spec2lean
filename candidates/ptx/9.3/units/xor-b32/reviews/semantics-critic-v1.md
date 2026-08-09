# Independent Semantic Critique — xor-b32-semantics-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/xor-b32/semantics/semantics-v1.json` (interpretation_id `ptx-9.3-xor-b32-semantics-v1`, schema_version 2, status `READY_FOR_CRITIQUE`, 338 lines), the first semantic interpretation for the bounded `xor.b32` unit.
- This critique is an independent semantic-critic review. It does not approve Gate B and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines), via the restricted specification tools.
- Source bundle consulted: `candidates/ptx/9.3/units/xor-b32/source-bundles/source-bundle-v1.json` (bundle_id `ptx-9.3-xor-b32-source-bundle-v1`, 33 fragments `PTX-9.3-XOR-001..033`, status `DRAFT_SOURCE_BUNDLE_NOT_SEMANTICALLY_INTERPRETED`).
- Architecture consulted: `candidates/ptx/9.3/units/xor-b32/architecture/foundation-v1.md` (SHA-256 `1ff5041f7ea24f013dafe91107855bf6ec066f96b370aa94067086afa17ebf25` as recorded in the spec-architect execution record in `runs/ptx-9.3-xor.b32-23b2e519/run.json`), approved at Human Gate A per `reviews/ptx-xor-b32/gate-a/ptx-xor-b32-a-approval-v1.json` (decision `approved`, `humanConfirmationRecorded: true`, submittedAtUtc `2026-08-09T16:08:08.613Z`).
- Human Gate B lesson consulted: `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-rejection-v1.json` (decision `rejected`, directive to source-resolve the guard-false consequence rather than present it as a human assumption).
- Run metadata consulted: `runs/ptx-9.3-xor.b32-23b2e519/run.json` (unit `xor.b32`, stage SEMANTIC_CRITIQUE attempt 1, revision 9, Gate A approved, Gate B pending).

## 2. Overall verdict

**SUITABLE for Human Gate B presentation (no substantive revision required; Gate B not approved).**

The semantic interpretation is faithful to the bounded source bundle and to the human-approved architecture scope. All 73 semantic claims (`PTX-XOR-SEM1-001..073`) reference only bundle fragment IDs `PTX-9.3-XOR-001..033`; the claim counts (31 SOURCE_FACT, 23 DERIVED_INTERPRETATION, 6 DESIGN_DEPENDENCY, 0 ASSUMPTION, 13 OPEN_QUESTION = 73) are accurate and were verified by exhaustive scan.

Key correctness checks, all independently confirmed:

- **Core semantics.** `xor.b32 d, a, b;` with `d = a ^ b;` over the 32-bit untyped bit-value domain is correctly derived from the verbatim Semantics line (HTML line 14341), the description "Bitwise exclusive-OR (inequality)." (line 14329) / "Compute the bit-wise exclusive-or operation for the bits in `a` and `b`." (line 14338), and the `.b32` "Bits (untyped)" type (Table 8, lines 3053-3054; register width 32-bit at lines 2622-2624). Claims PTX-XOR-SEM1-004/007/008/013/032/033 are accurate.
- **Operand order and roles.** `d` destination, `a`/`b` sources, matching the syntax `xor.type d, a, b;` (lines 14332-14334), section 9.2 ("the `d` operand is the destination operand, while `a`, `b`, and `c` are source operands", lines 7526-7527), and the official example `xor.b32  d,q,r;` (line 14353). Claims PTX-XOR-SEM1-005/006/009/061 are accurate.
- **Bit width / type.** `.b32` is the "Bits (untyped)" fundamental type of 32-bit width; the family is "fundamentally untyped" (section 9.7.8 intro, lines 14240-14243). No signed/unsigned confusion exists: the value domain is untyped bits, and the operand-typing rule is size-based, correctly left partly open at OQ-7/GAP-5 (claim 071).
- **No modifiers.** The scalar syntax has no modifier position; the bounded base form correctly has no modifiers (claim 020). No modifier behavior is invented.
- **Guard predication.** The guard-false consequence ("instruction does not execute and no state component changes") is correctly classified DERIVED_INTERPRETATION (PTX-XOR-SEM1-035, confidence medium), grounded in the verbatim official clause of section 9.7.13.2: "Threads with a False guard predicate do nothing." (lines 21838-21839) with Semantics "If {!}p then instruction" (line 21841), combined with the general predicability rule (lines 8722-8723) and guard-syntax rule (lines 7547-7550). The official clause itself is SOURCE_FACT (PTX-XOR-SEM1-028); the state-level reading is explicitly identified as an interpretation subject to Gate B confirmation. `@!p` execution-when-`p`-false is stated without the erroneous "negated guard true means no-op" phrasing (guard_expression_evaluation, claims 022/031/034/035). Zero ASSUMPTION-classified claims exist, implementing the mov.b32 Gate B lesson.
- **State reads/writes.** Reads of sources `a`/`b` and guard predicate `p`; single destination write; no invented memory/special-register/carry/status writes (claims 036-039). The locality claim is derived and consistent with the three-operand syntax.
- **No invented exceptional behavior.** Error/UB/implementation-defined absence is recorded as OPEN_QUESTION (052/053/054), never as a positive source fact (bundle GAP-4, coverage area 15 NOT_FOUND).
- **Version/target.** Base `xor.b32`: introduced in PTX ISA 1.0 and supported on all target architectures, directly from the xor-family notes in the xor section itself (lines 14348/14350; fragments XOR-007/008). No target-set gap exists for this unit (contrast with the scalar mov.b32 case), and the semantics correctly records this.
- **Honest gap handling.** Immediate source (OQ-1/GAP-1), bit-bucket destination (OQ-2/GAP-2), determinism non-statement (GAP-3), operand-typing formulation (OQ-7/GAP-5), and negative literal-search results (GAP-8) are OPEN_QUESTION or honest DERIVED items with explicit non-statement notes, never fabricated source facts. Sibling `and`/`or` `.b32` immediates are recorded but not inferred (`do_not_infer` honored, claims 010/066).

Findings are limited to three MINOR classification/traceability/wording items (F-1, F-2, F-3) and three NOTE-level observations (F-4, F-5, F-6). None changes the semantic content and none requires revision before Gate B presentation. The artifact is ready to be presented to Human Gate B; Gate B is not approved by this review.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/xor-b32/semantics/semantics-v1.json` — complete candidate read (338/338 lines); all 73 claims, syntax, operands, types, modifiers, preconditions, state reads/writes, guard semantics, behavior, exceptional/undefined/implementation-defined behavior, determinism, version/target, ambiguities (AMB-1..AMB-5), open questions (13), resolved open questions (OQ-3), blocking issues (none), future theorem obligation topics (PRF-1..PRF-7), and traceability summary inspected.
- `candidates/ptx/9.3/units/xor-b32/source-bundles/source-bundle-v1.json` — complete read (958/958 lines); all 33 fragments (001-033), the predication-evidence search log, all 22 coverage areas, and all 8 evidence gaps (GAP-1..GAP-8) cross-checked against the claims.
- `candidates/ptx/9.3/units/xor-b32/architecture/foundation-v1.md` — full read (273 lines); all architecture cross-references used by the semantics (D-0c, D-1, D-3, D-5, D-8, D-11, D-14, D-16, D-25, A-3, A-8, OQ-1..OQ-8, PRF-1..PRF-7) confirmed present.
- `reviews/ptx-xor-b32/gate-a/ptx-xor-b32-a-approval-v1.json` — verified (decision `approved`, `humanConfirmationRecorded: true`).
- `reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-rejection-v1.json` — verified (decision `rejected`, directive recorded).
- `candidates/ptx/9.3/units/not-b32/reviews/semantics-critic-v1.md` — read in full as the same-family process precedent for critique structure and severity calibration.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools (see Section 6).
- `documents/sources/nvidia/ptx/9.3/source-manifest.json` and `documents/sources/nvidia/ptx/9.3/SHA256SUMS` — hashes cross-checked against the bundle records (HTML `e2095c4a...`, PDF `769cc12e...`).
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is a semantic interpretation candidate only. No Lean review was performed because none was provided at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | SOURCE_FACT claim PTX-XOR-SEM1-015 (statement) | Interpretive tail "(32-bit width is therefore possible for .b32 registers)" embedded inside a SOURCE_FACT statement, against the artifact's own stated policy ("interpretive tails are kept out of SOURCE_FACT statements"); content is accurate and the tail is acknowledged in the interpretation_note |
| F-2 | MINOR | DERIVED claim PTX-XOR-SEM1-038 (statement) | Phrasing "The source states no other register write for the bounded base xor.b32 form" could be misread as a positive source assertion; the source does not explicitly state that negative — locality is derived from the three-operand syntax. Claim 039 states the same content with the correct grounding |
| F-3 | MINOR | OPEN_QUESTION claim PTX-XOR-SEM1-073 (evidence_fragment_ids) | Negative literal-search results are reported with only fragment PTX-9.3-XOR-009 as evidence, but the search log lives in the bundle-level `predication_evidence_search` field (no fragment ID); claim text is accurate and was independently re-verified |
| F-4 | NOTE | `source_bundle_references[0].sha256` | Bundle-level SHA-256 remains null with an honest `sha256_note`; fragment-level hashes and source-document hashes are recorded, so traceability is not broken |
| F-5 | NOTE | bundle fragments `pdf_page` fields; claim line ranges | PDF page references were verified by the source curator during curation; this critique re-verifies against the official HTML (the primary source) — PDF pages were not independently re-checked here (no PDF tool in the critic toolset) |
| F-6 | NOTE | `PTX-XOR-SEM1-003`, AMB-1, traceability summary | Bounded base scope covers only the scalar 32-bit `.b32` form of `xor` (`.pred`/`.b16`/`.b64` deferred), human-confirmed at Gate A (D-0c); the Gate B reviewer should reconfirm the carried scope and the DERIVED state-level reading of "do nothing" |

## 5. Findings detail

### F-1 — MINOR — Interpretive tail inside SOURCE_FACT claim PTX-XOR-SEM1-015

- **Exact location:** `semantic_claims` PTX-XOR-SEM1-015 (line 196 of the artifact): statement "Registers (.reg state space) are fast storage locations; aside from 1-bit predicate registers, scalar registers have a width of 8-, 16-, 32-, 64-, or 128-bits (32-bit width is therefore possible for .b32 registers); registers are not fully addressable."
- **Relevant official evidence:** Section 5.1.1 Register State Space, lines 2617-2627 (verified): register widths and 1-bit predicate registers at lines 2622-2624; "not fully addressable" at lines 2626-2627. The quoted content is accurate.
- **Description:** The claim is classified SOURCE_FACT, but its statement embeds the interpretive tail "(32-bit width is therefore possible for .b32 registers)", which is a derived reading of the listed widths rather than source text. This is the same classification-hygiene pattern the mov.b32 and not.b32 semantic critiques flagged as F-1. The artifact's own claim PTX-XOR-SEM1-002 records the policy "interpretive tails are kept out of SOURCE_FACT statements" (claim 002's interpretation_note, applying the mov.b32 lesson), so claim 015 is inconsistent with the artifact's stated policy. The tail is harmless and correctly acknowledged in the interpretation_note; the issue is classification purity only.
- **Consequence:** Downstream traceability tooling that treats SOURCE_FACT statements as verbatim source content could pick up the parenthetical as if it were official text. No semantic content is wrong.
- **Required owner:** Semantic Extractor (future revision; not required before Gate B).
- **Required revision:** In a future revision, move the parenthetical out of the SOURCE_FACT statement (into the interpretation_note, or into a DERIVED claim). Not required before Gate B; content is accurate.
- **Human review required:** No.

### F-2 — MINOR — Wording of claim PTX-XOR-SEM1-038 could be misread as a positive source assertion

- **Exact location:** `semantic_claims` PTX-XOR-SEM1-038 (line 219 of the artifact): statement "State write: when the instruction executes with a real destination register, the destination register d is updated with the bitwise exclusive-or of the values read from sources a and b. The source states no other register write for the bounded base xor.b32 form."
- **Relevant official evidence:** The xor Semantics `d = a ^ b;` (line 14341), description (line 14338), and syntax `xor.type d, a, b;` (lines 14332-14334) establish the single destination write; the source does not contain an explicit sentence asserting "no other register is written."
- **Description:** The sentence "The source states no other register write for the bounded base xor.b32 form" is ambiguous between (a) the intended absence reading "the source does not state any other register write" and (b) a positive assertion "the source states that there are no other register writes." The source does not contain the positive assertion; the locality conclusion is derived from the absence of any other writable operand in the syntax. Claim 039 (state-write locality) states the same content correctly, grounding it in "the base form has no such operands." Because claim 038 is a DERIVED_INTERPRETATION, the substance is not wrong; the wording risk is that a Gate B reviewer or downstream tooling reads it as a quoted negative.
- **Consequence:** Possible misreading of an absence-based inference as a positive source fact; no semantic content error.
- **Required owner:** Semantic Extractor (future revision; not required before Gate B).
- **Required revision:** In a future revision, rephrase to "the source does not state any other register write for the bounded base xor.b32 form (the base form has no other writable operand)", aligning with claim 039's grounding. Not required before Gate B.
- **Human review required:** No.

### F-3 — MINOR — Negative-search claim's evidence location is not fragment-addressable

- **Exact location:** `semantic_claims` PTX-XOR-SEM1-073 (line 254 of the artifact), `evidence_fragment_ids: ["PTX-9.3-XOR-009"]`.
- **Relevant official evidence:** The bundle-level `predication_evidence_search` log (source-bundle lines 59-125) records the literal searches `@p xor` (0 matches), `xor.pred` (0 matches), `xor.b32 %` (0 matches), `xor.b32` (2 matches: HTML line 14353 and line 23754 `redux.sync.xor.b32`), `xor.b64` (1 match: HTML line 19000, a multimem example).
- **Description:** The claim's evidence_fragment_ids point only to fragment PTX-9.3-XOR-009 (the xor Examples block), which does not itself contain the negative-search results; the search log is a bundle-level field with no fragment ID. Under the semantic stage's rule that claims may reference only bundle fragment IDs, the claim's true evidence location is unreferenced. The claim text is accurate: this critique independently re-ran the searches and confirmed `@p xor` = 0, `xor.pred` = 0, `xor.b32` = 2 matches at lines 14353 and 23754, and `xor.b64` = 1 match at line 19000 (multimem, a different instruction).
- **Consequence:** Traceability soft spot for negative-evidence claims only; no content error.
- **Required owner:** Semantic Extractor / Source Curator (future revision, optional).
- **Required revision:** Optionally record in the claim's interpretation_note that the negative-search log is the bundle-level `predication_evidence_search` field. Not required before Gate B.
- **Human review required:** No.

### F-4 — NOTE — Bundle-level SHA-256 still null

- **Exact location:** `source_bundle_references[0].sha256` (line 41), with honest `sha256_note` stating no value was fabricated.
- **Relevant official evidence:** The bundle records fragment-level `fragment_sha256` for all 33 fragments (helper files exist under `source-bundles/.hash-material/PTX-9.3-XOR-001..033.json`) and source-document hashes (HTML `e2095c4a...`, PDF `769cc12e...`), which match the source manifest and SHA256SUMS.
- **Description:** The semantics does not fabricate a bundle hash. Traceability to the bundle is by path and bundle_id; bundle content was verified at SOURCE_CURATION (run.json history, 16:24:43).
- **Consequence:** Minor traceability soft spot only.
- **Required owner:** Semantic Extractor / Orchestrator (optional).
- **Required revision:** None required.
- **Human review required:** No.

### F-5 — NOTE — PDF page references verified by the source curator, not re-verified here

- **Exact location:** bundle fragments `pdf_page` fields (e.g., 256/257 for the xor section, 400 for section 9.7.13.2) and the PDF page references inside claims (e.g., PTX-XOR-SEM1-001 "PDF page 256", PTX-XOR-SEM1-028 "PDF page 400").
- **Relevant official evidence:** The source curator's pass recorded that all PDF page references were verified against the official PDF (pages 46-47, 53-54, 62, 65, 66, 111, 131-132, 139, 254-258, 399-400, plus targeted searches) and that the HTML is the primary source. The critic toolset exposes only the whitelisted HTML; this critique re-verified every fragment quote and HTML line range (all match), not the PDF pages.
- **Description:** No discrepancy found; HTML line ranges in claims (14324-14327, 14330-14336, 14337-14338, 14339-14343, 14344-14346, 14347-14348, 14349-14350, 14351-14356, 21826-21839, 21840-21845, 21846-21853) all match the verified anchors.
- **Consequence:** None.
- **Required owner:** None.
- **Required revision:** None.
- **Human review required:** No.

### F-6 — NOTE — Bounded base scope and DERIVED guard-false reading to be reconfirmed at Gate B

- **Exact location:** `PTX-XOR-SEM1-003` (DESIGN_DEPENDENCY), `PTX-XOR-SEM1-005` (DERIVED), AMB-1, traceability summary; correspondingly architecture D-0c / OQ-4.
- **Relevant official evidence:** Section 9.7.8.3 (verified): `xor.type d, a, b;` with `.type = { .pred, .b16, .b32, .b64 };` (lines 14332-14334); examples `xor.b32  d,q,r;` and `xor.b16  d,x,0x0001;` (lines 14353-14354).
- **Description:** The unit name `xor.b32` is narrower than the full `xor` type set. The scope reduction (scalar `.b32` only; `.pred`/`.b16`/`.b64` deferred to future units) was explicitly human-approved at Gate A (D-0c) and the semantics inherits it correctly without re-interpreting the out-of-scope forms. Similarly, the state-level reading "no state component changes" of the official "do nothing" clause is a DERIVED interpretation (PTX-XOR-SEM1-035, confidence medium) that the Gate B reviewer should explicitly confirm.
- **Consequence:** None if the Gate B reviewer reconfirms the bounded scope and the DERIVED guard-false reading.
- **Required owner:** Human Gate B reviewer (scope and interpretation confirmation); Semantic Extractor for future `.pred`/`.b16`/`.b64` units.
- **Required revision:** No artifact change required.
- **Human review required:** Yes (Gate B scope and interpretation confirmation).

## 6. Source-verification notes

Specification-tool calls used in this critique: 9 restricted context reads, 2 restricted span reads, and 1 literal-search verification set (3 searches: `@p xor`, `xor.pred`, `xor.b32`) against the official HTML via the restricted spec tools, plus candidate read/grep checks on the artifacts.

All load-bearing source facts were re-verified and remain accurate against the official HTML:

- **xor section 9.7.8.3** (anchor `logic-and-shift-instructions-xor`, line 14324; section 14324-14357): Description "Bitwise exclusive-OR (inequality)." (14329); Syntax `xor.type d, a, b;` / `.type = { .pred, .b16, .b32, .b64 };` (14332-14334); Description "Compute the bit-wise exclusive-or operation for the bits in `a` and `b`." (14338); Semantics `d = a ^ b;` (14341); Notes "The size of the operands must match, but not necessarily the type." / "Allowed types include predicate registers." (14345-14346); PTX ISA Notes "Introduced in PTX ISA version 1.0." (14348); Target ISA Notes "Supported on all target architectures." (14350); Examples `xor.b32  d,q,r;` and `xor.b16  d,x,0x0001;` (14353-14354). Confirmed. All match fragments XOR-001..009.
- **Family intro 9.7.8** (anchor `logic-and-shift-instructions`, line 14236): untyped bit-wise operations on operands of the same size; `and`, `or`, `xor`, `not` also operate on predicates; instruction list includes `xor` (14240-14255). Confirmed (XOR-010).
- **Sibling immediates** (anchors `logic-and-shift-instructions-or` line 14290; `logic-and-shift-instructions-and` line 14256): `or.b32  mask mask,0x00010001` at 14319 (both printed anomalies — missing comma between the `mask` tokens and missing terminating semicolon — faithfully recorded); `and.b32  sign,fpvalue,0x80000000;` at 14286. Confirmed (XOR-011/012).
- **Predication applicability** (anchor `instructions`, line 8718): "All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax." (8722-8723). Confirmed (XOR-013).
- **Section 9.2 PTX Instructions** (anchor `ptx-instructions`, line 7513): 0-4 operands plus optional guard; `@p opcode d, a, b;` form; `d` destination / `a, b, c` sources (7517-7527); bit bucket `_` (7534-7535). Confirmed (XOR-015/016).
- **Section 9.3 Predicated Execution** (anchor `predicated-execution`, line 7537): predicate registers virtual with `.pred` type (7541-7542); guard syntax `@{!}p` and unconditional execution without guard (7547-7550); examples `@p add.s32 j, j, 1;` (7562) and `@!p bra L1;` (7570). Confirmed (XOR-017/018/019).
- **Section 9.7.13 / 9.7.13.1 / 9.7.13.2** (anchors `control-flow-instructions` line 21788, `control-flow-instructions-curly-braces` line 21801, `control-flow-instructions-at` line 21826): construct list `{} @ bra call ret exit` (21794-21799); `{}` instruction grouping (21809-21815); `@` predication with Description "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." (21838-21839), Semantics "If {!}p then instruction" (21841), PTX ISA/Target ISA Notes (21843/21845), Examples (21848-21851). Confirmed (XOR-029..033).
- **Section 5.2.1 Fundamental Types** (anchor `fundamental-types`, line 3015): fundamental type = basic type + size; register variables always of a fundamental type (3019-3022); Table 8 lists `.b32` under "Bits (untyped)" (3053-3054); compatibility rules "The bit-size type is compatible with any fundamental type having the same size." (3062-3066). Confirmed (XOR-020/021/022).
- **Section 5.1.1 Register State Space** (anchor `register-state-space`, line 2613): registers fast storage (2617); widths 8/16/32/64/128, predicate 1-bit (2622-2624); not fully addressable (2626-2627). Confirmed (XOR-023).
- **Section 5.1.2 Special Register State Space** (anchor `special-register-state-space`, line 2633): `.sreg` predefined, platform-specific (2637-2639). Confirmed (XOR-024).
- **Section 5.4.1 Variable Declarations** (anchor `variable-declarations`, line 3747): declaration names state space/type/size/name/optional array/initializer/fixed address; predicate variables only in register state space (3751-3755). Confirmed (XOR-025).
- **Section 5.4.6 Parameterized Variable Names** (anchor `parameterized-variable-names`, line 3933): `.reg .b32 %r<100>;` declares `%r0`..`%r99`; shorthand with any fundamental type and any state space (3940-3948). Confirmed (XOR-026).
- **Section 5.2.2 Restricted Use of Sub-Word Sizes** (anchor `restricted-use-of-sub-word-sizes`, line 3070): `.u8`, `.s8`, `.b8` restricted to ld/st/add/sub/min/max/neg/cvt (3074-3075); `.b32` not in the list. Confirmed (XOR-027).
- **Section 7.1 predication exception** (anchor `function-declarations-and-definitions`, line 6139; span 6257-6262): "st.param and ld.param instructions used for argument passing cannot be predicated." (6260-6261). Confirmed (XOR-028).
- **Section 9.1 Format and Semantics** (anchor `format-and-semantics-of-instruction-descriptions`, line 7505): instruction descriptions include name, format, semantics, examples (7509-7511). Confirmed (XOR-014).
- **Unrelated-instruction matches** (for GAP-8 claim 073): `redux.sync.xor.b32 dst, src, mask;` at line 23754 (verified via span read); `multimem.cp.reduce.async.bulk.global.shared::cta.bulk_group.xor.b64 [dstMem], [srcMem], size;` at line 19000 (verified via span read); both are different instructions from the logic `xor`. Confirmed.
- **Document hashes:** HTML SHA-256 `e2095c4a...` (47,743 lines), PDF SHA-256 `769cc12e...` — match source-manifest.json and SHA256SUMS. Confirmed.
- **Literal searches (bundle log):** `@p xor` (0), `xor.pred` (0), `xor.b32 %` (0), `xor.b32` (2: lines 14353 and 23754), `xor.b64` (1: line 19000) — independently re-run for `@p xor`, `xor.pred`, `xor.b32` and consistent with the fragment evidence; GAP-8 handling (OPEN_QUESTION, negative results support no claims) is correct.

Claim-level verification:

- Claim IDs are sequential 001..073 with no gaps or duplicates; `traceability_summary.claim_counts` (31/23/6/0/13 = 73) matches an exhaustive scan of the `semantic_claims` array (the additional classification fields outside the array — modifiers, preconditions PRE-1..7, state reads/writes, determinism — are structural sections, not claims).
- Every claim's `evidence_fragment_ids` reference only `PTX-9.3-XOR-001..033`; `fragment_ids_used` lists exactly those 33 IDs; no out-of-bundle references and no add.u32/mov.b32/not.b32 semantic evidence imported (the mov.b32 Gate B rejection is used only as a process lesson, per the evidence_interface_note).
- All architecture cross-references used by the semantics exist in foundation-v1.md (D-0c, D-1, D-3, D-5, D-8, D-11, D-14, D-16, D-25, OQ-1..OQ-8, PRF-1..PRF-7).
- Honest gap handling verified: determinism remains DERIVED with explicit non-statement note (GAP-3); immediate source remains OPEN_QUESTION (GAP-1) and sibling immediates are NOT used to infer xor's operand forms (do_not_infer honored, claims 010/066); bit-bucket applicability remains OPEN_QUESTION (GAP-2); error/UB/implementation-defined absence remains OPEN_QUESTION (GAP-4); operand-typing formulation remains OPEN_QUESTION (GAP-5); negative literal-search results remain OPEN_QUESTION (GAP-8).
- Gate A record verified (decision `approved`); Gate B lesson directive verified (decision `rejected`, directive recorded); run history confirms source-bundle-v1 creation at 16:24:43 and semantics-v1 creation at 16:45:15.

No SOURCE_FACT mislabeling of interpretation as fact in the load-bearing claims (only the F-1 parenthetical in claim 015); the guard-false consequence is correctly classified DERIVED (not SOURCE_FACT, not ASSUMPTION); no phantom fragment IDs; no invented error/UB behavior; no use of `sorry`/`admit`/axioms/`unsafe` (no Lean exists); no vacuous theorem statements (no theorems exist). The four-label taxonomy is used consistently except for the F-1 interpretive tail in claim 015.

## 7. Required revisions (consolidated)

No substantive revisions are required before Gate B. Optional refinements:

1. Move the interpretive tail out of the SOURCE_FACT statement of claim PTX-XOR-SEM1-015 (F-1) — classification hygiene; align with the policy stated in claim 002's interpretation_note.
2. Rephrase the "The source states no other register write" sentence of claim PTX-XOR-SEM1-038 to the absence reading aligned with claim 039's grounding (F-2).
3. Optionally record the bundle-level `predication_evidence_search` location in claim PTX-XOR-SEM1-073's interpretation_note (F-3).
4. Optionally record the bundle SHA-256 when a hash tool is available (F-4).
5. Gate B reviewer to reconfirm the bounded base scope (scalar `.b32` only) and the DERIVED state-level reading of "do nothing" (F-6).

## 8. Residual open questions

- Will the Gate B reviewer accept the DERIVED_INTERPRETATION classification of the `xor.b32` guard-false consequence, including the state-level reading of "do nothing" as "no state component changes" (PTX-XOR-SEM1-035, PRF-4)? This is now evidence-backed by section 9.7.13.2; the reviewer's confirmation is the intended gate.
- Will the Gate B reviewer approve determinism as a DERIVED interpretation (PTX-XOR-SEM1-047, GAP-3) and the derived no-other-write locality reading (PTX-XOR-SEM1-038/039)?
- Is PRF-6's disposition (possible reclassification as a VAL-style definitional obligation) confirmed at the theorem-design stage (Gate C / theorem-strength gate)?
- Does the Gate B reviewer reconfirm that the bounded base unit (scalar `.b32` form only) is the intended `xor.b32` unit (F-6)?

## 9. Gate B readiness assessment

Ready for presentation to Human Gate B. The semantic interpretation is source-faithful, traceable (73 claims, all to bundle fragment IDs 001-033), honest about all evidence gaps (GAP-1/GAP-2/GAP-4/GAP-5/GAP-8 handled as OPEN_QUESTION; GAP-3 determinism handled as an explicitly non-stated DERIVED item; never as invented source facts), and consistent with the human-approved architecture scope (foundation-v1, Gate A approved). The mov.b32 Gate B lesson is fully implemented: explicit false-guard no-op evidence from section 9.7.13.2 is part of the bundle, the guard-false consequence is classified DERIVED (not ASSUMPTION), and zero ASSUMPTION-classified claims remain. The core `xor.b32` semantics (`d = a ^ b;` over the 32-bit untyped bit-value domain), operand order/roles (`d, a, b`), bit width (32-bit "Bits (untyped)"), no-modifier reading, guard/predication behavior (`@p`, `@!p`, no-guard), state reads/writes, version (PTX ISA 1.0), and target set (all architectures) are all directly evidenced and correctly interpreted. The three MINOR findings (F-1 classification tail in claim 015; F-2 wording in claim 038; F-3 negative-search evidence location) are wording/traceability refinements; F-4/F-5/F-6 are notes. The artifact itself correctly records `gate_b_status: NOT READY`, the proper state for a candidate awaiting human approval. This assessment is not a Gate B approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/xor-b32/semantics/semantics-v1.json`. No semantic claims were rewritten, no source evidence was fabricated, no Lean code was written, and no `xor.b32` exclusive-or or guard semantics were altered during this review. No gates were approved and nothing was promoted to `accepted/`.
