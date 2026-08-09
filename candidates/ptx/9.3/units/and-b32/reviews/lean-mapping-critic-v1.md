# Independent Lean Mapping Critique — and-b32 AndB32-v1

## 1. Status

- Reviewed artifact: `candidates/ptx/9.3/units/and-b32/lean/AndB32-v1.lean` (505 lines, SHA-256 `bcbe497526596b5da9d96417ec565118c49d2d1374f01ab8e531b2159bc24465`, 23,230 bytes), namespace `Spec2Lean.PTX.AndB32`, produced by the LEAN_FORMALIZATION stage of run `ptx-9.3-and.b32-d33dfec2`.
- This critique is an independent semantic-critic review of the Lean mapping against the human-approved Gate B semantic interpretation. It does not approve Gate C and does not edit or repair the reviewed artifact.
- Approved semantic interpretation reviewed against: `candidates/ptx/9.3/units/and-b32/semantics/semantics-v2.json` (interpretation_id `ptx-9.3-and-b32-semantics-v2`, SHA-256 `45e0fe93f02a3261976962026eb7b5b2e1a5343c10d4a388f500f6f30a24ca0e`; 74 claims: 23 SOURCE_FACT, 32 DERIVED_INTERPRETATION, 7 DESIGN_DEPENDENCY, 0 ASSUMPTION, 12 OPEN_QUESTION).
- Gate B record: `reviews/ptx-and-b32/gate-b/ptx-and-b32-b-approval-v1.json` (decision `approved`, human_confirmation_recorded true, submittedAtUtc 2026-08-09T18:44:55.281Z) — confirmed to exist and to reference the same semantics SHA-256.
- Gate A record: `reviews/ptx-and-b32/gate-a/ptx-and-b32-a-approval-v1.json` (decision `approved`) — confirmed to exist.
- Architecture reference: `candidates/ptx/9.3/units/and-b32/architecture/foundation-v1.md` (SHA-256 `9798324a87bbb883a64f879e96d63e3f5cd9253c1b8b63547812c36254918187`), approved at Gate A.
- Source bundle: `candidates/ptx/9.3/units/and-b32/source-bundles/source-bundle-v2.json` (SHA-256 `57e86be0f823fa70e7559ca21cba30bf7f4b434a87c33cb39b134ce13f27ea53`).
- Authoritative source consulted: `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (PTX ISA 9.3, SHA-256 `e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`).
- Run metadata: `runs/ptx-9.3-and.b32-d33dfec2/run.json` (stage LEAN_MAPPING_CRITIQUE; revision 16; Gate C pending; expected artifact `candidates/ptx/9.3/units/and-b32/reviews/lean-mapping-critic-v1.md`).
- Prior critique consulted as context: `candidates/ptx/9.3/units/and-b32/reviews/semantics-critic-v1.md` (verdict READY FOR PRESENTATION TO HUMAN GATE B; findings F-1..F-5 MINOR/NOTE), `candidates/ptx/9.3/units/and-b32/reviews/architecture-critic-v1.md`.

## 2. Overall verdict

**READY FOR PRESENTATION TO HUMAN GATE C (no blockers; no major defects; the Lean mapping is faithful to the human-approved Gate B semantics; findings are MINOR/NOTE level and do not require a mapping revision before Gate C).**

The Lean candidate maps the approved `and.b32` semantics into Lean with high fidelity and complete traceability:

- **Value domain**: `.b32` is modeled as an untyped 32-bit bit-value domain `B32` wrapping `Fin (2^32)` (b32Bits = 32, b32DomainSize = 2^32), matching the `Bits (untyped)` fundamental type (PTX-AND-SEM2-013/015/026/056, design D-11). No signed/unsigned confusion: the domain is untyped and the operation is the pure bitwise-and `Nat.land` over the 32-bit domain.
- **Operand roles and order**: `AndB32Instruction` carries `d`, `a`, `b` in the official order (`and.type d, a, b;`, AND_SYNTAX_FORM; PTX-AND-SEM2-004/055, D-1/D-16). Distinct types `SourceA` (register only) and `SourceB` (register or immediate) enforce the approved asymmetry: position-`b` immediate is evidenced (PTX-AND-SEM2-024) while position-`a` immediate is an open question (PTX-AND-SEM2-061), so no immediate constructor is introduced for `a` (documented in the header).
- **Semantics rule**: `andValue x y = Nat.land x y mod 2^32` implements `d = a & b;` (PTX-AND-SEM2-008 SOURCE_FACT, PTX-AND-SEM2-032) correctly over the 32-bit untyped domain; verified by executable examples (0&0=0, 0xFFFFFFFF&0xFFFFFFFF=0xFFFFFFFF, 5&3=1, 0xFFFF0000&0x00FF00FF=0x00FF0000).
- **State**: `MachineState` is the minimal pair (value-register file, predicate-register file) per PTX-AND-SEM2-054 / D-5/D-14. Reads are partial (`Option`); missing registers yield `none` (partial execution), not an invented error — consistent with PTX-AND-SEM2-048/049/050 and D-8/PTX-AND-SEM2-058 (no error constructor).
- **Guard/predication**: `Guard` = unguarded | `@p` | `@!p`; `evalGuard` returns true for unguarded, the predicate value for `@p`, and the negation for `@!p` (PTX-AND-SEM2-029/030/035, D-19/D-21). Guard-false yields `ExecOutcome.guardFalse` with the state unchanged (PTX-AND-SEM2-063, source-resolved via CTX-08 "Threads with a False guard predicate do nothing.").
- **State writes**: `updateDestination` writes only the destination value register and preserves all predicate registers (PTX-AND-SEM2-036/037); the bit bucket is a no-write candidate (D-18; PTX-AND-SEM2-062 open question, documented at candidate strength). No memory, special-register, carry, or status components exist (PTX-AND-SEM2-037).
- **Relational form**: `AndB32Step` is the relational counterpart of the executable function per D-25 / PTX-AND-SEM2-057, keeping determinism/frame obligations non-vacuous for the theorem stage.
- **Read-before-write aliasing**: sources are read from the pre-instruction state before the destination update (PTX-AND-SEM2-060); verified by the aliasing example (d == a: r1 becomes 5 & 3 = 1) and self-aliasing example (5 & 5 = 5).
- **No forbidden constructs**: no `sorry`, `admit`, new `axiom`, or `unsafe`; the only proof terms are genuine `by decide` computations (0 < 2^32) and `Nat.mod_lt`; the only import is the trivial `Spec2Lean.Basic` (`def hello := "world"`), so no other-unit semantics are imported.
- **Compilation and examples**: `lake env lean` reports 0 errors, 0 warnings; all 17 `#eval` examples evaluate to the documented expected values (see Section 3).

