# Independent Theorem-Strength Review: PTX ISA 9.3 `add.u32` — Theorem-Obligation Set v1

- Review ID: `ptx-add-u32-obligations-v1-strength-critic`
- Reviewer role: Semantic Critic (independent)
- Review date: 2026-08-07
- Unit: PTX ISA 9.3 `add.u32` (base scalar, non-saturating, unsigned 32-bit add)
- Artifact under review: `candidates/ptx/9.3/theorems/add-u32-obligations-v1.json`
- Review type: independent theorem-strength review (pre-proof-generation)
- Overall conclusion: **READY_FOR_PROOF_REVIEW.** The six theorem obligations are
  semantically faithful, non-vacuous, non-circular, properly scoped, and
  realistically provable from the Gate-C-approved Lean mapping without changing
  semantics. 0 BLOCKERs, 0 MAJORs, 1 MINOR, 3 NOTEs. No reviewed artifact was
  modified.

---

## 1. Status

- Status: COMPLETE
- Verdict: **READY_FOR_PROOF_REVIEW**
- This verdict means the theorem set is suitable for human strength approval and
  subsequent Proof Engineer execution. It does not mean the theorems are proved,
  and it is not a Gate C/D approval.
- The theorem statements in the obligation set are Lean sketches, not compiled
  Lean (risk R-6); that is expected at this stage and does not block strength
  review.
- No artifact was edited, repaired, weakened, or rewritten by this critic.

---

## 2. Overall verdict

**READY_FOR_PROOF_REVIEW**

The obligation set proposes six theorems that together cover the required
areas (modulo-2^32 result conformance, false-guard state preservation,
predicate-register preservation, unrelated-value-register frame,
destination-only update, bit-bucket state preservation, totality on the
well-formed lookup domain, and read-before-write aliasing) without any
unsupported strengthening:

- THM-001 correctly characterizes the approved well-formed lookup domain and
  never demands source lookups when the guard is false.
- THM-002 pins the written destination value to source values read from the
  pre-instruction state, which genuinely establishes read-before-write
  aliasing; the modulo-2^32 equality carries the human-assumption traceability
  and is never presented as an NVIDIA source fact.
- THM-003 states the strongest precise guard-false property: the outcome is
  exactly `some (ExecOutcome.guardFalse s)`, i.e., the carried state equals the
  input state.
- THM-004 is strictly a bounded-`MachineState` frame theorem (value-register
  file and predicate-register file only); it makes no carry/status claim and
  retains the negative-evidence caveat.
- THM-005 states the bit-bucket discard at the strength of the general section
  9.2 rule plus the approved minimal-state semantics, with the AMB-1 caveat
  retained; it is not presented as add-specific NVIDIA behavior.
- THM-006's biconditional is logically correct in both directions; the
  proof-strategy hint's direction labels are inverted relative to the written
  iff orientation but both directions are actually proved (cosmetic only).
- All six theorems are provable by unfolding the existing
  `execAddU32`/`updateDestination`/`evalGuard`/`evalSource` definitions without
  changing `AddU32.lean`.
- Validation obligations are appropriately static checks, and the
  result-domain-membership topic (PRF-6) is correctly subsumed by the
  `Fin (2^32)` representation. Deferred properties are correctly deferred:
  functional determinism would be vacuous, whole-PTX frame claims require a
  broader model, and absent-evidence claims are not promoted to theorems.

One MINOR recommendation (F-1): add an explicit aliasing corollary to THM-002 so
the read-before-write property is a first-class, directly traceable statement
tied to the official example `add.u32 %r, %r, 4` (PTX-9.3-ADD-025). The
corollary is a direct consequence of THM-002 and does not require any change to
the approved semantics or to `AddU32.lean`.

---

## 3. Inputs reviewed

