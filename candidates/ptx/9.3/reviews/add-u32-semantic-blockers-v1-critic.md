# Independent Semantic-Blocker Review: PTX ISA 9.3 `add.u32` — BLOCK-1 and BLOCK-2

- Review ID: `ptx-add-u32-semantic-blockers-v1-critic`
- Reviewer role: Semantic Critic (independent)
- Review date: 2026-08-07
- Unit: PTX ISA 9.3 `add.u32` (bounded semantic interpretation `ptx-9.3-add-u32-semantics-v1`)
- Review type: independent blocker review of the bounded semantic interpretation
- Overall conclusion: **BLOCK-1 is genuinely unresolved by the curated official evidence (evidence verdict: UNSUPPORTED). BLOCK-2 is partially supported but not fully resolved (evidence verdict: PARTIALLY_SUPPORTED). Gate B is NOT READY. No reviewed artifact was modified.**

---

## 1. Status

This review independently assesses the two blocking issues recorded against the bounded semantic interpretation `ptx-9.3-add-u32-semantics-v1` (status `BLOCKED`, blocking issues `BLOCK-1` and `BLOCK-2`), using only the five listed artifacts. No raw specification tools were used in this review; the curated evidence was judged as it stands. No Lean formalization was performed. No Gate B approval is made or implied.

Summary of determinations:

| Blocker | Evidence verdict | Recommended human action |
|---|---|---|
| BLOCK-1 (exact 32-bit result when the mathematical sum exceeds the unsigned 32-bit range) | **UNSUPPORTED** | **REQUIRE_MORE_OFFICIAL_SOURCE_SEARCH** |
| BLOCK-2 (machine-state effect when the complete guard expression evaluates false) | **PARTIALLY_SUPPORTED** | **HUMAN_APPROVED_FORMALIZATION_ASSUMPTION** |

New findings introduced by this review: **0 new BLOCKERs; 1 new MAJOR; 1 new MINOR; 1 NOTE** (see Section 5 and the findings table in Section 8). The two pre-existing blockers remain open.

---

## 2. Inputs reviewed and hashes

| # | Artifact | SHA-256 | Verification method |
|---|---|---|---|
| 1 | `candidates/ptx/9.3/source-bundles/add-u32-v1.json` | `c137078da5e8e0a475a090ae16409cd89d6ee7b93911f0b78a9a36f94d2a4924` | returned by bounded candidate reader (full 738-line artifact read) |
| 2 | `candidates/ptx/9.3/source-bundles/add-u32-blockers-supplement-v1.json` | `5f3075fe378d9374a2d28481bbe27f05c3e79f44ad21d0896dbb312a7186ea2b` | returned by bounded candidate reader (full 308-line artifact read) |
| 3 | `candidates/ptx/9.3/semantics/add-u32-v1.json` | `b56831645736479b5e204500087c6cbb6615055a8af9f4307c98774dca9b4165` | returned by bounded candidate reader (full 757-line artifact read) |
| 4 | `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md` | `3857b9cb512cc77981365228b454f34153d2ccd5308ac5499194b30ec003e9d7` | as recorded in artifacts 3 and 5; not recomputed by this review |
| 5 | `reviews/ptx-add-u32/gate-a/ptx-add-u32-gate-a-v2.json` | not independently computed (read via generic file reader; no hash tool invoked) | content verified; records Gate A `approved`, human confirmation recorded |

Note: the Gate A record itself records Gate A as `approved` (reviewer "Human reviewer", `humanConfirmationRecorded: true`, `submittedAtUtc: 2026-08-07T00:37:52.546Z`). Gate A approval is an input fact; it does not constitute Gate B readiness and is not re-approved here.

---

## 3. BLOCK-1 independent assessment

### 3.1 Blocker restated

BLOCK-1: Does the available official evidence determine the exact resulting 32-bit value of base scalar `add.u32` when the mathematical addition of the two `.u32` source values exceeds the unsigned 32-bit range (i.e., when the mathematical sum `a + b >= 2^32`)?

### 3.2 Curated evidence that bears on BLOCK-1