The mapping introduces no unapproved new preconditions, invents no error/undefined behavior, and does not weaken or overstate anything (no theorem statements exist yet, so there are no vacuous or overstated theorems at this stage).

## 3. Inputs reviewed and verification performed

- `candidates/ptx/9.3/units/and-b32/lean/AndB32-v1.lean` — complete read (505/505 lines).
- `candidates/ptx/9.3/units/and-b32/semantics/semantics-v2.json` — complete read (389/389 lines); all 74 claims and claim classifications reviewed.
- `candidates/ptx/9.3/units/and-b32/source-bundles/source-bundle-v2.json` — complete read (394 lines); evidence fragments checked against the Lean traceability citations.
- `candidates/ptx/9.3/units/and-b32/architecture/foundation-v1.md` — complete read (275 lines); design choices D-1..D-33 checked.
- `candidates/ptx/9.3/units/and-b32/reviews/semantics-critic-v1.md` and `architecture-critic-v1.md` — complete reads (context).
- `runs/ptx-9.3-and.b32-d33dfec2/run.json` — complete read (253 lines).
- `reviews/ptx-and-b32/gate-b/ptx-and-b32-b-approval-v1.json` — read; decision approved, references the same semantics SHA-256.
- `lean/Spec2Lean/Basic.lean` — read; trivial module, no semantics imported.
- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` — verified via restricted specification tools:
  - anchor `logic-and-shift-instructions-and` (line 14256), lines 14252-14290 — section 9.7.8.1: syntax `and.type d, a, b;` (14264), type set (14266), description (14270), Semantics `d = a & b;` (14273), Notes (14277-14278), PTX ISA Note (14280), Target ISA Note (14282), examples `and.b32 x,q,r;` (14285) and `and.b32 sign,fpvalue,0x80000000;` (14286) — all verbatim as used by the semantics and the Lean header.
  - anchor `instructions` (line 8718), lines 8716-8724 — CTX-07 (9.7 intro): "All PTX instructions may be predicated. In the following descriptions, the optional guard predicate is omitted from the syntax." verified.
  - anchor `control-flow-instructions-at` (line 21826), lines 21824-21856 — CTX-08 (9.7.13.2): Description "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing." (21838-21839), Semantics "If {!}p then instruction" (21841), examples `@!p div.f32 ratio,x,y` and `@q bra L23;` (21849/21851) verified.
  - anchor `predicated-execution` (line 7537), lines 7535-7557 — CTX-02 (9.3): predicate registers virtual/`.pred`, `.reg .pred p, q, r;`, optional guard predicate, `@{!}p` prefix, "Instructions without a guard predicate are executed unconditionally." verified.
  - anchor `fundamental-types` (line 3015), lines 3013-3065 — CTX-04 (5.2.1): fundamental type = basic type + size; Table 8 lists `.b32` under "Bits (untyped)" (3053-3054) and `.pred` under "Predicate" (3057-3058); compatibility sentences (3064-3066) verified.
  - anchor `register-state-space` (line 2613), lines 2611-2635 — CTX-03 (5.1.1): registers typed/untyped; scalar registers 8/16/32/64/128-bit; predicate registers 1-bit; registers not fully addressable verified.
- Lean tool verification:
  - `lean_check_file` on `candidates/ptx/9.3/units/and-b32/lean/AndB32-v1.lean`: success, exitCode 0, errorCount 0, warningCount 0.
  - `lean_run_eval` on the same file: 17 outputs, each matching the documented expected value in order:
    1. `0` (0 & 0)
    2. `4294967295` (0xFFFFFFFF & 0xFFFFFFFF)
    3. `0` (0xFFFFFFFF & 0)
    4. `1` (5 & 3)
    5. `16711680` (0xFFFF0000 & 0x00FF00FF = 0x00FF0000)
    6. `some 2147483648` (official example shape: 0xFFFFFFFF & 0x80000000)
    7. `some 16711680` (register-source example: q = 0xFFFF0000, r = 0x00FF00FF)
    8. `some true` (unguarded guard = true)
    9. `some true` (@!p with p = false)
    10. `some 100` (destination update writes only destination)
    11. `some 1` (bit bucket: no value register written)
    12. `some 5` (@p with p = false: state unchanged, r1 stays 5)
    13. `some 1` (@!p with p = false: executes, 5 & 3 = 1)
    14. `some 1` (immediate source b: 5 & 3 = 1)
    15. `some 1` (aliasing d == a: read-before-write, 5 & 3 = 1)
    16. `some 5` (self-aliasing: 5 & 5 = 5)
    17. `"partial-none"` (missing source register: partial execution, no invented error)
  - grep for `sorry|admit|axiom|unsafe` under `candidates/ptx/9.3/units/and-b32/lean/`: no matches.

## 4. Findings table

| ID | Severity | Location | Summary |
|----|----------|----------|---------|
| F-1 | NOTE | AndB32-v1.lean, `execAndB32` (lines 323-333), header note (lines 312-313) | Guard-false branch returns `guardFalse` without reading source operands. The approved semantics (PTX-AND-SEM2-063) specifies the guard-false consequence as "no state component changes"; it does not explicitly state whether sources are read. The Lean choice — no source reads, so a missing source with a false guard still yields `guardFalse` rather than `none` — is the natural reading of "Threads with a False guard predicate do nothing." (CTX-08) and is documented in the header. No drift; mapping decision only |
| F-2 | NOTE | AndB32-v1.lean, `MachineState.predRegs` (line 213); comment (lines 127-132) | Predicate values are encoded as `Bool` (two-valued). The exact Lean encoding of the 1-bit predicate register value domain is explicitly deferred to the Lean-mapping phase (OQ-5, PTX-AND-SEM2-065; architecture D-13, A-7). `Bool` is the expected two-valued encoding and is documented; Gate C reviewers should confirm it as the approved encoding |
| F-3 | NOTE | AndB32-v1.lean, `Destination.bitBucket` (line 176), `updateDestination` (line 295), header (lines 55-60) | The bit bucket `_` is modeled as a candidate alternative destination (D-18) with no-write behavior, although scalar and.b32-specific bit-bucket applicability remains an open question (OQ-2, PTX-AND-SEM2-062). This is documented at "candidate strength" and mirrors the architecture's D-18 candidate design. Contrast with source-`a` immediate (F-3b): that open question is handled conservatively by omitting the constructor, whereas the bit bucket is included. Both treatments are documented and justified (bit bucket has a general 9.2 rule basis, SF-A13; source-`a` immediate has none) |
| F-4 | NOTE | AndB32-v1.lean, `andValue` (lines 275-278) | `Nat.land` modulo 2^32 is used to implement `d = a & b;`. For arguments in [0, 2^32) the bitwise-and is again in [0, 2^32), so the modulo is a no-op that keeps the `Fin` bound proof definitional. The representation of bitwise-and over the 32-bit bit-value domain is acknowledged as an open question for the theorem statement (OQ-8, PTX-AND-SEM2-068); the executable definition is the Lean mapping's concrete choice and is verified by the examples. The exact and-fidelity theorem statement (PRF-7) is deferred to the theorem-design stage as designed |
| F-5 | NOTE | AndB32-v1.lean, whole file (no theorem/proof sections) | The candidate contains no theorem statements and no proofs; PRF-1..PRF-7 are deferred to the theorem-design/proof stages, as documented in the header (lines 69-72) and in the run history. Since no theorems exist, the "Lean-checked proofs" input for a proof critique is absent by design at this stage; there are therefore no vacuous theorems, no weakened statements, and no theorem-name overstatements to check. This is expected and correct for the LEAN_FORMALIZATION output |
| F-6 | NOTE | AndB32-v1.lean, header (lines 1-78) | Header metadata verified accurate: declared semantics SHA-256 (`45e0fe93...24ca0e`) matches the Gate-B-approved artifact and the Gate B record; declared bundle SHA-256 (`57e86be0...27ea53`) matches source-bundle-v2.json; declared "17 executable examples" verified (17 `#eval` blocks); declared "0 errors, 0 warnings" verified by `lean_check_file`; declared "no sorry/admit/axioms/unsafe" verified by grep. The only inaccuracy class observed in prior stages (off-by-one line counts) is absent here |