| # | Artifact | Role | Read |
|---|---|---|---|
| 1 | `candidates/ptx/9.3/theorems/add-u32-obligations-v1.json` | artifact under review (6 theorems, 6 validations, 8 deferred) | complete |
| 2 | `reviews/ptx-add-u32/gate-c/ptx-add-u32-gate-c-v1.json` | Gate C record (approved; human confirmation recorded) | complete |
| 3 | `reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json` | human-approved modulo-2^32 assumption (approved) | complete |
| 4 | `candidates/ptx/9.3/semantics/add-u32-v2.json` | Gate-B-approved semantic interpretation | complete |
| 5 | `candidates/ptx/9.3/lean/AddU32.lean` | Gate-C-approved Lean mapping | complete |
| 6 | `candidates/ptx/9.3/reviews/add-u32-lean-mapping-v1-critic.md` | pre-Gate-C Lean mapping critique | complete |
| 7 | `candidates/ptx/9.3/reviews/add-u32-semantics-v2-critic.md` | pre-Gate-B semantic critique (negative-evidence caveat SEM2-CRIT-F1) | complete |
| 8 | `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html` (whitelisted official HTML) | load-bearing source evidence, independently re-verified via `spec_get_context` / `spec_search` | targeted |

Independent evidence verification performed with the restricted specification
tools:

- add section anchor `integer-arithmetic-instructions-add` (lines 8757-8827):
  "Add two values."; "Performs addition and writes the resulting value into a
  destination register."; Syntax `add.type1 d, a, b;` /
  `add{.sat}.type2 d, a, b;` with `.u32` in `.type2`; Semantics else branch
  `d = a + b;` (lines 8807-8809). ✓
- predication clause anchor `control-flow-instructions-at` (lines 21826-21841):
  "Threads with a False guard predicate do nothing." with Semantics
  "If {!}p then instruction". ✓ (confirms BLOCK-2 source support)
- bit-bucket rule (line 7534): "For some instructions the destination operand
  is optional. A bit bucket operand denoted with an underscore (_) may be used
  in place of a destination register." ✓
- universal predication (line 8722): "All PTX instructions may be predicated."
  ✓
- official aliasing example `add.u32 %r, %r, 4` (line 6172; fragment
  PTX-9.3-ADD-025): destination aliases source a. ✓

Independent Lean verification performed with `lean_check_file`
(`candidates/ptx/9.3/lean/AddU32.lean`): success, exit code 0, 0 errors,
0 warnings, not timed out; SHA-256
`4fa14a35f4d127b4df6cd10eb541bf6a4503042c6dc306290e4258f90c691b7b`.

---

## 4. Per-theorem strength table

| # | Obligation | Name accuracy | Hypotheses satisfiable | Hypotheses exactly strong enough | Unapproved precondition? | Conclusion in hypotheses? | Conclusion too weak? | Conclusion too strong? | Vacuous? | Lean sketch matches English? | Duplicates? | Provable without changing semantics? | Strength verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| THM-001 | `execAddU32_total_on_well_formed_lookup_domain` | YES | YES | YES | NO | NO | NO | NO | NO | YES | NO | YES | ADEQUATE |
| THM-002 | `execAddU32_result_conforms_modulo_with_read_before_write` | YES | YES | YES | NO | NO | NO | NO | NO | YES | NO | YES | ADEQUATE (recommend explicit aliasing corollary) |
| THM-003 | `execAddU32_guard_false_preserves_state` | YES | YES | YES | NO | NO | NO | NO | NO | YES | NO | YES | ADEQUATE / STRONG |
| THM-004 | `execAddU32_destination_only_frame` | YES | YES | YES | NO | NO | NO | NO | NO | YES | NO | YES | ADEQUATE |
| THM-005 | `execAddU32_bit_bucket_preserves_state` | YES | YES | YES | NO | NO | NO | NO | NO | YES | NO | YES | ADEQUATE |
| THM-006 | `execAddU32_executes_iff_guard_true` | YES | YES | YES | NO | NO | NO | NO | NO | YES | NO | YES | ADEQUATE (hint labels cosmetic) |