- `PTX-9.3-ADD-002`: "Add two values."
- `PTX-9.3-ADD-004`: "Performs addition and writes the resulting value into a destination register."
- `PTX-9.3-ADD-006`: Semantics block; the scalar else branch is `d = a + b;`.
- `PTX-9.3-ADD-005`, `PTX-9.3-ADD-019`, `PTX-9.3-ADD-020`, `PTX-9.3-ADD-022`: `d`, `a`, `b` have the same type as the instruction type; `.u32` is an unsigned integer fundamental type of size 32; scalar registers have widths including 32 bits.
- `PTX-9.3-ADD-007`: the `.sat` modifier "limits result to MININT..MAXINT (no overflow)" — scoped to the separate saturating form.
- `PTX-9.3-ADD-SUP-001` (section 9.6): "The semantics are described using C, until C is not expressive enough."
- `PTX-9.3-ADD-SUP-002` (section 9.7.2): only `add.cc`, `addc`, `sub.cc`, `subc`, `mad.cc`, `madc` access the condition-code carry flag; base `add` does not.
- Search audit: `wraparound` (0), `modulo` (0), `low-order` (6, all address-masking), `least-significant` (5, one result-width statement but only for `shf.r`), `truncated` (8, `redux.sync` and `ld/st/cvt` only), `overflow` (29, saturating-modifier and other-instruction notes), `carry` (41, extended-precision section only), `low bits` (2, `cvt`/`ld/st` only).

### 3.3 What the evidence establishes and what it does not

Established by the curated fragments:
1. The operation performed is addition of two values (`ADD-002`, `ADD-004`).
2. The pseudocode rule for the scalar branch is `d = a + b;` (`ADD-006`).
3. The destination is a 32-bit unsigned register, so any value written to `d` lies in the 32-bit unsigned value domain (`ADD-005`, `ADD-019`, `ADD-020`, `ADD-022`). This is domain membership only.
4. Base `add` does not record a carry-out anywhere (`ADD-SUP-002`).

NOT established by the curated fragments:
- Which 32-bit value is written when the mathematical sum is at least `2^32`. No explicit wraparound, truncation, modulo-reduction, low-bits selection, carry-discard, trap, saturation (for the base form), or unspecified-value rule appears in the evidence.
- Any shared instruction-family rule that would determine the result width for integer arithmetic.

### 3.4 Can BLOCK-1 be resolved by combining explicit normative fragments?

No. The natural candidates all fail under the review constraints:

- Combining `d = a + b;` with the `.u32` 32-bit type and a 32-bit register destination establishes only that the written value is *some* element of the 32-bit unsigned domain. The mapping from the mathematical sum to that element (e.g., `(a + b) mod 2^32`) is not stated. Inferring modulo behavior from the type width alone is expressly forbidden.
- `ADD-SUP-001` (section 9.6, "described using C") is a notation statement about how the pseudocode is written; it does not import ISO C's unsigned-arithmetic reduction rule as PTX normative text. Even if C arithmetic were imported, the overflow behavior of unsigned arithmetic is defined by ISO C, not by the PTX specification, so relying on it would still be outside-language semantics.
- `ADD-007` (the `.sat` note) shows that when the specification intends to bound results it says so explicitly ("limits result to MININT..MAXINT (no overflow)"). Its absence from the base form is informative context but is not a positive determination of the base form's overflow result.
- The `shf.r` and `redux.sync` result-width statements found by the supplement are correctly judged instruction-specific and cannot be generalized to `add.u32`.

Therefore the exact resulting 32-bit value on overflow **cannot be determined from the curated official evidence** without either importing outside-language semantics or making an unsupported inference.

### 3.5 Is BLOCK-1 essential to the bounded semantics?

Essential to a full-coverage semantic definition of base `add.u32`: the source imposes no non-overflow precondition on operand values, so a semantics that defines the instruction for all legal `.u32` operand pairs must fix the overflow result. BLOCK-1 can be excluded only by an explicit formalization-scope reduction to non-overflowing inputs (a project-level decision, not a source fact), at the cost of not covering all legal operand values.

### 3.6 BLOCK-1 verdict