## 5. Findings detail

### F-1 — NOTE — Guard-false branch does not read source operands

- **Exact location:** AndB32-v1.lean, `execAndB32` lines 323-333 (`| some false => some (ExecOutcome.guardFalse s)`); header comment lines 307-321 ("Source operands are NOT read in this branch.").
- **Relevant official evidence:** CTX-08 (section 9.7.13.2, HTML 21838-21839): "Execute an instruction or instruction block for threads that have the guard predicate True. Threads with a False guard predicate do nothing."; approved semantics claim PTX-AND-SEM2-063 (guard-false → "no state component changes") and PTX-AND-SEM2-074 (derivation chain).
- **Description:** When the complete guard expression evaluates false, the Lean function returns `ExecOutcome.guardFalse s` (the unchanged state) without reading `a` or `b`. The approved semantics specifies the state consequence (no change) but does not explicitly state whether source reads occur in the false-guard branch. The Lean choice is the natural reading of "do nothing" and has the observable consequence that a missing source register in a false-guard instruction still yields `guardFalse` rather than `none` (partial). This is a mapping decision consistent with the approved semantics; no semantic drift.
- **Consequence:** None for faithfulness; the behavior is the most conservative reading of the official "do nothing" clause. Gate C reviewers may wish to note it as an explicit modeling decision.
- **Required owner:** Lean Formalizer (informational; no revision required).
- **Required revision:** None.
- **Human review required:** No.