Per-theorem detail:

### THM-001 — totality on the well-formed lookup domain
- Meaningful: establishes that `execAddU32` is total (never `none`) on the
  approved well-formed lookup domain: the complete guard expression resolves and
  the sources resolve whenever the guard is true. This is exactly the
  domain-quantification requirement of the mapping critic (LMAP-CRIT-F2 /
  risk R-2).
- Name accurate: "total on well-formed lookup domain" matches the claim.
- Hypothesis shape: `hguard : evalGuard s i.guard = some b` plus
  `hsources : b = true -> Exists va, Exists vb, evalSource s i.a = some va /\
  evalSource s i.b = some vb`. When `b = false`, `hsources` is vacuous — no
  source lookup is demanded. This exactly matches the code, where the
  `some false` branch returns `guardFalse` without evaluating sources. Special
  attention item 5 satisfied.
- No unapproved precondition: no value-level dynamic precondition is added
  (PTX-ADD-SEM2-038 is respected); the only preconditions are lookup-success
  conditions defining the well-formed domain.
- Conclusion `Exists o, execAddU32 s i = some o` is not an element of the
  hypotheses; it is the totality claim.
- Non-vacuous: satisfiable (e.g., unguarded `add.u32 %r, %r, 4` with `%r`
  defined); the conclusion does not hold for arbitrary states (missing source
  register yields `none`), so it is not built into the type.
- Provable without changing semantics: case analysis on `b`; for `b = false`
  unfold to `guardFalse`; for `b = true` split `hsources` and unfold to
  `executed`. ✓

### THM-002 — arithmetic result conformance with read-before-write
- Meaningful: pins the exact value written to the destination register as
  `addU32 va vb` where `va`, `vb` are the source values read from the
  pre-instruction state `s`.
- Read-before-write aliasing (special attention item 1): the theorem DOES prove
  read-before-write aliasing, not merely hint at it. The hypotheses
  `ha : evalSource s i.a = some va` and `hb : evalSource s i.b = some vb` are
  stated over the pre-state `s`, and the conclusion
  `s'.valueRegs r = some (addU32 va vb)` is a function of those pre-state
  reads. When the destination aliases a source (e.g., `i.a = SourceOperand.reg
  r`), `va` unfolds to `s.valueRegs r`, the pre-update value, and the write is
  computed from it. This excludes any read-after-write semantics: if the
  sources were read after the destination update, the written value for an
  aliased operand would differ from `addU32` applied to the pre-state values.
  An explicit aliasing corollary is recommended but not required for semantic
  faithfulness (see F-1): it would make the aliasing property first-class and
  directly traceable to the official example PTX-9.3-ADD-025.
- Modulo attribution (special attention item 6): the modulo-2^32 equality
  appears only here among the six theorems, via `addU32`. The obligation
  declares `human_assumption_dependencies: ["PTX-ADD-SEM2-015 ..."]`, and both
  the precise statement and the strength risks state that the modulo rule is
  NOT an NVIDIA source fact and is never attributed to NVIDIA. ✓
- Hypotheses: `hguard = some true` (execution), `hd : i.d = Destination.reg r`
  (register destination), `ha`, `hb` (pre-state source reads). All needed; no
  unapproved precondition.
- Conclusion not too weak (it pins the exact written value) and not too strong
  (it is exactly what `execAddU32` computes; frame properties are left to
  THM-004).
- Provable without changing semantics: unfold `execAddU32`, `updateDestination`
  with `hd`; result follows from the `if r' == r` update. ✓

### THM-003 — guard-false state preservation
- Meaningful and strong: the conclusion
  `execAddU32 s i = some (ExecOutcome.guardFalse s)` pins both the outcome
  constructor and the carried state to exactly the input state `s`. Since
  `ExecOutcome.guardFalse` carries a `MachineState` and the only producer in
  `execAddU32` is `some (ExecOutcome.guardFalse s)`, this is the strongest
  precise statement of "thread does nothing" for the modeled state pair.
