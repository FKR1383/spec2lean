# Independent Semantic Critique — mov-b32-semantics-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v1.json` (interpretation_id `ptx-9.3-mov-b32-semantics-v1`, status `READY_FOR_CRITIQUE`, 1055 lines), the first semantic interpretation for the bounded `mov.b32` unit.
- This critique is an independent semantic-critic review. It does not approve Gate B and does not edit or repair the reviewed artifact.
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`, 47,743 lines), via the restricted specification tools.
- Source bundle consulted: `candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v1.json` (bundle_id `ptx-9.3-mov-b32-source-bundle-v1`, 32 fragments `PTX-9.3-MOV-001..032`).
- Architecture consulted: `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md` (human-approved at Gate A per `reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json`, decision `approved`, submittedAtUtc `2026-08-07T11:09:53.469Z`).
- Prior review consulted: `candidates/ptx/9.3/units/mov-b32/reviews/architecture-critic-v1.md` (findings F-1..F-5).
- Run metadata consulted: `runs/ptx-9.3-mov.b32-f910feea/run.json` (unit `mov.b32`, stage SEMANTIC_CRITIQUE, revision 8, Gate B pending).

## 2. Overall verdict

**SUITABLE for Human Gate B presentation (no substantive revision required).**

The semantic interpretation is faithful to the bounded source bundle and to the human-approved architecture scope. All 70 semantic claims (`PTX-MOV-SEM1-001..070`) reference only bundle fragment IDs `PTX-9.3-MOV-001..032`; the claim counts (29 SOURCE_FACT, 18 DERIVED_INTERPRETATION, 6 DESIGN_DEPENDENCY, 2 ASSUMPTION, 15 OPEN_QUESTION = 70) are accurate. The core value-copy semantics (`d = a;`, operand order `d, a`, `.b32` untyped 32-bit), guard semantics for `@p`/`@!p`, state reads/writes, and version facts were independently re-verified against the official HTML and are correct. The artifact's honest gap handling — guard-false "no state update" as ASSUMPTION (GAP-1), determinism as DERIVED with explicit non-statement note (GAP-2), target set as OPEN_QUESTION (GAP-7), error/UB absence as OPEN_QUESTION (GAP-3) — is verified sound: the official HTML indeed contains no explicit "does not execute" / "state is unchanged" clause for guard-false and no determinism statement for `mov`.

Findings are limited to one MINOR classification-hygiene item (interpretive tails embedded in SOURCE_FACT claims), one MINOR wording hazard in the `guarded_form` field, one MINOR deferred-vacuity-resolution item (PRF-6, carried from architecture critic F-3), and two NOTE-level observations (bundle-level SHA-256 null in the semantics; bounded base scope is a proper subset of official `mov.b32`). None of these change the semantic content, and none require revision before Gate B presentation. The artifact is ready to be presented to Human Gate B; Gate B is not approved by this review.

## 3. Inputs reviewed

- `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v1.json` — complete candidate read (1055/1055 lines); all 70 claims, preconditions, state reads/writes, guard semantics, behavior, exceptional behavior, determinism, version/target, assumptions, ambiguities, open questions, and traceability summary inspected.
- `candidates/ptx/9.3/units/mov-b32/source-bundles/source-bundle-v1.json` — complete read (858/858 lines); all 32 fragments and all 8 evidence gaps (GAP-1..GAP-8) cross-checked against the claims.
- `candidates/ptx/9.3/units/mov-b32/architecture/foundation-v1.md` — full read; all architecture cross-references used by the semantics (D-0c, D-1, D-3, D-5, D-8, D-11, D-14, D-16, D-25, A-3, A-4, A-6, A-8, OQ-1..OQ-9, AMB-1..AMB-3, PRF-1..PRF-7) confirmed present.
- `candidates/ptx/9.3/units/mov-b32/reviews/architecture-critic-v1.md` — full read (F-1..F-5).
- `reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json` — read; decision `approved`, `humanConfirmationRecorded: true`.
- `runs/ptx-9.3-mov.b32-f910feea/run.json` — read; stage history confirms Gate A approval at 11:09:56 and SOURCE_CURATION verification of the bundle at 11:27:17.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools:
  - anchor `data-movement-and-conversion-instructions-mov` (line 14999), lines 14996-15077: section heading, Description "Write register d with the value of a." (15025), operand-a categories (15026-15027), address semantics (15028-15036), Semantics block `d = a;` first line (15039), Notes (15047-15052), PTX ISA Notes (15055-15058), Target ISA Notes (15060-15061), Examples (15064-15071). All match the bundle fragments.
  - anchor `predicated-execution` (line 7537), lines 7535-7577: `.pred` type (7541-7542), guard syntax `@{!}p` and unconditional-execution rule (7547-7550), examples `@p add.s32` (7562) and `@!p bra L1;` (7570). Match bundle fragments PTX-9.3-MOV-020/021/022.
  - anchor `fundamental-types` (line 3015), lines 3013-3071: fundamental type definition (3019-3022), Table 8 with `.b32` under "Bits (untyped)" (3053-3054), compatibility rules (3062-3066). Match fragments PTX-9.3-MOV-023/024/025.
  - anchor `register-state-space` (line 2613), lines 2611-2633: registers fast storage, 8/16/32/64/128-bit scalar widths, 1-bit predicate, not fully addressable. Matches fragment PTX-9.3-MOV-026.
  - anchor `data-movement-and-conversion-instructions-mov-2` (line 15075), lines 15073-15103: vector pack/unpack description with sink `_` (15089-15095). Matches fragment PTX-9.3-MOV-012.
  - anchor `statements` (line 1652), lines 1650-1670: `.reg .b32 r1, r2;` (1660) and `mov.b32 r1, %tid.x;` (1663). Matches fragment PTX-9.3-MOV-030.
  - literal search `not executed`: 1 match only (setmaxnreg warpgroup context, line 42205), no predication clause.
  - literal search `state is unchanged`: 0 matches.
  - literal search `does not execute`: 0 matches.
  - literal search `deterministic`: 5 matches, none concerning `mov` or general instruction determinism.
- No Lean definitions, theorem obligations, or proofs exist yet; the reviewed artifact is a semantic interpretation candidate only. No Lean review was performed because none was provided at this stage.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | MINOR | SOURCE_FACT claims PTX-MOV-SEM1-049, -053, -054 (and lightly -002) | Interpretive/design parentheticals are embedded inside SOURCE_FACT claim statements (e.g., "not modeled in the instruction-local semantics", "out-of-scope" linkage), blurring the SOURCE_FACT/DERIVED boundary |
| F-2 | MINOR | `syntax.guarded_form` (line 41) | Parenthetical "(equivalently @!p mov.b32 d, a;)" could be misread as semantic equivalence between `@p` and `@!p`; the guard_semantics section correctly disambiguates |
| F-3 | MINOR | `future_theorem_obligation_topics` PRF-6 (lines 999-1002) | Architecture critic F-3 requested the semantic phase to reclassify or reformulate the result-domain-membership obligation; the artifact records the recommendation but retains PRF-6 unresolved with `blocked_by: null` |
| F-4 | NOTE | `source_bundle_references[0].sha256` (line 29) | Bundle-level SHA-256 is null in the semantics (no hash tool at the semantic stage); fragment-level hashes exist inside the bundle, so traceability is not broken |
| F-5 | NOTE | `PTX-MOV-SEM1-004/-013`, AMB-2 | Bounded base scope covers only register/immediate sources of scalar `mov.b32`; this is a proper subset of the official form and was human-confirmed at Gate A; the Gate B reviewer should reconfirm the carried scope |

## 5. Findings detail

### F-1 — MINOR — Interpretive tails embedded in SOURCE_FACT claims

- **Exact location:** `semantic_claims`:
  - PTX-MOV-SEM1-049 (line 628-633): "…and have function-scope/ABI declaration restrictions at the compilation level (spilling, function-scope, legacy module-scope handling are compilation-level notes not modeled in the instruction-local semantics)."
  - PTX-MOV-SEM1-053 (line 659-665): "…All special registers are predefined. This is the state space behind the out-of-scope sreg source category."
  - PTX-MOV-SEM1-054 (line 667-673): "…The generic address may be produced via cvta. This address semantics concerns the out-of-scope avar/avar+imm forms; the device-function-parameter copy-on-stack note also concerns an out-of-scope form."
  - PTX-MOV-SEM1-002 (line 251-257): "…this frames the mov Syntax/Semantics/Examples blocks as normative source content."
- **Relevant official evidence:** The quoted source text portions of these claims are accurate (verified at HTML 2617-2631, 2637-2639, 15028-15036, 7509-7511 respectively). The issue is classification hygiene, not content.
- **Description:** Each of these claims is classified SOURCE_FACT but the claim statement includes a design/scope-interpretation clause (e.g., "not modeled in the instruction-local semantics", "concerns the out-of-scope … forms", "frames … as normative"). The source-quoted portion is a genuine source fact; the appended clause is an interpretation or a design decision that belongs in a DERIVED_INTERPRETATION or DESIGN_DEPENDENCY claim, or at least in a clearly separated sentence of the statement.
- **Consequence:** Downstream traceability tooling that treats SOURCE_FACT claims as verbatim source content could pick up interpretive wording as if it were official text. No semantic claim content is wrong; the risk is classification purity, which the project discipline (four-label taxonomy) requires.
- **Required owner:** Semantic Extractor.
- **Required revision:** In a future revision, split the interpretive clause out of the SOURCE_FACT statement (either into a DERIVED/DESIGN_DEPENDENCY claim or into a clearly marked note field). Not required before Gate B; content is accurate.
- **Human review required:** No.

### F-2 — MINOR — `guarded_form` wording hazard

- **Exact location:** `syntax.guarded_form` (line 41): `"@p mov.b32 d, a;  (equivalently @!p mov.b32 d, a;)"`.
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 7547-7550 (`@{!}p` prefix, `p` optionally negated); semantics' own `guard_semantics.guard_expression_evaluation` (lines 186-191) correctly states that `@!p` executes when the underlying predicate value is false.
- **Description:** The parenthetical "(equivalently @!p mov.b32 d, a;)" appears immediately after the `@p` form. Read in isolation, "equivalently" could suggest that `@p` and `@!p` guarded forms are interchangeable or semantically equivalent, which is false (they have opposite execution conditions). The intended meaning is presumably "the guarded form may alternatively be written with the negated guard". The artifact's own guard_semantics section is unambiguous and correct, so this is a wording-precision issue, not a semantic error.
- **Consequence:** A reader or downstream tool consuming only the `syntax` field could misunderstand guard semantics; the risk is contained because guard_semantics disambiguates.
- **Required owner:** Semantic Extractor.
- **Required revision:** Reword the parenthetical (e.g., "alternatively @!p mov.b32 d, a;") or remove the parenthetical and rely on guard_semantics. Not required before Gate B.
- **Human review required:** No.

### F-3 — MINOR — PRF-6 vacuity resolution deferred rather than executed

- **Exact location:** `future_theorem_obligation_topics` PRF-6 (lines 999-1002), and traceability_summary note at lines 1032-1035.
- **Relevant official evidence:** architecture-critic-v1.md F-3 (lines 78-86) explicitly asked the semantic phase to "reclassify PRF-6 as a definitional/validation-style well-formedness obligation (like VAL-1/VAL-2) or state it over a value domain in which membership is non-trivial".
- **Description:** The semantics artifact's PRF-6 topic restates the architecture critic's recommendation ("the semantic phase should reclassify it as a definitional/validation-style well-formedness obligation … or state it over a value domain in which membership is non-trivial") but does not itself perform the reclassification; PRF-6 remains a future-theorem topic with `blocked_by: null`. The traceability_summary claims F-3 is "addressed" — it is addressed in the sense of being recorded, but the requested decision (reclassify vs. reformulate) is passed forward to the theorem-design stage.
- **Consequence:** Low risk now (no Lean/theorem statements exist); the vacuity hazard re-emerges at theorem-strength review if PRF-6 is stated under the typed register-file representation.
- **Required owner:** Proof Engineer, with Semantic Extractor for the state-representation decision.
- **Required revision:** Resolve the PRF-6 classification at the theorem-obligation design stage (Gate C / theorem-strength gate); optionally, the semantics revision can record the recommended disposition (reclassify to VAL-style) as the decision. Not required before Gate B.
- **Human review required:** Yes (at the semantic/theorem-strength gate).

### F-4 — NOTE — Bundle-level SHA-256 is null in the semantics

- **Exact location:** `source_bundle_references[0].sha256` (line 29), with the honest `sha256_note` explaining no hash tool is available at the semantic stage.
- **Relevant official evidence:** The bundle records fragment-level `fragment_sha256` values for all 32 fragments and the source-document hashes (HTML `e2095c4a…`, PDF `769cc12e…`).
- **Description:** The semantics cannot cite the bundle file's own SHA-256; it does not fabricate one. Traceability to the bundle is by path and bundle_id, and the bundle's content was independently verified at SOURCE_CURATION (run.json history, 11:27:17).
- **Consequence:** Minor traceability soft spot only; no integrity risk because fragment hashes and source-document hashes are recorded.
- **Required owner:** Semantic Extractor / Orchestrator (optional).
- **Required revision:** None required; optionally compute and record the bundle SHA-256 when a hash tool becomes available.
- **Human review required:** No.

### F-5 — NOTE — Bounded base scope is a proper subset of official `mov.b32`; carried from Gate A

- **Exact location:** `PTX-MOV-SEM1-004` (DESIGN_DEPENDENCY), `PTX-MOV-SEM1-013` (DERIVED_INTERPRETATION), AMB-2 (lines 855-861); correspondingly architecture D-0c and architecture-critic F-5.
- **Relevant official evidence:** `ptx_isa_9.3.html` lines 15008-15021 (scalar mov syntax incl. `sreg`, `avar`, `avar+imm`, `fname`, `kernel` forms), line 1663 (`mov.b32 r1, %tid.x;` with special-register source).
- **Description:** The unit name `mov.b32` is broader than the interpreted base unit (register/immediate sources only). The scope reduction was explicitly human-approved at Gate A; the semantics inherits it correctly and does not re-interpret the out-of-scope source categories. This is a confirmation point for the Gate B reviewer, not a defect.
- **Consequence:** None if the reviewer reconfirms the bounded scope; otherwise the base unit would need the `sreg` category and the special-register state space.
- **Required owner:** Human Gate B reviewer (scope confirmation); Semantic Extractor for future `sreg`-form units.
- **Required revision:** No artifact change required.
- **Human review required:** Yes (Gate B scope confirmation).

## 6. Source-verification notes

Specification-tool calls used in this critique: 4 restricted context reads and 4 restricted literal searches (all verified directly against the official HTML).

Verification results:

- All 32 bundle fragment quotes used by the semantics were checked against the bundle and the key ones re-verified against the official HTML: syntax/description/semantics of section 9.7.9.3 (fragments 001-010), vector form 9.7.9.4 (011-014), 9.7.9 intro (015), 9.7 predicability (016), 9.1 (017), 9.2 operand format and bit bucket (018-019), 9.3 predicated execution (020-022), 5.2.1 fundamental types/compatibility (023-025), 5.1.1 register state space (026), 5.1.2 special registers (027), 5.4.1 declarations (028), 5.4.6 parameterized names (029), 4.3 example (030), 5.2.2 sub-word restriction (031), 7.1 predication exception (032). All match.
- Claim counts verified by exhaustive scan: 29 SOURCE_FACT, 18 DERIVED_INTERPRETATION, 6 DESIGN_DEPENDENCY, 2 ASSUMPTION, 15 OPEN_QUESTION = 70 claims; IDs unique and sequential 001..070; traceability_summary counts match.
- Every claim's `evidence_fragment_ids` reference only `PTX-9.3-MOV-001..032`; `fragment_ids_used` lists exactly those 32 IDs. No out-of-bundle references and no add.u32/other-unit evidence (the artifact explicitly prohibits knowledge transfer and honors it).
- All architecture cross-references used by the semantics (D-0c, D-1, D-3, D-5, D-8, D-11, D-14, D-16, D-25, A-3, A-4, A-6, A-8, OQ-1..OQ-9, AMB-1..AMB-3, PRF-1..PRF-7) exist in foundation-v1.md.
- Gate A record verified: `reviews/ptx-mov-b32/gate-a/ptx-mov-b32-a-approval-v1.json` (decision `approved`, `humanConfirmationRecorded: true`, `promotionPerformed: false`).
- Honest gap handling verified against the HTML: no "does not execute", "state is unchanged", or "not executed"-as-guard-false clause exists in the read sections; the only "not executed" match is a `setmaxnreg` warpgroup note (line 42205). No `mov` determinism statement exists ("deterministic" matches are unrelated). The ASSUMPTION classification of guard-false "no state update" and the DERIVED classification of determinism are therefore correct and do not overstate the source.
- The core semantic content is correct: operand order `d, a` (destination first), `d` destination / `a` source roles, `.b32` = Bits (untyped) 32-bit, `d = a;` copy with no arithmetic/truncation, no modifiers, no extra state writes, guard `@p`/`@!p` semantics via the complete guard expression, PTX ISA 1.0 introduction, no family-specific target restriction for the base form.

No SOURCE_FACT mislabeling of interpretation as fact (the guard-false and determinism items are correctly NOT source facts), no phantom fragment IDs, no invented error/UB behavior, no use of `sorry`/`admit`/axioms/unsafe (no Lean exists), and no vacuous theorem statements (no theorems exist). The four-label taxonomy is used consistently except for the F-1 interpretive tails inside SOURCE_FACT statements.

## 7. Required revisions (consolidated)

No substantive revisions are required before Gate B. Optional refinements:

1. Split interpretive clauses out of SOURCE_FACT claim statements (F-1) — classification hygiene.
2. Reword the `guarded_form` parenthetical to avoid a semantic-equivalence misreading (F-2).
3. Resolve PRF-6's reclassification vs. reformulation at the theorem-obligation design stage (F-3).
4. Optionally record the bundle SHA-256 when a hash tool is available (F-4).
5. Gate B reviewer to reconfirm the bounded base scope (register/immediate only) (F-5).

## 8. Residual open questions

- Will the Gate B reviewer approve the guard-false "no state update" ASSUMPTION (PTX-MOV-SEM1-034/038, architecture A-4/OQ-3), or require a source-curation supplement with explicit official evidence (as was done for the add.u32 unit)? PRF-4 is blocked on this decision.
- Will the Gate B reviewer approve determinism as a DERIVED interpretation (PTX-MOV-SEM1-039, GAP-2)?
- Is PRF-6 reclassified as a VAL-style definitional obligation or reformulated over a non-trivial value domain (F-3)?
- Does the Gate B reviewer reconfirm that the bounded base unit (register/immediate sources only) is the intended `mov.b32` unit (F-5)?

## 9. Gate B readiness assessment

Ready for presentation to Human Gate B. The semantic interpretation is source-faithful, traceable (70 claims, all to bundle fragment IDs), honest about all evidence gaps (GAP-1..GAP-8 handled as ASSUMPTION/DERIVED/OPEN_QUESTION, never as invented source facts), and consistent with the human-approved architecture scope. The MINOR findings (F-1, F-2) are wording/classification refinements; F-3 is a theorem-stage decision; F-4 and F-5 are notes. The artifact itself correctly records `gate_b_status: NOT READY`, which is the proper state for a candidate awaiting human approval. This assessment is not a Gate B approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/mov-b32/semantics/semantics-v1.json`. No semantic claims were rewritten, no source evidence was fabricated, no Lean code was written, and no `mov.b32` copy semantics were altered during this review. No gates were approved and nothing was promoted to `accepted/`.