### F-2 — NOTE — Predicate value domain encoded as Bool

- **Exact location:** AndB32-v1.lean, `MachineState` line 213 (`predRegs : PredId -> Option Bool`); comment lines 127-132.
- **Relevant official evidence:** CTX-03 (section 5.1.1, HTML 2622-2624: predicate registers are 1-bit); approved semantics open question PTX-AND-SEM2-065 (OQ-5: exact Lean encoding of the 1-bit predicate value domain is a Lean-mapping decision); architecture D-13/A-7 (two-valued boolean-like domain by design).
- **Description:** The 1-bit predicate domain is encoded as `Bool` (two values). This is exactly the kind of Lean-mapping decision OQ-5 defers to this phase. The encoding is consistent with the architecture's two-valued design and with the boolean-style use of predicates in `setp` examples.
- **Consequence:** None; expected mapping decision. Gate C confirmation of the `Bool` encoding is part of the gate's purpose.
- **Required owner:** Lean Formalizer (informational).
- **Required revision:** None.
- **Human review required:** No (subject to the ordinary Gate C review).

### F-3 — NOTE — Bit-bucket destination modeled at candidate strength

- **Exact location:** AndB32-v1.lean, `Destination` line 176 (`| bitBucket : Destination`), `updateDestination` line 295 (`| Destination.bitBucket => s`), header lines 55-60.
- **Relevant official evidence:** General section 9.2 bit-bucket rule recorded in the architecture (SF-A13; section 9.2 not in the bundle); approved semantics open question PTX-AND-SEM2-062 (OQ-2); architecture D-18 ("the bit bucket `_` ... as a candidate alternative ... applicability to `and` is an open question, OQ-2").
- **Description:** The Lean includes the bit-bucket destination with no-write behavior, documented as a candidate alternative at the strength of the general 9.2 rule. The approved semantics retains scalar and.b32-specific bit-bucket applicability as an open question; the Lean does not present the bit bucket as a confirmed source fact. This mirrors the architecture's D-18 candidate design. The treatment is asymmetric with source-`a` immediate (open question 061), which is handled by omitting the constructor entirely; the asymmetry is defensible because the bit bucket has a general rule basis while source-`a` immediate has none, and both are documented.
- **Consequence:** A user of the Lean API can construct a bit-bucket instruction even though scalar and.b32 applicability is an open question; the mapping does not claim more than the architecture's candidate design. Non-blocking.
- **Required owner:** Lean Formalizer (informational).
- **Required revision:** None.
- **Human review required:** No (subject to the ordinary Gate C review).