- Special attention item 3: exact `guardFalse s` is the right strong statement;
  it is stronger than merely asserting "some guard-false outcome exists" and is
  exactly what the approved semantics (PTX-ADD-SEM2-024/031) and the official
  predication clause (section 9.7.13.2) require.
- Hypotheses: only `hguard : evalGuard s i.guard = some false`; no source
  hypotheses are required because the guard-false branch does not read sources.
  This is correct and is part of the conclusion's semantic content, not an
  unapproved precondition.
- Source attribution: correctly presented as a DERIVED_INTERPRETATION from the
  explicit predication clause (BLOCK-2 resolved by official evidence, not a
  human assumption). ✓
- Provable without changing semantics: unfold `execAddU32`; the `some false`
  branch returns `some (ExecOutcome.guardFalse s)` directly. ✓
- NOTE (F-3): the English description "The theorem also entails that source
  operands are not read in this branch" over-describes the formal statement;
  the theorem does not formalize "not read" — it proves the outcome equality,
  and the absence of source reads is an implementation-level consequence of the
  code structure. The formal statement is correct; only the prose is
  imprecise.

### THM-004 — destination-only frame
- Meaningful: destination-only update / frame over the bounded `MachineState`.
- Special attention item 3: the conclusion quantifies only over
  `RegId`/`PredId` within the model: `forall r', r' != r -> s'.valueRegs r' =
  s.valueRegs r'` and `forall p, s'.predRegs p = s.predRegs p`. It makes no
  claim about carry flags, status registers, or condition codes, and the
  negative-evidence caveat (SEM2-CRIT-F1 / LMAP-CRIT-F1 / risk R-1) is retained
  in `strength_risks`. The theorem never turns the absence-based inference into
  an affirmative NVIDIA claim.
- Hypotheses: same well-formed-execution shape as THM-002 (guard true, register
  destination, sources resolve); all needed to reach the executed branch.
- Separation of duties is correct: THM-002 proves the written value; THM-004
  proves everything else is preserved; the destination register is allowed to
  change. No attempt to strengthen this theorem into a claim about components
  outside the model.
- Provable without changing semantics: unfold `updateDestination`; the value
  file update is `if r' == r then some result else s.valueRegs r'`; use
  `by_cases (r' == r)` with the derived `DecidableEq` on `RegId`; predicate
  file untouched by record update. ✓

### THM-005 — bit-bucket state preservation
- Meaningful: the bit-bucket destination discards the result and leaves the
  whole modeled state unchanged (`s' = s`).
- Special attention item 4: the theorem is justified to the strength of the
  general section 9.2 bit-bucket rule (PTX-ADD-SEM2-047 SOURCE_FACT, SEM2-030
  DERIVED_INTERPRETATION, SEM2-054 OPEN_QUESTION / AMB-1). The Lean conclusion
  `s' = s` is exactly what the approved `updateDestination bitBucket => s`
  computes, and the obligation retains the R-4 caveat: it is not presented as
  add-specific explicit NVIDIA behavior. The whole-state equality `s' = s`
  includes predicate preservation, which is within the approved minimal-state
  semantics (SEM2-049) and the destination-only write design; it is not an
  NVIDIA-affirmative claim beyond the general rule.
- Hypotheses: `hguard = some true`, `hd : i.d = Destination.bitBucket`, `ha`,
  `hb` (sources resolve). All needed: in the executed branch the sources are
  evaluated before `updateDestination` is applied, so `ha`/`hb` are required to
  reach the executed outcome.
- Provable without changing semantics: unfold `execAddU32`; with `hd`, unfold
  `updateDestination`; the bit-bucket branch returns `s`. ✓