**Evidence verdict: UNSUPPORTED.** The curated official evidence does not determine the exact resulting 32-bit value of base scalar `add.u32` when the mathematical sum exceeds the unsigned 32-bit range.

**Recommended human action: REQUIRE_MORE_OFFICIAL_SOURCE_SEARCH.** See Sections 5 and 7 for the evidence-sufficiency basis and the full decision space. If, after a further official-source search, the evidence remains silent, the fallback human options are `HUMAN_APPROVED_FORMALIZATION_ASSUMPTION` (assume `(a + b) mod 2^32`) or `REDUCE_FORMALIZATION_SCOPE` (restrict to non-overflowing inputs); either would be a project-level choice and neither may be attributed to NVIDIA's text.

---

## 4. BLOCK-2 independent assessment

### 4.1 Blocker restated

BLOCK-2: Does the available official evidence determine the machine-state effect when the complete guard expression of a predicated `add.u32` evaluates false?

### 4.2 Curated evidence that bears on BLOCK-2

- `PTX-9.3-ADD-016` / `PTX-9.3-ADD-SUP-003` (section 9.3): "All instructions have an optional guard predicate which controls conditional execution of the instruction."; "Instructions without a guard predicate are executed unconditionally."
- `PTX-9.3-ADD-SUP-004` (section 4.3.2): instructions have an optional guard predicate which "controls conditional execution"; written `@p` or `@!p`.
- `PTX-9.3-ADD-018` / `PTX-9.3-ADD-SUP-005`: official example `@p add.s32 j, j, 1; // if i < n, add 1 to j`.
- `PTX-9.3-ADD-SUP-006`: official example `@!p bra L1; // if False, branch over` (false guard prevents the branch action; control falls through).
- `PTX-9.3-ADD-010`: official example `@p add.u32 x,y,z;` — guarded `add.u32` is in scope.
- Search audit: `no-op` (0), `not executed` (1, unrelated), `suppress` (1, unrelated), `conditional execution` (4), full section 9.3 read (lines 7534-7582).

### 4.3 What the evidence establishes and what it does not

Established by the curated fragments:
1. The guard predicate "controls conditional execution of the instruction" (sections 9.3 and 4.3.2).
2. Instructions without a guard execute unconditionally (section 9.3).
3. A guarded `add` executes its add only when the guard is true (the `@p add.s32` example).
4. A false complete negated guard prevents a branch instruction's action — "if False, branch over" (the `@!p bra` example). This demonstrates a false-guard state effect for a control-flow instruction.

NOT established by the curated fragments:
- An explicit clause stating the machine-state effect of a false guard on a value-writing instruction such as `add.u32` — e.g., "the destination register is not written", "the state is unchanged", or any equivalent. The full section 9.3 read and the `conditional execution` search found no such clause.

### 4.4 Can BLOCK-2 be resolved by combining explicit normative fragments?