### F-4 — NOTE — Bitwise-and represented with Nat.land modulo 2^32

- **Exact location:** AndB32-v1.lean, `andValue` lines 275-278.
- **Relevant official evidence:** AND_SEMANTICS (`d = a & b;`, HTML 14273); approved semantics claims PTX-AND-SEM2-008 (SOURCE_FACT) and PTX-AND-SEM2-032 (DERIVED bitwise-and semantics); open question PTX-AND-SEM2-068 (OQ-8: exact Lean statement of and-fidelity obligation PRF-7, including representation of bitwise-and over the 32-bit domain).
- **Description:** `andValue` computes `Nat.land` of the two `Fin` values' underlying naturals, reduced modulo 2^32. For in-domain arguments the reduction is a no-op (bitwise-and of two 32-bit values stays in [0, 2^32)); the `Fin` bound proof is definitional. The examples confirm the expected arithmetic (5 & 3 = 1, 0xFFFF0000 & 0x00FF00FF = 0x00FF0000 = 16711680, official example 0xFFFFFFFF & 0x80000000 = 2147483648). The formal and-fidelity statement (per-bit characterization) remains a theorem-stage matter as designed.
- **Consequence:** None; the executable semantics is correct for the bounded 32-bit domain, and the theorem statement is deferred as approved.
- **Required owner:** Lean Formalizer (informational).
- **Required revision:** None.
- **Human review required:** No.

### F-5 — NOTE — No theorem statements or proofs in the candidate

- **Exact location:** AndB32-v1.lean, whole file; header lines 69-72; run.json LEAN_FORMALIZATION record.
- **Relevant approved artifacts:** Architecture D-25/D-26 and Section 10 (PRF-1..PRF-7 candidate families); semantics-v2 `future_theorem_obligation_topics` (PRF-1..PRF-7); run.json stage flow (theorem design occurs after Gate C / theorem-strength gate).
- **Description:** The LEAN_FORMALIZATION output intentionally contains no theorem statements or proofs; PRF obligations are deferred to the theorem-design and proof stages. Because no theorems exist, there are no vacuous theorems, no weakened statements, no overstated theorem names, and no proof-strength issues to check at this stage. The relational `AndB32Step` was included so that future determinism/frame obligations are non-vacuous (D-25).
- **Consequence:** The mapping stage is complete; theorem/proof verification belongs to later stages. This is reported explicitly as the "Lean-checked proofs" input does not exist yet.
- **Required owner:** Proof Engineer (future stages).
- **Required revision:** None.
- **Human review required:** No.

### F-6 — NOTE — Header metadata verified accurate

- **Exact location:** AndB32-v1.lean, header lines 1-78.
- **Relevant artifacts:** semantics-v2.json SHA-256, source-bundle-v2.json SHA-256, Gate B record, run.json.
- **Description:** The header's declared semantics SHA-256 (`45e0fe93f02a3261976962026eb7b5b2e1a5343c10d4a388f500f6f30a24ca0e`), bundle SHA-256 (`57e86be0f823fa70e7559ca21cba30bf7f4b434a87c33cb39b134ce13f27ea53`), Gate A/B record paths, example count (17), compile status (0 errors, 0 warnings), and forbidden-construct claim were all independently verified and found accurate.
- **Consequence:** None; metadata hygiene is good.
- **Required owner:** None.
- **Required revision:** None.
- **Human review required:** No.