### THM-006 — executes iff guard true
- Special attention item 2: independent logical analysis of the biconditional:
  - LHS → RHS (`exists executed` → `b = true`): assume
    `execAddU32 s i = some (ExecOutcome.executed s')`. The `evalGuard` match
    cannot have taken the `none` branch (returns `none`) nor the `some false`
    branch (returns `guardFalse`, not `executed`); hence it took the
    `some true` branch, so `evalGuard s i.guard = some true`. With
    `hguard : evalGuard s i.guard = some b`, injectivity of `some` gives
    `b = true`. This direction does not use `hsources`. Correct.
  - RHS → LHS (`b = true` → exists executed): assume `b = true`; `hsources`
    splits into `va`, `vb`; `hguard` gives `evalGuard s i.guard = some true`;
    `execAddU32` returns
    `some (ExecOutcome.executed (updateDestination s i.d (addU32 va vb)))`. 
    Correct.
  - Hypothesis shape is exactly the well-formed domain: `hsources` is guarded
    by `b = true`; adding source-resolution hypotheses unconditionally would be
    an unapproved strengthening, and the obligation correctly warns against it.
  - The theorem statement itself is logically sound. The proof-strategy hint's
    direction labels are inverted relative to the written iff orientation
    (`(Exists executed) <-> b = true`: the hint calls the `b = true -> executed`
    direction "Forward" and the `executed -> b = true` direction "Reverse",
    whereas the conventional left-to-right "forward" is
    `executed -> b = true`). Both directions are actually proved, so this is a
    cosmetic labeling issue only (F-2).
- Non-vacuous: satisfiable for both `b = true` and `b = false` (`@p` with
  `p = true` and `p = false`); both directions of the biconditional are
  genuinely exercised.
- Not a determinism claim (PRF-1) and not a duplicate of THM-001/THM-003:
  THM-001 is totality (some outcome exists), THM-003 pins the guard-false
  outcome value, THM-006 is the outcome-classification iff. Complementary.
- Provable without changing semantics: unfold `execAddU32`, case analysis on
  `b` and the `evalGuard` match, injectivity of `some`. ✓

---

## 5. Findings