Partially, and only partially. The uniform guard rule ("controls conditional execution of the instruction"), combined with the `@p add.s32` example (guarded add executes only when the guard is true) and the `@!p bra` example (false guard prevents the instruction's action), supports the reading that a false complete guard expression prevents the instruction from executing. For `add.u32`, "not executing" most naturally means the destination register is not updated and no other state component is modified. However, the specification does not spell out that machine-state consequence for value-writing instructions; stating "the entire state is unchanged" is an inference from the guard rule and examples, not an explicit normative clause. Inferring no-op state behavior from common ISA practice is forbidden; the evidence here is the guard rule plus official examples, which is genuine but partial support.

### 4.5 Is BLOCK-2 essential to the bounded semantics?

Essential to guarded semantics of `add.u32`. Guarded `add.u32` is explicitly in scope: the add Examples block contains `@p add.u32 x,y,z;` (`ADD-010`) and section 9.7 states "All PTX instructions may be predicated" (`ADD-011`). A semantic definition that covers the predicated form must fix the guard-false state effect. BLOCK-2 can be excluded only by excluding predication from the unit, which would drop an official example form and the uniform predication rule — a disproportionate scope reduction.

### 4.6 BLOCK-2 verdict

**Evidence verdict: PARTIALLY_SUPPORTED.** The curated official evidence supports that a false complete guard expression prevents instruction execution, but does not explicitly state the resulting machine-state effect (e.g., that the state is unchanged) for a value-writing instruction.

**Recommended human action: HUMAN_APPROVED_FORMALIZATION_ASSUMPTION.** The precise specification of the assumption is given below.

### 4.7 Precise specification of the recommended assumption (BLOCK-2)

If the human approves a formalization assumption for BLOCK-2:

- **Behavior to be assumed:** For a predicated `add.u32` whose complete guard expression evaluates false (i.e., `@p` with `p` false, or `@!p` with `p` true), the instruction does not execute and the machine state is unchanged: the destination register `d` retains its prior value, source operands are not modified, the guard predicate register is not modified, and no other value-register or predicate-register component changes. Equivalently, the execution relation for `add.u32` has a guard-false case that maps `(state, instruction)` to the identical state.
- **Why it is not a source fact:** PTX ISA 9.3, as curated in `ADD-016`, `ADD-018`, `ADD-SUP-003` through `ADD-SUP-006`, states that the guard "controls conditional execution of the instruction" and demonstrates false-guard suppression for a branch example, but contains no explicit clause stating the machine-state effect of a false guard on a value-writing instruction (no "state is unchanged", "destination is not written", or equivalent). The no-state-update reading is an inference from the guard rule and examples, not an explicit normative statement.
- **Later Lean definitions/theorems that must carry traceability to this assumption:** (a) the execution-relation definition's guard-false branch; (b) the guard-false frame obligation (semantics PRF-4 / architecture PRF-4: "when the complete guard expression evaluates false, the entire state is unchanged"); (c) the guard-behavior obligation (semantics PRF-5 / architecture PRF-5: "the instruction executes if and only if the complete guard expression evaluates true", including the false side); (d) any determinism or locality theorem whose statement covers guarded executions with a false guard; (e) any executable example or test that evaluates a predicated `add.u32` with a false guard. Each such definition/theorem must cite the human-approved assumption identifier (e.g., `PTX-ADD-HA-BLOCK-2`) in its traceability metadata, and no such theorem may classify the guard-false state effect as `SOURCE_FACT`.
- **Claim that must never be made about NVIDIA's specification:** Never claim that "PTX ISA 9.3 specifies that a false guard leaves the machine state unchanged", "NVIDIA defines a predicated-off `add.u32` as a no-op", or any wording attributing the no-state-update behavior to NVIDIA's specification as an explicit normative statement. The only permissible attribution is: "the project adopted a human-approved formalization assumption because the specification is silent on the guard-false machine-state effect."

---

## 5. Evidence sufficiency analysis

### 5.1 Was the supplementary source pass sufficiently broad and careful?

Broad and careful for the official HTML's most natural query vocabulary, with identifiable limits:

- **Strengths.** The supplement searched the core terms for both blockers (`wraparound`, `modulo`, `truncated`, `overflow`, `carry`, `low bits`, `low-order`, `least-significant` for BLOCK-1; `no-op`, `not executed`, `suppress`, `conditional execution` for BLOCK-2), inspected match ranges, correctly classified each match as instruction-specific or unrelated, read the full section 9.3, and read section 9.6 as framing context. It explicitly did not import CUDA C, compiler behavior, another ISA, or unofficial sources, and it did not treat section 9.6's "described using C" as importing C overflow semantics. The curation notes are transparent about method and budget.
- **Limits.** (1) The manifest-listed official PDF artifact (`ptx_isa_9.3.pdf`, SHA-256 `769cc12e363e7bb9cd311464f2a42edbdaf4c74ca18575de8c358e93223434fc`) was never read in the primary pass or the supplement (`read_in_this_curation_pass: false`; `pdf_page` null for all fragments). The PDF is a distinct official artifact in the bounded source manifest; for a blocker classified `NOT_FOUND`, the "available official evidence" has not been fully examined while an official artifact remains unread. (2) The search budget was explicitly capped ("Exactly 20 specification-source tool calls were used; no more searches were performed"), and several plausible overflow-result query terms were not tried (e.g., `truncation`, `wrap`, `out of range`, `2^32`, `low 32`, `discard`, `exceeds`, `result width`, `mod`).

These limits matter for BLOCK-1 (which is `UNSUPPORTED`) and are secondary for BLOCK-2 (which is `PARTIALLY_SUPPORTED` and rests on already-captured guard text plus a full section 9.3 read).

### 5.2 Did the supplement miss a clearly relevant fragment already represented in the bundles?

No. Cross-checking every fragment in both bundles against the two blockers:

- For BLOCK-1, the core fragment is `PTX-9.3-ADD-006` (the `d = a + b;` semantics block). It is already the basis of the blocker in the semantic interpretation (BLOCK-1 `related_fragment_ids` includes `PTX-9.3-ADD-006`) and in the primary bundle's GAP-1. The supplement additionally recorded the two closest searched contexts (`SUP-001`, `SUP-002`) and its `overflow` audit inspected line 8817 (`ADD-007`, the `.sat` note). No curated fragment that would resolve BLOCK-1 was omitted.
- For BLOCK-2, the relevant primary-bundle fragments (`ADD-010`, `ADD-011`, `ADD-016`, `ADD-018`) overlap the supplement fragments (`SUP-003` duplicates `ADD-016`'s quote; `SUP-005`/`SUP-006` split `ADD-018`'s quote). All relevant guard text is represented, and the supplement read the full section 9.3. No curated fragment that would resolve BLOCK-2 was omitted.

The gap is therefore in the unread official PDF and the bounded query set, not in the curated bundle coverage.

### 5.3 Can either blocker be resolved by combining explicit normative fragments without importing outside-language semantics?

- BLOCK-1: **No.** Any determination of the overflow result requires either importing ISO C unsigned-arithmetic semantics (forbidden; section 9.6 is a notation statement) or inferring modulo behavior from the type width alone (forbidden).
- BLOCK-2: **Partially.** The guard rule plus official examples support "false guard prevents execution"; the full "state unchanged" statement is an inference from those fragments, not an explicit clause. Partial support, not full resolution.

---

## 6. Source-faithfulness risks

1. **C-semantics import via section 9.6.** The statement that semantics are "described using C" (`SUP-001`) could be misused to import ISO C unsigned-overflow (modulo) behavior into `add.u32`. It is a notation statement only; the PTX text contains no normative import of C arithmetic rules. Any future modulo behavior must be an approved assumption, not a "source fact".
2. **Modulo inference from type width.** Concluding `(a + b) mod 2^32` from the `.u32` type or the 32-bit register width alone is forbidden. The type establishes the result domain, not the overflow mapping.
3. **No-op inference from common ISA practice.** Concluding "false guard ⇒ no state update" from typical predicated-execution behavior of other ISAs is forbidden. BLOCK-2's partial support comes only from the PTX guard rule and official examples.
4. **Treating absence as a behavioral determination.** `NOT_FOUND`/`UNSUPPORTED`/`PARTIALLY_SUPPORTED` are statements about evidence, not about NVIDIA-defined behavior. It must never be claimed that "NVIDIA specifies no overflow behavior for `add.u32`" or "NVIDIA specifies no state change on a false guard"; the correct statement is that the curated official evidence does not determine these points.
5. **The unread official PDF.** Concluding "no official normative rule exists" for BLOCK-1 while the manifest-listed PDF remains unread overstates the coverage of the official evidence set.
6. **Downstream theorem overclaiming.** Once a human-approved assumption is made, Lean definitions/theorems (e.g., the arithmetic result rule, guard-false frame, guard-behavior) must carry traceability to the assumption ID and must not be labeled source facts. The semantics artifact currently blocks PRF-4, PRF-5 (BLOCK-2) and PRF-6, PRF-7 (BLOCK-1) correctly; that blocking must persist until the human decision.
7. **Circularity/vacuity risk.** Any future theorem that derives the guard-false behavior from a definition that already hard-codes it would be circular; the guard-false case must be stated as an assumption-backed clause and the frame obligations proved over it, not assumed inside the theorem.

---

## 7. Human decision options for each blocker

### 7.1 BLOCK-1 options

1. **REQUIRE_MORE_OFFICIAL_SOURCE_SEARCH (recommended).** Source Curator performs an additional official-source pass covering (a) the manifest-listed official PDF (never read) for the `add` section and any shared integer-arithmetic overflow text, and (b) additional HTML terms such as `truncation`, `wrap`, `out of range`, `2^32`, `low 32`, `discard`, `exceeds`, `result width`, `mod`. If the search confirms silence, the reviewer re-reviews and the human then chooses among options 2-4 with complete information.
2. **HUMAN_APPROVED_FORMALIZATION_ASSUMPTION.** Assume the result written to `d` equals the low-order 32 bits of the mathematical sum, i.e., `(a + b) mod 2^32`, for all `.u32` operand values. This is not a source fact: no curated fragment states a reduction rule; `d = a + b;` (`ADD-006`) is uninterpreted pseudocode; `SUP-001` does not import C arithmetic; the type width establishes only the result domain. Later Lean definitions/theorems (the arithmetic rule in the execution definition; PRF-7 arithmetic result correctness; any full-domain determinism or example) must carry traceability to the approved assumption ID, and no claim may be made that "PTX ISA 9.3 specifies wrapping behavior for `add.u32`".
3. **REDUCE_FORMALIZATION_SCOPE.** Restrict the formalization to well-formed states in which the mathematical sum is below `2^32` (non-overflowing inputs), declared explicitly as a project scope decision. All theorems then carry the non-overflow precondition, and the artifact must not claim full legal-input coverage of `add.u32`. This keeps the unit source-faithful but partial.
4. **KEEP_UNIT_BLOCKED.** Leave the semantic interpretation blocked until one of the above is chosen.

### 7.2 BLOCK-2 options

1. **HUMAN_APPROVED_FORMALIZATION_ASSUMPTION (recommended).** Approve the assumption specified in Section 4.7: a false complete guard expression ⇒ instruction does not execute and the machine state is unchanged. This is the smallest step consistent with the partial evidence, preserves the in-scope official `@p add.u32 x,y,z;` form, and is fully traceable.
2. **REQUIRE_MORE_OFFICIAL_SOURCE_SEARCH.** Search the PDF and further terms for an explicit false-guard state-effect clause. Possible, but the core guard text (full section 9.3) is already captured, and the missing clause is a precise state-effect statement unlikely to be added by more HTML queries; the PDF remains the only unexamined official artifact.
3. **REDUCE_FORMALIZATION_SCOPE.** Exclude predicated forms from the unit. This drops the official example form `@p add.u32 x,y,z;` (`ADD-010`) and the uniform rule "All PTX instructions may be predicated" (`ADD-011`); disproportionate for a first bounded unit.
4. **KEEP_UNIT_BLOCKED.** Leave the semantic interpretation blocked; the guarded semantics of `add.u32` would remain undefined indefinitely.

---

## 8. Findings

### 8.1 Blocker assessments (pre-existing, re-assessed)

| Finding ID | Severity | Affected artifact | Location | Description | Required owner | Human review required |
|---|---|---|---|---|---|---|
| FC-BLOCK-1 | BLOCKER (unchanged) | `candidates/ptx/9.3/semantics/add-u32-v1.json` | BLOCK-1 / GAP-1 / AMB-2 / SEM-041 | Exact overflow/result-width behavior of base scalar `add.u32` is not determined by curated official evidence. Evidence verdict: UNSUPPORTED. | Semantic Extractor + human decision (Source Curator for further search) | Yes |
| FC-BLOCK-2 | BLOCKER (unchanged) | `candidates/ptx/9.3/semantics/add-u32-v1.json` | BLOCK-2 / GAP-2 / AMB-3 / SEM-042 | Machine-state effect when the complete guard expression evaluates false is not explicitly determined; guard rule and examples partially support non-execution. Evidence verdict: PARTIALLY_SUPPORTED. | Semantic Extractor + human decision | Yes |

### 8.2 New findings introduced by this review

| Finding ID | Severity | Affected artifact | Exact location | Evidence references | Description | Consequence | Required owner | Human review required |
|---|---|---|---|---|---|---|---|---|
| NEW-FINDING-1 | MAJOR | `add-u32-blockers-supplement-v1.json` (search coverage); `add-u32-v1.json` (primary bundle GAP-7) | curation notes ("Exactly 20 specification-source tool calls"; PDF `read_in_this_curation_pass: false`); primary bundle GAP-7 | supplement curation notes lines 297, 305; primary bundle lines 42, 713-717 | The manifest-listed official PDF artifact was never read by the primary pass or the supplement. For BLOCK-1 (UNSUPPORTED), the conclusion that no official normative rule exists is not yet grounded in the full set of available official evidence. | `REQUIRE_MORE_OFFICIAL_SOURCE_SEARCH` for BLOCK-1 is warranted before any formalization assumption or scope reduction is approved; without it, "no official evidence" would overstate coverage. | Source Curator | No (routed to source curation; re-review after the pass) |
| NEW-FINDING-2 | MINOR | `add-u32-blockers-supplement-v1.json` | search_audit | BLOCK-1 audit entries | The bounded query set omitted several plausible overflow-result terms (`truncation`, `wrap`, `out of range`, `2^32`, `low 32`, `discard`, `exceeds`, `result width`, `mod`). | Residual risk that a directly relevant clause exists but was not matched; informs the additional-search recommendation. | Source Curator | No |
| NEW-FINDING-3 | NOTE | all reviewed artifacts | cross-artifact | semantics BLOCK-1/BLOCK-2, supplement blocker_results, architecture OQ-2/OQ-3/A-4, gate-a rationale | The three candidate artifacts and the architecture are mutually consistent: both blockers are labeled open; the architecture's guard-false "no state update" (D-6/D-20/PRF-4) and the semantics' SEM-038 agree it is an interpretation pending human approval, not a source fact; no semantic drift or overclaim was found in the reviewed artifacts. | None; confirms the artifacts do not silently resolve the blockers. | n/a | No |

**New BLOCKER count: 0. New MAJOR count: 1.**

---

## 9. Recommended next action

1. **Source Curator:** perform the additional official-source search pass for BLOCK-1 (manifest-listed PDF; additional HTML terms listed in Section 7.1 option 1), and optionally a targeted PDF check for BLOCK-2 state-effect wording. The unit remains blocked during this pass.
2. **Semantic Extractor / Spec Manager:** after (or in parallel with) the search, prepare human review material for the BLOCK-2 `HUMAN_APPROVED_FORMALIZATION_ASSUMPTION` specified in Section 4.7 and, if the BLOCK-1 search confirms silence, for the BLOCK-1 decision among the Section 7.1 options.
3. **No Lean formalization** of the unresolved points; do not unblock PRF-4, PRF-5, PRF-6, PRF-7.
4. Do not present the semantic interpretation for Gate B until both blockers have a human decision and the interpretation is updated and re-reviewed.

---

## 10. Gate B readiness

**Gate B is NOT READY.** The semantic interpretation `ptx-9.3-add-u32-semantics-v1` remains `BLOCKED` on BLOCK-1 and BLOCK-2. No semantic interpretation exists that has been reviewed against the bounded official source bundle with both blockers resolved. This review does not approve Gate B and does not approve any human gate.

---

## 11. Critic independence statement

I, the Semantic Critic, performed this review independently. I read the five listed artifacts completely (source bundle, supplement, semantic interpretation, foundation architecture v2, Gate A record). I did not use raw specification tools in this review; I judged the curated evidence as it stands, per the review instructions. I did not edit, repair, rewrite, or weaken any reviewed artifact. I did not resolve either underspecified point myself: BLOCK-1 remains UNSUPPORTED and BLOCK-2 remains PARTIALLY_SUPPORTED, and the recommended human actions are recommendations only. I did not import ISO C/C++ semantics, CUDA C semantics, another ISA, compiler behavior, or model prior knowledge as evidence. I did not infer modulo behavior from type width, did not infer no-op state behavior from common ISA practice, and did not treat absence of evidence as evidence of a behavior. I performed no Lean formalization and made no human-gate approval. The only artifact I created is this review.
