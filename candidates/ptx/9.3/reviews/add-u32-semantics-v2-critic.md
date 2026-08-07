# Independent Pre-Gate-B Semantic Critique: PTX ISA 9.3 `add.u32` — Semantic Interpretation v2

- Review ID: `ptx-add-u32-semantics-v2-critic`
- Reviewer role: Semantic Critic (independent)
- Review date: 2026-08-07
- Unit: PTX ISA 9.3 `add.u32` (bounded semantic interpretation `ptx-9.3-add-u32-semantics-v2`)
- Review type: independent pre-Gate-B semantic critique
- Overall conclusion: **READY_FOR_HUMAN_REVIEW.** The semantic interpretation is sufficiently faithful, explicit, non-circular, and traceable to be presented to the human for Gate B. 0 BLOCKERs, 0 MAJORs, 2 MINORs, 4 NOTEs. No reviewed artifact was modified.

---

## 1. Scope, inputs, and independence

This critique reviews the semantic interpretation candidate
`candidates/ptx/9.3/semantics/add-u32-v2.json` (SHA-256
`76499344dc8767c7acca596a8b8bcb8aad671779b581e74bf94d57dd52f9bbb6`, 965 lines) against:

| # | Artifact | Role |
|---|---|---|
| 1 | `candidates/ptx/9.3/semantics/add-u32-v1.json` (SHA-256 `b56831645736479b5e204500087c6cbb6615055a8af9f4307c98774dca9b4165`) | prior blocked revision, revision_of target |
| 2 | `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md` (SHA-256 `3857b9cb512cc77981365228b454f34153d2ccd5308ac5499194b30ec003e9d7`) | approved language architecture (Gate A) |
| 3 | `candidates/ptx/9.3/source-bundles/add-u32-v1.json` (SHA-256 `c137078da5e8e0a475a090ae16409cd89d6ee7b93911f0b78a9a36f94d2a4924`) | primary bounded official-source bundle (fragments PTX-9.3-ADD-001..027) |
| 4 | `candidates/ptx/9.3/source-bundles/add-u32-blockers-supplement-v2.json` (SHA-256 `a74ab1167e4a20d5aa37360713aec8a28ee219763c93f28e3a47c57ae81c1fec`) | supplementary official-source evidence (fragments PTX-9.3-ADD-SUP2-001..007) |
| 5 | `reviews/ptx-add-u32/gate-a/ptx-add-u32-gate-a-v2.json` | Gate A decision (approved) |
| 6 | `reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json` | human-approved overflow assumption (decision: approved) |
| 7 | `candidates/ptx/9.3/reviews/add-u32-semantic-blockers-v1-critic.md` (SHA-256 `0cca5cee320a3fd33c14ae283f40be07cd0ef554186f9edca4010b40d781262b`) | prior critic review of v1 (BLOCK-1 UNSUPPORTED; BLOCK-2 PARTIALLY_SUPPORTED) |