| Finding ID | Severity | Affected artifact | Exact location | Evidence references | Description | Consequence | Required owner | Human review required |
|---|---|---|---|---|---|---|---|---|
| OBLS-STR-F1 | MINOR | `candidates/ptx/9.3/theorems/add-u32-obligations-v1.json` | PTX-ADD-THM-002 (statement, `precise_statement_in_words`, `strength_risks`) | PTX-9.3-ADD-025 (`add.u32 %r, %r, 4`, d == a); PTX-ADD-SEM2-043; required-area table `read_before_write_aliasing` | THM-002 genuinely proves read-before-write aliasing: source values `va`/`vb` are read from the pre-instruction state `s`, and the written value `addU32 va vb` is a function of those pre-state reads; when the destination aliases a source, the pre-update value is used. However, the aliasing case is not stated as an explicit theorem or corollary; a reader must instantiate the general statement. An explicit aliasing corollary (e.g., `i.d = Destination.reg r`, `i.a = SourceOperand.reg r`, `s.valueRegs r = some va` implies the written value is `addU32 va vb` with `va` the pre-update value) would make the property first-class and directly traceable to the official example. | The theorem set is semantically faithful as-is, but the read-before-write claim is implicit rather than explicit. Recommended for clarity and traceability at human strength approval; a corollary is a direct consequence of THM-002 and requires no semantic or Lean change. | Proof Engineer / theorem-set author (proposed corollary); human strength review (accept recommendation) | No (recommendation for the human strength-approval material) |
| OBLS-STR-F2 | NOTE | `candidates/ptx/9.3/theorems/add-u32-obligations-v1.json` | PTX-ADD-THM-006 `proof_strategy_hint` | THM-006 statement and conclusion | The hint labels the `b = true -> executed exists` direction "Forward" and the `executed exists -> b = true` direction "Reverse". Relative to the written conclusion `(Exists s', executed s') <-> b = true`, the conventional forward direction is `executed -> b = true`. The labels are therefore inverted, but both directions are actually proved and the reasoning in the hint is correct. | Cosmetic labeling inconsistency in the proof-strategy hint only; no defect in the theorem statement or its provability. | Proof Engineer | No |
| OBLS-STR-F3 | NOTE | `candidates/ptx/9.3/theorems/add-u32-obligations-v1.json` | PTX-ADD-THM-003 `precise_statement_in_words` | THM-003 statement; `execAddU32` `some false` branch | The English claims the theorem "also entails that source operands are not read in this branch (the code returns before evaluating sources)". The formal theorem proves the outcome equality `execAddU32 s i = some (ExecOutcome.guardFalse s)`; the fact that sources are not read is an implementation-level consequence of the code structure, not a separate formal consequence of the theorem statement. The hypothesis shape (no source hypotheses) is exactly right and demonstrates source-independence. | Prose over-description only; the formal statement is correct and appropriately strong. | theorem-set author (wording precision) | No |
| OBLS-STR-F4 | NOTE | `candidates/ptx/9.3/theorems/add-u32-obligations-v1.json` | PTX-ADD-VAL-002; THM-002; PRF-6 mapping | PTX-ADD-SEM2-009/010/016; `U32`/`Fin`/`addU32` in `AddU32.lean` | Result-domain membership (PRF-6) is handled as a representation invariant: every `U32` wraps `Fin u32Modulus`, so any value written to a destination (always of type `U32`) lies in `[0, 2^32)` by construction. Keeping this as a validation obligation rather than a theorem is appropriate; a dedicated theorem would be a trivial restatement of the type. If the Proof Engineer wants an explicit PRF-6 artifact, a short lemma `s'.valueRegs r = some v -> v.toFin.val < 2^32` is derivable, but it is not needed for theorem strength. | Confirms that `Fin (2^32)` adequately handles result-domain membership; no change required. | Proof Engineer | No |

Severity counts: BLOCKER 0, MAJOR 0, MINOR 1, NOTE 3.

---

## 6. Validation-obligation assessment

- VAL-001 (bounded instruction representation): appropriate as a static
  definitional check; the single-constructor `AddTypeSpecifier` and the
  semantically inert `type` field are documented (LMAP-CRIT-F3). Not a theorem.
- VAL-002 (U32 domain by representation): appropriate as a representation
  invariant; subsumes PRF-6. See F-4. Not a theorem.
- VAL-003 (no `sorry`/`admit`/`axiom`/`unsafe`): appropriate static check;
  re-checkable at proof phase.
- VAL-004 (Lean candidate compiles): independently re-verified by this critic
  (`lean_check_file` success, 0 errors, 0 warnings). Appropriate; compilation
  is necessary but not sufficient for faithfulness.
- VAL-005 (operand order/forms): appropriate static definitional check.
- VAL-006 (MachineState minimal pair): appropriate static definitional check.
- No validation obligation is really a theorem in disguise; no proposed theorem
  should be demoted to validation. The division is sound.

---

## 7. Deferred-property assessment

- DEF-001 (determinism, PRF-1): correctly deferred. A functional
  single-valuedness statement over `execAddU32` would be vacuous (function
  application is deterministic by congruence). The relational semantics design
  (D-25, PTX-ADD-SEM2-052) is the right future home. Not expressible
  meaningfully now without changing the mapping.
- DEF-002 (whole-PTX frame beyond the minimal state): correctly deferred.
  Statements about carry/status/CC components are absence-based negative
  evidence (SEM2-CRIT-F1 / LMAP-CRIT-F1 / risk R-1), not affirmative NVIDIA
  enumeration; THM-004 is strictly bounded and retains the caveat. Not
  expressible meaningfully in the current `MachineState`.