## 6. Traceability verification

Every Lean declaration carries a comment citing approved semantic claim IDs and/or architecture design choices. The critic independently confirmed that:

- The cited semantic claim IDs exist in `semantics-v2.json` and their classifications match the claims' meaning: `b32Bits`/`b32DomainSize` (013/015/026/056), `B32` (013/018/056, D-11), `RegId` (015/022, D-12), `PredId` (043, D-13), `SourceA` (023/025/061), `SourceB` (023/024), `Destination` (022/062, D-18), `Guard` (029/030/035/043, D-19/D-21), `AndTypeSpecifier` (003/004/005/028), `MachineState` (054, D-5/D-14), `AndB32Instruction` (006/021/055, D-1/D-16), `evalSourceA`/`evalSourceB` (034), `evalGuard` (029/030/035, D-19), `andValue` (008/032/068), `updateDestination` (036/037/062), `ExecOutcome` (058, D-8), `execAndB32` (032/033/034/036/048/049/050/060/063), `AndB32Step` (057, D-25).
- The cited architecture design choices (D-1, D-5, D-8, D-11, D-12, D-13, D-14, D-16, D-18, D-19, D-21, D-25, SF-A13, D-0c) exist in `foundation-v1.md`.
- The import graph is minimal: the file imports only `Spec2Lean.Basic`, which is a trivial module (`def hello := "world"`) containing no semantics; no `AddU32`/`MovB32`/`XorB32`/`NotB32` or other-unit semantics are imported. The accepted units' patterns were not used as semantic authority.
- The official examples `and.b32 x,q,r;` (register sources) and `and.b32 sign,fpvalue,0x80000000;` (immediate in position b) are represented and exercised by the examples; the source evidence at HTML 14285-14286 was re-verified.

## 7. Required revisions (consolidated)

No substantive Lean mapping revision is required before Gate C. All findings are NOTE-level transparency items, and the mapping is faithful to the human-approved Gate B semantics.

Optional refinements (recommended, not blocking):
1. Confirm at Gate C the `Bool` predicate encoding (OQ-5 / PTX-AND-SEM2-065) as the approved Lean encoding (F-2).
2. Confirm at Gate C the candidate-strength bit-bucket destination modeling (OQ-2 / PTX-AND-SEM2-062) as an acceptable modeled alternative (F-3).
3. Note at Gate C that the guard-false branch performs no source reads by design (F-1).

## 8. Residual open questions

- Whether the human Gate C reviewer confirms the `Bool` encoding of the 1-bit predicate value domain (OQ-5, PTX-AND-SEM2-065).
- Whether the human Gate C reviewer confirms the bit-bucket destination candidate (OQ-2, PTX-AND-SEM2-062) as modeled, given that scalar and.b32-specific applicability remains an open question.
- Whether source operand `a` may be a constant immediate (OQ-1, PTX-AND-SEM2-061) — retained open; the Lean conservatively omits the immediate constructor for `a`.
- The exact formal statement of the and-fidelity obligation (PRF-7) and the determinism/frame obligations (PRF-1..PRF-6) are theorem-design-stage matters (OQ-8, PTX-AND-SEM2-068); the relational `AndB32Step` is in place so those obligations will be non-vacuous.

## 9. Gate C readiness assessment

Ready for presentation to Human Gate C. The Lean mapping `AndB32-v1.lean` is a faithful, complete, and traceable Lean encoding of the human-approved Gate B semantic interpretation `semantics-v2.json` for the bounded `and.b32` unit. The mapping is Lean-checked (0 errors, 0 warnings), all 17 executable examples evaluate to the expected values, no `sorry`/`admit`/new axioms/`unsafe` are present, the value domain is the correct untyped 32-bit domain, operand order and roles are correct, the bitwise-and rule `d = a & b;` is implemented faithfully, the guard/predication model (unguarded/`@p`/`@!p`) and the source-resolved guard-false no-op are correctly represented, state reads/writes are minimal and faithful, no error/UB behavior is invented, and traceability to the approved semantics is complete. The findings in this critique (F-1..F-6) are all NOTE-level transparency items. This assessment is not a Gate C approval; approval is a human decision.

## 10. Critic independence statement

The critic did not edit, replace, or repair the reviewed artifact `candidates/ptx/9.3/units/and-b32/lean/AndB32-v1.lean` or any other artifact. No Lean code was written, and no gate was approved. Nothing was promoted to `accepted/`.