Independent verification was performed against the whitelisted official HTML
(`documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, SHA-256
`e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`) using the
restricted specification tools, and against the SHA256SUMS acquisition record
and the source manifest. No raw PDF tool is available to this critic, so PDF
page numbers are not independently re-verified (see NOTE-3). No Lean
formalization was performed. No Gate B approval is made or implied.

Required inputs for a semantic-interpretation critique are all present:
bounded source bundle (primary + supplement), exact evidence fragment IDs,
semantic interpretation candidate, and approved language architecture (Gate A
`approved`, human confirmation recorded).

---

## 2. Verification checklist (task items 1-14)

### 2.1 Every SOURCE_FACT is supported by curated official evidence — CONFIRMED

All 28 claims classified `SOURCE_FACT` in the semantic_claims array
(PTX-ADD-SEM2-001..041, 047) were checked against the cited evidence fragment
IDs and the underlying official HTML:

- Construct identity / add section existence (SEM2-001; ADD-001): verified at
  HTML 8757-8760, anchor `integer-arithmetic-instructions-add`. ✓
- Section 9.1 framing (SEM2-002; ADD-013): verified at HTML 7509-7511. ✓
- Exact syntax variants (SEM2-003; ADD-003): verified at HTML 8765-8772. ✓
- Operand order and role conventions (SEM2-004; ADD-014): verified at HTML
  7517-7527 ("the `d` operand is the destination operand, while `a`, `b`, and
  `c` are source operands"). ✓
- Meaning and execution descriptions (SEM2-005/006; ADD-002/004): verified at
  HTML 8762 and 8776. ✓
- Operand typing and the `.b32` packed-only exception (SEM2-008; ADD-005):
  verified at HTML 8783-8784. ✓
- `.u32` fundamental type (SEM2-009; ADD-019/020): verified (Table 8 "Unsigned
  integer: .u8, .u16, .u32, .u64"; fundamental-type prose). ✓
- Register widths and non-addressability (SEM2-010; ADD-022): verified. ✓
- Type compatibility (SEM2-011; ADD-021): verified. ✓
- Semantics block three branches (SEM2-013; ADD-006): verified at HTML
  8787-8809, else branch `d = a + b;` at 8807-8809. ✓
- Section 9.6 "described using C" notation statement (SEM2-014;
  ADD-SUP2-002): verified at HTML 8693. The claim explicitly states the
  notation does not import ISO C arithmetic rules and that no C overflow
  semantics are used. ✓
- Universal predication (SEM2-017; ADD-011): verified at HTML 8722. ✓
- Guard rule (SEM2-018; ADD-016): verified at HTML 7547-7550. ✓
- `@p add.u32 x,y,z;` example (SEM2-019; ADD-010): verified at HTML 8836. ✓
- Guard examples (SEM2-020; ADD-018): verified at HTML 7561-7572. ✓
- Predicate registers `.pred` (SEM2-021; ADD-017): verified at HTML
  7541-7546. ✓
- Predication construct 9.7.13.2 clause (SEM2-022; ADD-SUP2-006/007):
  verified at HTML 21826-21841 ("Threads with a False guard predicate do
  nothing"; Semantics "If {!}p then instruction"). ✓
- Guard-predicate state read (SEM2-027; ADD-016/017/SUP2-005): verified. ✓
- Destination update write (SEM2-028; ADD-004/006): verified for the positive
  portion; the negative-evidence portion is the subject of MINOR-1. ✓ (with
  finding)
- Static preconditions (SEM2-032/034/035; ADD-005/021/012/025/026/016/017/023):
  verified. ✓
- Version/target notes and .sat scoping (SEM2-037/039/040/041;
  ADD-008/009/007): verified at HTML 8822-8833 and 8817-8818. ✓
- General bit-bucket rule (SEM2-047; ADD-015): verified at HTML 7534-7535. ✓

No SOURCE_FACT was found to misquote, overstate, or fabricate official
content.

### 2.2 Every DERIVED_INTERPRETATION follows from its cited evidence and stated dependencies — CONFIRMED

All 14 claims classified `DERIVED_INTERPRETATION` were checked:

- Destination-only update (SEM2-007), add.u32 identity as the scalar
  non-saturating .u32 form (SEM2-012), destination precondition (SEM2-033),
  version gating (SEM2-036): each follows directly from the cited add syntax,
  typing rules, and version notes. ✓
- Destination update fully determined as `(a + b) mod 2^32` (SEM2-016) and
  state-write detail (SEM2-029): both declare explicit `depends_on:
  PTX-ADD-SEM2-015` on the human-approved assumption. ✓
- Complete guard-expression model (SEM2-023) and guard-false no-op (SEM2-024,
  SEM2-031): follow from the universal predication rule (ADD-011), the
  guard rule (ADD-016), the official examples (ADD-018), and the explicit
  9.7.13.2 clause (SUP2-005/006/007). ✓
- State reads (SEM2-025/026), bit-bucket discard (SEM2-030, confidence
  medium, explicitly "supported only to the strength of the general rule"),
  determinism (SEM2-042, explicitly derived, NOT a source fact, stated as
  PRF-1), and aliasing/read-before-write (SEM2-043, grounded in the official
  example `add.u32 %r, %r, 4;` where d == a): each is a faithful reading of
  the cited evidence. ✓

### 2.3 Modulo-2^32 is never represented as an NVIDIA SOURCE_FACT — CONFIRMED

- The modulo-2^32 rule exists only in claim PTX-ADD-SEM2-015, classified
  `HUMAN_APPROVED_ASSUMPTION`, and in the `result_rule` /
  `result_rule_classification` fields, which explicitly state the rule "is NOT
  an NVIDIA source fact and is never attributed to NVIDIA as explicitly
  specified."
- No claim classified `SOURCE_FACT` contains modulo, wrapping, truncation, or
  low-bits language. The only SOURCE_FACT that touches overflow-adjacent text
  is the `.sat` note (SEM2-041), which is explicitly scoped to the separate
  saturating form.
- The `classification_note` in traceability_summary restates the rule:
  "Modulo-2^32 behavior is never classified as SOURCE_FACT."

### 2.4 Every modulo-dependent claim traces to the human-approved assumption — CONFIRMED

- The human assumption decision record
  (`reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json`)
  was read: decision `approved`, reviewer "Human reviewer", rationale
  explicitly approves the modulo-2^32/low-32-bits rule, explicitly states the
  rule "is not an NVIDIA SOURCE FACT and must never be presented as explicitly
  specified by NVIDIA", and requires the semantic interpretation, Lean
  definitions, executable semantics, bit-width theorems, examples, and final
  traceability to reference the assumption.
- Every modulo-dependent claim carries the dependency: SEM2-015 (the
  assumption itself), SEM2-016 (`depends_on: [PTX-ADD-SEM2-015]`), SEM2-029
  (`depends_on: [PTX-ADD-SEM2-015]`), SEM2-042 (`depends_on:
  [PTX-ADD-SEM2-015, PTX-ADD-SEM2-024]`), the state_writes destination entry
  (`depends_on: [PTX-ADD-SEM2-015]`), the behavior.result_rule, and PRF-7
  (which requires traceability to PTX-ADD-SEM2-015 and forbids classifying the
  rule as SOURCE_FACT).
- The decision record certifies the SHA-256 of the three artifacts it reviews
  (v1 semantics `b5683164...`, supplement v2 `a74ab116...`, v1 critic
  `0cca5cee...`); all three match the actual artifacts read by this critic.
  The record's own SHA-256 is null; see MINOR-2 and item 13 below.

### 2.5 Complete guard expression handling (unguarded -> true; @p -> p; @!p -> not p) — CONFIRMED

`guard_expression_evaluation` (lines 201-206) states:

- no_guard: "The complete guard expression is true; the instruction is
  executed unconditionally."
- at_p: "the complete guard expression is the value of predicate register p;
  execution occurs when p is true."
- at_bang_p: "the complete guard expression is the logical negation of the
  value of predicate register p; execution occurs when p is false."
- execution_condition: "Execution occurs if and only if the complete guard
  expression evaluates true. The underlying predicate value is not confused
  with the evaluated guard expression: for @!p, the guard expression is true
  exactly when the predicate value is false."

This is exactly the required three-case model and corrects the v1-era
negated-guard phrasing concern (architecture F-5). The derived claim
SEM2-023 repeats the model with blocking_if_wrong true.

### 2.6 False complete guard behavior is grounded in official supplementary evidence and is not mislabeled as a human assumption — CONFIRMED

- The `guard_false_consequence` field (line 207) quotes the 9.7.13.2 clause,
  cites SUP2-005/006/007, and states: "This resolves BLOCK-2 by official
  specification evidence; it is not treated as a human assumption."
- SEM2-024 is classified `DERIVED_INTERPRETATION` (not ASSUMPTION), with
  evidence SUP2-005/006/007 + ADD-010/011.
- The `assumptions` array contains exactly one entry: PTX-ADD-SEM2-015
  (modulo). Guard-false behavior is not listed there.
- The v1 assumptions SEM-038 (guard-false pending approval) and SEM-040 (PDF
  not read) are explicitly superseded; the v1 critic's PARTIALLY_SUPPORTED
  verdict for BLOCK-2 is replaced because the explicit clause was found.
- Independent HTML verification: the clause exists verbatim at
  `control-flow-instructions-at`, lines 21838-21839, with Semantics
  "If {!}p then instruction" at 21840-21841; the `do nothing` phrase is a
  single exact match in the whole HTML. The interpretation is correct that the
  base clause is source evidence while its application to add.u32 via
  universal predication is a derived interpretation.

### 2.7 d/a/b roles and ordering — CONFIRMED

- operands.order = "d, a, b (destination first, then two sources)"; roles: d
  destination, a source, b source.
- Verified against HTML 7517-7527 (section 9.2) and the add syntax
  `add.type1 d, a, b;` / `add{.sat}.type2 d, a, b;` (HTML 8765-8766).
- The state_writes and aliasing claims use the correct order (e.g., SEM2-043
  uses the official `add.u32 %r, %r, 4` where the destination is the first
  operand and also a source).

### 2.8 State reads and writes contain no unsupported effects — CONFIRMED

- Reads: source operand a (register or immediate), source operand b (register
  or immediate), guard predicate p (when a guard is present). Each is grounded
  (SEM2-025/026/027).
- Writes: destination register d only (SEM2-028/029); bit bucket -> no write
  (SEM2-030); guard-false -> no state change (SEM2-031).
- No carry flag, status register, condition-code, memory, or concurrency
  component is added to the machine-state effects. The only nuance is the
  negative-evidence classification in SEM2-028 (MINOR-1).

### 2.9 Destination-only/locality behavior does not overstate the source evidence — CONFIRMED

- The positive claim "writes the resulting value into a destination register"
  is a verbatim source fact (SEM2-028 first sentence; HTML 8776).
- The "no other register write" claim is framed as what the source states
  (absence-based) rather than as an independent NVIDIA promise; the
  architecture's destination-only design (D-6, PRF-2) is carried as a future
  frame obligation over the execution relation, not as an asserted source
  fact. See MINOR-1 for the classification-precision observation.

### 2.10 Bit-bucket behavior is no stronger than the curated evidence — CONFIRMED

- SEM2-047 records only the general section 9.2 rule (HTML 7534-7535).
- SEM2-030 derives the no-write consequence "supported only to the strength of
  the general rule; the add section does not demonstrate the bit-bucket form
  (AMB-1)"; confidence medium, blocking_if_wrong false; AMB-1 retained open;
  PRF-3 strength explicitly depends on AMB-1. This is appropriately
  conservative and no stronger than the evidence.

### 2.11 No errors, traps, UB, implementation-defined behavior, or determinism invented from silence — CONFIRMED

- exceptional_behavior: absence recorded as open question SEM2-044; "no error,
  trap, or exceptional behavior is invented."
- undefined_behavior: no claim made (SEM2-045).
- implementation_defined_behavior: no claim made (SEM2-046).
- determinism: "Determinism is NOT explicitly stated in the source (GAP-3);
  it is a derived interpretation that depends on the human-approved assumption
  (PTX-ADD-SEM2-015) and the source-supported guard rule (PTX-ADD-SEM2-024),
  and it is stated as proof obligation PRF-1." Not a source fact; correctly
  classified DERIVED_INTERPRETATION.

### 2.12 No OPEN QUESTION that affects the resulting machine state is incorrectly treated as non-blocking — CONFIRMED

The ten open questions were individually checked for machine-state impact:

- SEM2-038 (no dynamic precondition): absence record; no state-affecting
  consequence. Non-blocking. ✓
- SEM2-044/045/046/055 (absence of error/UB/impl-defined clauses): absence
  records; no behavior invented; state transitions remain fully specified.
  Non-blocking. ✓
- SEM2-053 (immediate range/encoding): affects static well-formedness of
  programs, not the state transition of a given legal instruction.
  Non-blocking. ✓
- SEM2-054 (add-specific bit-bucket demonstration; AMB-1): affects the exact
  set of well-formed destination forms and PRF-3 strength, not the base
  register-destination state behavior. Non-blocking; correctly flagged. ✓
- SEM2-056 ('same family' meaning): future saturating/packed forms only.
  Non-blocking. ✓
- SEM2-057 (PDF page numbers for primary fragments): metadata only.
  Non-blocking. ✓
- SEM2-058 (assumption-record SHA-256): traceability metadata; see MINOR-2.
  Non-blocking for state. ✓

The two state-affecting gaps from v1 (BLOCK-1 overflow result; BLOCK-2
guard-false effect) are both resolved: BLOCK-1 by the human-approved
assumption, BLOCK-2 by official specification evidence. The
`resolved_blockers` section accurately records both resolutions and
`blocking_issues` is empty.

### 2.13 The null human-assumption decision-record SHA-256 — assessed; does not block Gate B

- The v2 semantics records `decision_record_sha256: null` with status
  `NOT_PUBLISHED_IN_REPOSITORY`, explains that no hash-computation tool was
  available and that no hash is fabricated, and records the canonical
  decision_path for every HUMAN_APPROVED_ASSUMPTION claim (open question
  SEM2-058).
- Traceability impact: (a) the decision record's own identity is not
  hash-pinned in the repository, so a future silent modification of the record
  would not be detected by hash comparison alone; (b) however, the record is
  present and readable, its content unambiguously approves the modulo rule and
  explicitly forbids attributing it to NVIDIA, and the three SHA-256 values it
  certifies all match the actual artifacts; (c) the decision path is canonical
  and stable.
- The null hash does not block Gate B because the substance of the human
  decision is directly verifiable at review time, and the semantic artifact
  discloses the gap rather than fabricating a value. It must be closed
  (compute and record the record's own SHA-256, or add a repository-side
  binding) before final acceptance / Gate D. See MINOR-2.

### 2.14 Future theorem-obligation topics are meaningful and not vacuous — CONFIRMED

- PRF-1 (determinism) is stated over an execution relation (not a function),
  following architecture D-25, so it cannot hold vacuously by data-structure
  choice. ✓
- PRF-2 (destination-only frame), PRF-3 (bit-bucket discard, with AMB-1
  dependency), PRF-4 (guard-false frame, with explicit instruction that the
  theorem must not classify the behavior as SOURCE_FACT for add.u32), PRF-5
  (guard-behavior iff, covering no-guard/@p/@!p), PRF-6 (result-domain
  membership), PRF-7 (arithmetic result correctness, with explicit requirement
  to trace to PTX-ADD-SEM2-015 and never classify the modulo rule as
  SOURCE_FACT): each is a meaningful, non-vacuous obligation with grounding and
  no blocked_by dependencies. ✓
- Claim counts are internally consistent: total 58 = 28 SOURCE_FACT + 14
  DERIVED_INTERPRETATION + 5 DESIGN_DEPENDENCY + 1 HUMAN_APPROVED_ASSUMPTION +
  10 OPEN_QUESTION; fragment_ids_used covers all 34 fragments (27 primary + 7
  supplement). ✓

---

## 3. Findings

| Finding ID | Severity | Affected artifact | Exact location | Description | Consequence | Required owner | Human review required |
|---|---|---|---|---|---|---|---|
| SEM2-CRIT-F1 | MINOR | `candidates/ptx/9.3/semantics/add-u32-v2.json` | claim PTX-ADD-SEM2-028; state_writes destination entry | The claim is classified SOURCE_FACT but contains both a positive source fact ("the destination register d is updated with the resulting value", HTML 8776) and a negative-evidence assertion ("The source states no other register write for base add.u32 (no carry flag, status register, or condition-code component)"). The source does not affirmatively enumerate that no carry/status/CC component is written; the negative portion is an absence-based inference and, as stated, cites only ADD-004/006, which do not mention carry flags at all. The wording is honest (it says "the source states no other ...") but the classification mixes a source fact with a negative-evidence claim. | Downstream PRF-2/frame arguments must not cite the negative portion as an explicit NVIDIA statement that "no carry flag is written". The bounded semantics is not affected (no extra write is modeled), so this is not blocking. | Semantic Extractor | No (can be folded into the Gate B human review material) |
| SEM2-CRIT-F2 | MINOR | `candidates/ptx/9.3/semantics/add-u32-v2.json` (SEM2-058); `reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json` | human_assumption_references; open question PTX-ADD-SEM2-058 | The human-assumption decision record does not publish its own SHA-256, and no repository artifact binds it. The v2 semantics records this honestly (null value, NOT_PUBLISHED_IN_REPOSITORY, no fabrication). All hashes the record certifies are accurate, and the record's content matches the semantics' decision_summary. | Residual traceability gap: the decision record's own integrity is not machine-verifiable in the current repository state. It does not block Gate B because the record is readable and the approval substance is unambiguous, but it must be closed before final acceptance (Gate D). | Semantic Extractor / Spec Manager | No |
| SEM2-CRIT-F3 | NOTE | `candidates/ptx/9.3/semantics/add-u32-v2.json` | source_bundle_references; claims citing SUP2-005/006 (PDF pages 132, 400); SEM2-057 | This critic has no raw PDF tool and therefore cannot independently re-verify the PDF page numbers recorded in the supplement (e.g., PDF page 400 for 9.7.13.2). The v2 semantics' state-affecting claims do not depend on PDF-only content: the predication clause that resolves BLOCK-2 is independently verified in the official HTML (21826-21841), and the BLOCK-1 NOT_FOUND determination is consistent with the HTML searches ("wraparound" 0 matches; "modulo" 0 matches). | No impact on faithfulness of the state semantics. PDF page numbers remain a traceability nicety, not a state-affecting fact. | Source Curator (future verification) | No |
| SEM2-CRIT-F4 | NOTE | all reviewed artifacts | cross-artifact | Independent HTML verification confirms every load-bearing evidence point: the @ predication clause (21838-21841), the add section (8757-8842), section 9.2 operand roles (7517-7527), section 9.3 guard rule and examples (7547-7572), section 9.6 "described using C" (8693), the official examples (2902, 6172), and the SHA256SUMS/manifest hashes. Cross-references among the architecture (Gate A approved), v1 critic, supplement v2, assumption record, and semantics v2 are consistent; no semantic drift or circular claim was found. | None; confirms readiness. | n/a | No |
| SEM2-CRIT-F5 | NOTE | `candidates/ptx/9.3/semantics/add-u32-v2.json` | status_rationale; resolved_blockers; open_questions | The status_rationale's assertion that residual open questions "concern only non-state-affecting matters" is accurate: every remaining open question (038, 044-046, 053-058) was checked for machine-state impact and none changes the resulting state of a legal add.u32. BLOCK-1 is resolved only by the human-approved assumption and is never attributed to NVIDIA; BLOCK-2 is resolved by official evidence and is never labeled a human assumption. | None; confirms the interpretation's self-assessment. | n/a | No |

---

## 4. Source-faithfulness and independence notes

1. The semantics correctly refuses to import ISO C arithmetic rules via the
   section 9.6 "described using C" notation statement (SEM2-014 and
   `semantics_notation_note`); no C overflow semantics are used. This avoids
   the v1-critic source-faithfulness risk #1.
2. The semantics never infers modulo behavior from the `.u32` type width
   alone; the modulo rule is explicitly an approved human assumption. This
   avoids risk #2.
3. The semantics never infers false-guard no-op from common ISA practice; the
   guard-false behavior is grounded in the explicit 9.7.13.2 clause. This
   avoids risk #3.
4. `NOT_FOUND`/absence statements are framed as evidence-absence records
   (open questions), never as positive claims about NVIDIA-defined behavior.
   This avoids risk #4.
5. No `sorry`, `admit`, axiom, or unsafe shortcut exists (no Lean was
   produced). No vacuous theorem statements or weakened obligations were
   introduced; PRF-4 and PRF-7 carry explicit anti-overclaim instructions.

---

## 5. Verdict

**READY_FOR_HUMAN_REVIEW**

- READY_FOR_HUMAN_REVIEW means only that Human Gate B may occur; it is not a
  Gate B approval and not a final acceptance.
- Findings: 0 BLOCKER, 0 MAJOR, 2 MINOR, 4 NOTE.
- The two MINOR findings (SEM2-CRIT-F1 classification precision;
  SEM2-CRIT-F2 null decision-record hash) do not affect machine-state
  faithfulness, do not introduce unsupported behavior, and do not require
  revision before Gate B. They should be addressed before final acceptance.
- Modulo-2^32 is correctly isolated as a human-approved assumption and is
  never attributed to NVIDIA.
- False-guard behavior is correctly source-grounded in official supplementary
  evidence (section 9.7.13.2) and is not mislabeled as a human assumption.
- No unsupported state-affecting semantic gap remains.
- The null human-decision-record SHA-256 does not block Gate B.
- No reviewed artifact was modified by this critic; the only artifact created
  is this review.

## 6. Critic independence statement

I, the Semantic Critic, performed this review independently. I read all seven
listed artifacts completely. I verified the load-bearing evidence directly
against the whitelisted official HTML using the restricted specification tools,
and against SHA256SUMS and the source manifest. I did not use model prior
knowledge, CUDA C, LLVM, another ISA, or compiler behavior as evidence. I did
not import ISO C arithmetic semantics. I did not edit, repair, rewrite, or
weaken any reviewed artifact. I did not resolve any open question myself and
did not approve Gate B or any human gate. The only artifact I created is this
review.