- DEF-003 (add-specific bit-bucket demonstration, AMB-1): correctly deferred.
  THM-005 states the no-write consequence at general-rule strength; promoting
  it to an add-specific explicit claim requires official evidence, not a
  theorem.
- DEF-004 (immediate range/encoding, AMB-4): correctly deferred; static
  well-formedness, outside executable-semantics scope.
- DEF-005 (version/target gating): correctly deferred to the validation layer;
  not modeled in the executable mapping.
- DEF-006 (out-of-domain behavior, `none` = partiality): correctly deferred.
  A theorem "missing guard predicate or source register yields `none`" would be
  expressible now but would elevate the partiality convention to an approved
  semantic property; the approved semantics deliberately fixes behavior only
  for the well-formed domain (PTX-ADD-SEM2-044/045/046/050). The deferral is
  the right judgment call.
- DEF-007 (error/UB/impl-defined behavior): correctly deferred; no behavior
  invented from silence.
- DEF-008 (assumption-record SHA-256 publication): correctly deferred as a
  metadata closure item, not a theorem; must be closed before final acceptance
  (Gate D).
- No deferred property is already meaningfully expressible in a way that should
  be promoted to a theorem now.

---

## 8. Human-assumption attribution assessment

- The only human-approved assumption in scope is PTX-ADD-SEM2-015 (modulo-2^32
  result rule).
- THM-002 is the only theorem whose conclusion depends on the modulo rule
  (via `addU32`); it correctly declares
  `human_assumption_dependencies: ["PTX-ADD-SEM2-015 ..."]`, and both the
  precise statement and the strength risks state the rule is NOT an NVIDIA
  source fact and is never attributed to NVIDIA. ✓
- THM-001, THM-003, THM-004, THM-005, THM-006 declare no human-assumption
  dependency, and this is correct:
  - THM-003/THM-006 guard behavior is source-supported via the section 9.7.13.2
    predication clause (verified in HTML lines 21826-21841); BLOCK-2 is not
    treated as a human assumption. ✓
  - THM-005 bit-bucket behavior is grounded in the general section 9.2 rule
    (PTX-ADD-SEM2-047/030), not a human assumption. ✓
  - THM-004 frame behavior is grounded in the source write description plus the
    negative-evidence caveat, not a human assumption. ✓
- The traceability summary's statement "only PTX-ADD-THM-002 depends on it" is
  accurate.
- The known traceability gap (decision record's own SHA-256 not published,
  SEM2-058 / risk R-3) is disclosed and deferred correctly; it does not affect
  theorem strength.

---

## 9. Non-vacuity assessment

No theorem is vacuous:

- THM-001: satisfiable (unguarded `add.u32 %r, %r, 4` with `%r` defined);
  conclusion not true for arbitrary states (missing source yields `none`).
- THM-002: satisfiable (e.g., `%r = 5`, `add.u32 %r, %r, 7` → 12);
  conclusion is exact and distinguishes read-before-write from read-after-write.
- THM-003: satisfiable (`@p` with `p = false`); conclusion pins the exact
  outcome constructor and carried state.
- THM-004: satisfiable (`r1 = 1`, `r2 = 2`, update `r1` → `r2` preserved and
  predicate file untouched); conclusion is the frame content.
- THM-005: satisfiable (bit-bucket destination, sources resolve); conclusion
  `s' = s` is the discard content and distinguishes the bit-bucket from the
  register destination.
- THM-006: satisfiable for both `b = true` and `b = false`; both directions of
  the biconditional are exercised.

Each non-vacuity argument in the obligation set is accurate; none is circular
(no hypothesis contains its conclusion; the `#eval` examples cited are
demonstrations, not independent evidence).

---

## 10. Proof-readiness assessment

- `candidates/ptx/9.3/lean/AddU32.lean` compiles cleanly under
  `lake env lean` (independently re-run by this critic: success, 0 errors,
  0 warnings).
- All six theorem statements are provable by unfolding the existing
  definitions (`execAddU32`, `updateDestination`, `evalGuard`, `evalSource`,
  `addU32`) without changing `AddU32.lean`:
  - THM-001/THM-006: case analysis on `b` and the `evalGuard`/`evalSource`
    matches.
  - THM-002: unfold and the `if r' == r` update with `hd`.
  - THM-003: unfold; the `some false` branch returns `guardFalse s` directly.
  - THM-004: unfold; `by_cases (r' == r)` using the derived `DecidableEq` on
    `RegId`.
  - THM-005: unfold; `updateDestination bitBucket => s`.
- No theorem requires `sorry`, `admit`, new axioms, `unsafe`, or any
  modification of the approved semantics.
- The Lean sketches are realistic: they use only types and definitions already
  present (`MachineState`, `AddU32Instruction`, `evalGuard`, `evalSource`,
  `execAddU32`, `ExecOutcome`, `Destination`, `RegId`, `PredId`, `U32`,
  `u32Modulus`).
- The theorem statements are sketches, not compiled Lean (risk R-6); this is
  expected and is exactly what the Proof Engineer will compile next. No
  blocker.
- Recommended order of execution: THM-001 → THM-003 → THM-006 → THM-002 →
  THM-004 → THM-005, then the optional aliasing corollary (F-1) if approved.

---

## 11. Recommended theorem-set revisions (if any)

1. (Recommended, MINOR — F-1) Add an explicit aliasing corollary to THM-002:
   e.g., "if `evalGuard s i.guard = some true`, `i.d = Destination.reg r`,
   `i.a = SourceOperand.reg r`, `s.valueRegs r = some va`, and
   `evalSource s i.b = some vb`, then there exists `s'` with
   `execAddU32 s i = some (ExecOutcome.executed s')` and
   `s'.valueRegs r = some (addU32 va vb)`", making explicit that `va` is the
   pre-update value. This is a direct consequence of THM-002, requires no
   semantic or Lean change, and ties the required area
   `read_before_write_aliasing` directly to PTX-9.3-ADD-025.
2. (Cosmetic, NOTE — F-2) In THM-006's proof-strategy hint, relabel the
   directions to match the written iff orientation, or state explicitly that
   both directions are proved regardless of label.
3. (Cosmetic, NOTE — F-3) In THM-003's English, rephrase "the theorem also
   entails that source operands are not read in this branch" to "the theorem
   holds without any source-resolution hypothesis, showing the guard-false
   outcome is independent of source lookup".
4. (Optional, NOTE — F-4) No change required for VAL-002/PRF-6; a trivial
   domain-membership lemma may be added at proof time if an explicit PRF-6
   artifact is desired.

None of these revisions is required for semantic faithfulness; they are
clarity and traceability improvements to be considered at human strength
approval.

---

## 12. Critic independence statement

I, the Semantic Critic, performed this review independently. I read completely
the theorem-obligation set under review, the Gate C record, the human
overflow-assumption record, the Gate-B-approved semantic interpretation, the
Gate-C-approved Lean mapping, the pre-Gate-C Lean mapping critique, and the
pre-Gate-B semantic critique. I independently re-verified the load-bearing
official evidence against the whitelisted PTX ISA 9.3 HTML using the restricted
specification tools (add section, predication clause, bit-bucket rule,
universal predication, aliasing example), and I independently re-verified the
Lean candidate using the restricted Lean tooling (`lean_check_file`: success,
0 errors, 0 warnings). I did not use CUDA C, LLVM, another ISA, compiler
behavior, or model prior knowledge as evidence. I did not import ISO C
arithmetic semantics. I did not edit, repair, rewrite, weaken, or strengthen
any reviewed artifact, including the obligation set and `AddU32.lean`. I did
not write theorem statements into a Lean file and did not write proofs. I did
not approve Gate A, Gate B, Gate C, Gate D, or final acceptance. The only
artifact I created is this review.
