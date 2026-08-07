# Independent Pre-Gate-C Lean Mapping Critique: PTX ISA 9.3 `add.u32` — Lean Candidate

- Review ID: `ptx-add-u32-lean-mapping-v1-critic`
- Reviewer role: Semantic Critic (independent)
- Review date: 2026-08-07
- Unit: PTX ISA 9.3 `add.u32` (Lean candidate `candidates/ptx/9.3/lean/AddU32.lean`)
- Review type: independent pre-Gate-C Lean-mapping critique
- Overall conclusion: **READY_FOR_HUMAN_REVIEW.** The Lean candidate faithfully implements the Gate-B-approved bounded semantics within the well-formed-state domain. 0 BLOCKERs, 1 MINOR, 4 NOTEs. No reviewed artifact was modified.

---

## 1. Status

- Status: COMPLETE
- Verdict: **READY_FOR_HUMAN_REVIEW**
- Gate C is NOT approved by this critic. This verdict means only that Human Gate C may occur.
- No artifact was edited, repaired, weakened, or rewritten by this critic.

---

## 2. Overall verdict

**READY_FOR_HUMAN_REVIEW**

The Lean candidate `AddU32.lean` is a faithful Lean realization of the
Gate-B-approved semantic interpretation `add-u32-v2.json` for the domain of
well-formed states and well-typed instructions:

- The `.u32` value domain is realized exactly by `Fin (2^32)`.
- `addU32` implements exactly `(a + b) mod 2^32`, and the modulo rule is
  explicitly and repeatedly labeled as the human-approved project assumption
  (PTX-ADD-SEM2-015), never as an NVIDIA source fact.
- Operand order is `d, a, b`; sources are register-or-immediate; the
  destination is register-or-bit-bucket.
- The machine state is the minimal approved pair (value-register file,
  predicate-register file).
- Missing register/predicate lookups yield partial execution (`Option none`),
  not invented errors, traps, UB, or implementation-defined behavior.
- Guard semantics are exactly unguarded → true, `@p` → p, `@!p` → not p;
  a false complete guard returns the unchanged input state without evaluating
  source operands; a true guard reads both sources before the destination
  write (read-before-write for aliasing).
- `updateDestination` changes only the destination register (or nothing for
  the bit bucket) and preserves all unrelated value registers and all
  predicate registers by construction.
- Traceability comments cite only real semantic claim IDs, and the cited
  claims match the code's behavior.
- No `sorry`, `admit`, `axiom`, or `unsafe` occurs.
- Independent Lean tooling confirms successful compilation (0 errors,
  0 warnings) and correct executable-example output.

One MINOR finding (F-1) concerns comment-level precision on the
destination-only/no-carry negative evidence (the known semantic-critic MINOR
SEM2-CRIT-F1). It does not change code behavior and does not block Gate C
readiness; it must remain traceable and be addressed before final acceptance.

---

## 3. Inputs and hashes

| # | Artifact | Role | SHA-256 | Hash source |
|---|---|---|---|---|
| 1 | `reviews/ptx-add-u32/gate-b/ptx-add-u32-gate-b-v2.json` | Gate B decision (approved) | not published in record | Gate B record does not publish its own hash; read directly |
| 2 | `reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json` | human-approved overflow assumption (approved) | not published (SEM2-058) | record does not publish its own hash; read directly |
| 3 | `candidates/ptx/9.3/architecture/add-u32-foundation-v2.md` | approved language architecture (Gate A) | `3857b9cb512cc77981365228b454f34153d2ccd5308ac5499194b30ec003e9d7` | Gate A record / semantics `architecture_reference` |
| 4 | `candidates/ptx/9.3/semantics/add-u32-v2.json` | Gate-B-approved semantic interpretation | `76499344dc8767c7acca596a8b8bcb8aad671779b581e74bf94d57dd52f9bbb6` | Gate B record artifacts list |
| 5 | `candidates/ptx/9.3/reviews/add-u32-semantics-v2-critic.md` | pre-Gate-B semantic critique | `b43a44473ae4964e3b1fc159eda1dec17f8b73dec9054b12f4929ba6c18dc009` | Gate B record artifacts list |
| 6 | `candidates/ptx/9.3/source-bundles/add-u32-v1.json` | primary official-source bundle | `c137078da5e8e0a475a090ae16409cd89d6ee7b93911f0b78a9a36f94d2a4924` | Gate B record artifacts list |
| 7 | `candidates/ptx/9.3/source-bundles/add-u32-blockers-supplement-v2.json` | supplementary official-source evidence | `a74ab1167e4a20d5aa37360713aec8a28ee219763c93f28e3a47c57ae81c1fec` | Gate B record artifacts list |
| 8 | `candidates/ptx/9.3/lean/AddU32.lean` | Lean mapping candidate (review subject) | `4fa14a35f4d127b4df6cd10eb541bf6a4503042c6dc306290e4258f90c691b7b` | computed by `lean_check_file` |

Note on hashes: for non-Lean artifacts this critic has no SHA-256 computation
tool; hashes are transcribed from the governing human-gate records and from the
approved semantic artifact, which all agree. The Lean candidate hash was
computed by the restricted Lean tooling. The Gate B record and the assumption
record do not publish their own hashes (this is the known, disclosed
traceability gap SEM2-CRIT-F2 / PTX-ADD-SEM2-058, non-blocking for this
review).

Independent verification against the official HTML
(`documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html`, SHA-256
`e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856`) was
performed for the load-bearing evidence: the add section (anchor
`integer-arithmetic-instructions-add`, lines 8757-8802), the predication
clause (anchor `control-flow-instructions-at`, lines 21826-21841), the bit
bucket rule (line 7534-7535), and the register-width statement (lines
2617-2631). All confirmed. A literal search for "Threads with a False guard
predicate do nothing" returned 0 matches only because the words `True` and
`False` are wrapped in inline `<code>` markup; the direct anchor read and a
search for "do nothing" (exactly 1 match, line 21839) confirm the clause.

---

## 4. Semantic-to-Lean mapping table

Legend: ✓ faithful; ⚠ faithful with caveat/observation.

| # | Required check | Approved semantics (claim IDs) | Lean candidate | Result |
|---|---|---|---|---|
| 1 | `.u32` width representation | SEM2-009/010/012; D-11 (fixed-width 32-bit unsigned domain) | `U32` wraps `Fin u32Modulus` with `u32Modulus = 2 ^ u32Bits`, `u32Bits = 32`; every `U32` is in `[0, 2^32)`. Wrapper has no arithmetic operators; only `addU32` adds. | ✓ |
| 2 | `addU32` implements exactly `(a + b) mod 2^32` | SEM2-015 (HUMAN_APPROVED_ASSUMPTION), SEM2-016 | `addU32 a b = { toFin := Fin.mk ((a.toFin.val + b.toFin.val) % u32Modulus) ... }` — exactly the mathematical sum reduced mod 2^32. | ✓ |
| 3 | Modulo behavior clearly identified as human-approved project assumption, never NVIDIA source fact | SEM2-015 classification rule; Gate B rationale; assumption record | Header WARNING (lines 22-28), `u32Modulus` comment, `addU32` comment, and the `0xFFFFFFFF + 1 = 0` `#eval` comment all label the rule as the human-approved project assumption and state it is NOT an NVIDIA source fact. No comment attributes it to NVIDIA. | ✓ |
| 4 | Operand order exactly `d, a, b` | SEM2-004/048 | `AddU32Instruction` fields are `guard, d, a, b`; `execAddU32` reads `i.a` and `i.b` as sources and updates `i.d`; comments state operand order `d, a, b`. | ✓ |
| 5 | `SourceOperand` supports exactly the approved bounded source forms | SEM2-025/026/034 (register or constant immediate) | `SourceOperand.reg : RegId -> SourceOperand` and `SourceOperand.imm : U32 -> SourceOperand`; comment notes immediate range/encoding remains open (SEM2-053). | ✓ |
| 6 | Destination supports register and bit bucket only, to approved strength | SEM2-030/033/047 (bit-bucket consequence supported only to the strength of the general 9.2 rule) | `Destination.reg : RegId -> Destination` and `Destination.bitBucket : Destination`; bit-bucket no-write consequence implemented; comment cites SEM2-030/047 and the strength caveat. | ✓ |
| 7 | `MachineState` contains only approved minimal state | SEM2-049 (pair of value-register file and predicate-register file) | `MachineState` has exactly `valueRegs : RegId -> Option U32` and `predRegs : PredId -> Option Bool`; no memory, shared, special-register, or concurrency state. | ✓ |
| 8 | Missing registers/predicates yield partial execution rather than invented errors | SEM2-044/045/046/050; D-8 (no error constructor) | `Option none` is returned exactly for missing guard predicate or missing source register; comments describe this as PARTIAL execution, not error/trap/UB/impl-defined. See F-2. | ✓ (see F-2) |
| 9 | Guard semantics: unguarded → true; `@p` → p; `@!p` → not p | SEM2-018/023/027 | `evalGuard`: `unguarded => some true`; `atPos p => s.predRegs p`; `atNeg p => some (not b)` when `p` bound. | ✓ |
| 10 | False complete guard returns the unchanged input state | SEM2-024/031 | `execAddU32`: `some false => some (ExecOutcome.guardFalse s)` where `s` is the input state, unchanged. Confirmed by `#eval` (`@p` with p=false leaves r1 at 5). | ✓ |
| 11 | False guard does not unnecessarily evaluate source operands | (implementation-level consequence of 10) | `evalSource` is called only in the `some true` branch; the `some false` branch returns without evaluating `i.a` or `i.b`. | ✓ |
| 12 | True guard reads both sources before writing the destination | SEM2-025/026/029 | In the `some true` branch both `evalSource s i.a` and `evalSource s i.b` are evaluated in the match scrutinee before `updateDestination` is applied. | ✓ |
| 13 | Destination/source aliasing uses pre-update source values | SEM2-043 (official example `add.u32 %r, %r, 4`, d == a) | The result is computed from values read from the pre-update state; `#eval` with `d == a == r1` yields `5 + 7 = 12`, demonstrating read-before-write. | ✓ |
| 14 | `updateDestination` preserves unrelated value registers and all predicate registers by construction | SEM2-028/029; PRF-2 frame | `updateDestination` replaces only `valueRegs` via `if r' == r then some result else s.valueRegs r'`; `predRegs` are untouched (only the `valueRegs` field is updated in the record). | ✓ |
| 15 | Bit bucket leaves the state unchanged | SEM2-030 | `Destination.bitBucket => s` returns the input state; `#eval` confirms r1 stays 1. | ✓ |
| 16 | No error, trap, UB, or implementation-defined behavior invented | SEM2-044/045/046/050 | No error constructor; `none` is used only for partial lookups; comments explicitly disclaim invented error/UB/impl-defined behavior. | ✓ |
| 17 | `AddTypeSpecifier`/`ExecOutcome` introduce no semantic drift or meaningless distinctions | SEM2-048/050; D-8 | `AddTypeSpecifier` has a single constructor `.u32` and the `type` field is never read by `execAddU32` (structurally present, semantically inert — faithful to the approved instruction representation). `ExecOutcome` has exactly `executed` and `guardFalse`, matching the approved two-case outcome. See F-3, F-4. | ✓ (see F-3, F-4) |
| 18 | Helper definitions and `#eval` examples do not silently strengthen the semantics | executable-example scope; SEM2-015 labeling | `mkU32` reduces mod 2^32 using the same approved rule; `mkState` is a binder-list constructor; all `#eval`s are demonstrative, and the wrap example is explicitly labeled as the human assumption. No theorem is stated. | ✓ |
| 19 | Traceability comments accurately point to semantic claim IDs | all claims in add-u32-v2.json | Every claim ID cited in the Lean comments exists in the approved semantics and the cited claims match the code behavior (verified individually; see Section 7). | ✓ |
| 20 | No `sorry`, `admit`, `axiom`, or `unsafe` occurs | project restrictions | grep over `candidates/ptx/9.3/lean/*.lean` for `sorry|admit|axiom|unsafe|set_option|#check|#print` returned no matches. | ✓ |

---

## 5. Findings

| Finding ID | Severity | Affected artifact | Exact location | Description | Consequence | Required owner | Human review required |
|---|---|---|---|---|---|---|---|
| LMAP-CRIT-F1 | MINOR | `candidates/ptx/9.3/lean/AddU32.lean` | `updateDestination` doc comment (lines 209-217) | The comment states "no other value register, predicate register, carry flag, or status component is written by base add.u32." This wording mirrors the approved semantics claim SEM2-028/029, and the code itself is faithful (only the destination is written; no carry/status component exists in the minimal state). However, the known semantic-critic MINOR SEM2-CRIT-F1 established that the "no carry flag / status register / condition-code component" portion is negative evidence (absence-based inference), not an affirmative NVIDIA enumeration. The Lean comment repeats that negative claim without restating the absence-based caveat. The code and the approved bounded semantics are not affected, and no theorem in this candidate overstates the claim; but the caveat should be preserved in the comment so future PRF-2/frame arguments do not cite "no carry flag is written" as an explicit NVIDIA statement. | Comment-level traceability precision only. No change to execution behavior. Must remain traceable and be addressed before final acceptance (per Gate B), consistent with SEM2-CRIT-F1. | Lean Formalizer | No |
| LMAP-CRIT-F2 | NOTE | `candidates/ptx/9.3/lean/AddU32.lean` | `MachineState`, `evalSource`, `evalGuard`, `execAddU32` (`Option none`); header comment lines 34-36 | The approved semantics fixes behavior for well-formed states and well-typed instructions (PRF-1); it does not define behavior for a state missing a referenced register or predicate. The Lean candidate represents such out-of-domain states as partial execution (`Option none`), consistent with the approved no-error design (SEM2-050) and with required check 8. This is a Lean-mapping decision, not a semantic invention within the well-formed domain. | The theorem phase must quantify faithfully over well-formed states so the `none` case is excluded from faithfulness claims; `none` must never be interpreted as an approved error/trap. | Lean Formalizer / Proof Engineer | No |
| LMAP-CRIT-F3 | NOTE | `candidates/ptx/9.3/lean/AddU32.lean` | `AddTypeSpecifier` and `AddU32Instruction.type` (lines 140-167) | The instruction type field has a single constructor and is never read by `execAddU32`. It is structurally present but semantically inert. This is consistent with the approved instruction representation (SEM2-048: type specifier `.u32` is part of the form). It does not create vacuous state or any behavior distinction, because there is exactly one type value. | No impact on faithfulness. If a later unit adds more type specifiers, the field must become load-bearing or be removed; for the bounded unit it is harmless. | Lean Formalizer | No |
| LMAP-CRIT-F4 | NOTE | `candidates/ptx/9.3/lean/AddU32.lean` | `ExecOutcome` (lines 229-231) | `ExecOutcome.guardFalse` carries a `MachineState`, which in `execAddU32` is always the unchanged input state. The two-case outcome matches the approved design (SEM2-050; D-8: executed-with-updated-state and guard-false-no-state-change). The carried state is redundant but cannot introduce an unapproved distinction, because the only producer passes the input state unchanged. Also, the mnemonic `add` and the empty modifier set are implicit (fixed by unit identity) rather than explicit fields, matching the bounded unit's scope (SEM2-048 lists them in the representation; their absence does not change behavior). | No semantic drift. The redundant state in `guardFalse` should be kept in mind when PRF-4 (guard-false frame) is stated, but the implementation already guarantees the unchanged-state property. | Lean Formalizer | No |
| LMAP-CRIT-F5 | NOTE | `candidates/ptx/9.3/lean/AddU32.lean` | scope of executable model vs. semantics version/target fields | The approved semantics records version/target gating (PRE-5/PRE-6; SEM2-036/037; VAL-5/VAL-6) as static validation obligations, not as state-affecting execution behavior. The Lean candidate is an executable instruction-local semantics and does not model version/target metadata. This is a scope boundary of the bounded unit, not an omission of state behavior. Helper constructors and `#eval` examples (Section 4 check 18) were inspected and do not strengthen the semantics. | No impact on the state transition of a legal add.u32. Version/target validation is out of the executable-mapping scope and should be addressed (if at all) by the validation layer before final acceptance. | Lean Formalizer / Spec Manager | No |

---

## 6. Lean verification results

Independent verification was performed with the restricted Lean tools.

| Tool | Result |
|---|---|
| `lean_check_file` `candidates/ptx/9.3/lean/AddU32.lean` | `success: true`, exit code 0, 0 errors, 0 warnings, not timed out. Computed SHA-256 `4fa14a35f4d127b4df6cd10eb541bf6a4503042c6dc306290e4258f90c691b7b` (size 14090 bytes). |
| `lean_get_diagnostics` `candidates/ptx/9.3/lean/AddU32.lean` | 0 errors, 0 warnings, 0 information diagnostics. |
| `lean_run_eval` `candidates/ptx/9.3/lean/AddU32.lean` | All 9 `#eval` outputs printed and match expected semantics: `12` (5+7), `0` (0xFFFFFFFF+1 wrap under the human assumption), `some true` (unguarded guard), `some true` (@!p with p=false), `some 100` (register destination update), `some 1` (bit bucket leaves r1 unchanged), `some 5` (@p false: state unchanged), `some 12` (@!p false, aliased d==a: executes and reads pre-update value), `"partial-none"` (missing source register yields none, not an error). |

Successful compilation is necessary but not sufficient; the mapping analysis in
Sections 4-5 establishes faithfulness independently of compilation.

---

## 7. Traceability assessment

- Every semantic claim ID cited in the Lean candidate exists in the approved
  `add-u32-v2.json` and was individually checked: SEM2-004, 009, 010, 012,
  015, 016, 018, 021, 022, 023, 024, 025, 026, 027, 028, 029, 030, 031, 033,
  034, 035, 043, 044, 045, 046, 047, 048, 049, 050, 053, 055. All exist and
  match the code behavior they annotate.
- The header cites the Gate A record, Gate B record, assumption record,
  architecture reference, primary bundle, supplement bundle, and semantic
  critique; all are real, readable artifacts and were read by this critic.
- Load-bearing source facts were independently re-verified in the official
  HTML:
  - add section anchor `integer-arithmetic-instructions-add` (lines 8757-8802):
    syntax `add.type1 d, a, b;` / `add{.sat}.type2 d, a, b;` with `.u32` in
    `.type2`; "Add two values."; "Performs addition and writes the resulting
    value into a destination register."; operand typing; Semantics else branch
    `d = a + b;`. ✓
  - predication clause anchor `control-flow-instructions-at` (lines
    21826-21841): "Execute an instruction or instruction block for threads
    that have the guard predicate True. Threads with a False guard predicate
    do nothing." and Semantics "If {!}p then instruction". ✓ (This confirms
    BLOCK-2 is source-supported; the clause is not treated as a human
    assumption, matching SEM2-024.)
  - bit bucket rule (lines 7534-7535): "_" may be used in place of a
    destination register. ✓
  - register widths (lines 2617-2631): scalar registers of 8/16/32/64/128
    bits; predicate registers 1-bit; registers not fully addressable. ✓
- No circular test or self-referential evidence was found: the `#eval`
  examples are demonstrations of the defined functions, not independent
  evidence, and the semantic claims do not depend on the Lean candidate.

---

## 8. Human-assumption mapping assessment

- The modulo-2^32 rule is mapped exactly: `addU32` computes the mathematical
  sum of the two source values and reduces modulo `2^32`.
- The rule is identified, in the header WARNING and in each relevant comment
  (`u32Modulus`, `addU32`, and the wrap `#eval`), as the human-approved
  project assumption recorded in
  `reviews/ptx-add-u32/assumptions/ptx-add-u32-overflow-assumption-v1.json`
  and in semantic claim PTX-ADD-SEM2-015. The comments explicitly state it is
  NOT an NVIDIA source fact and is never attributed to NVIDIA as explicitly
  specified. This satisfies the assumption record's requirement that Lean
  definitions and executable examples reference the assumption.
- The dependency chain SEM2-015 → SEM2-016/029 (destination update fully
  determined by the assumption) is reflected in the `addU32` and
  `updateDestination` comments.
- The wrap example (`0xFFFFFFFF + 1 = 0`) is labeled as exercising the human
  assumption, which is the correct epistemic framing.
- No claim in the Lean candidate classifies the modulo rule as a source fact,
  and no comment attributes it to NVIDIA.

---

## 9. Residual risks

- R-1 (ties to LMAP-CRIT-F1 / SEM2-CRIT-F1): The "no carry flag / status
  register" statement is negative evidence. Future PRF-2/PRF-3 frame theorems
  must not cite it as an explicit NVIDIA statement that no such component is
  written; the frame obligation should be stated over the bounded model and
  the negative-evidence caveat must remain traceable until final acceptance.
- R-2 (ties to LMAP-CRIT-F2): `Option none` partial execution is a mapping
  decision for out-of-domain states. The theorem phase must quantify over
  well-formed states (PRF-1) so faithfulness claims are about the approved
  domain only; `none` is not an approved error behavior.
- R-3 (known gap SEM2-CRIT-F2 / SEM2-058): the human assumption decision
  record does not publish its own SHA-256. This was accepted at Gate B as
  non-blocking and must be closed before final acceptance (Gate D).
- R-4 (known AMB-1 / SEM2-054): add-specific bit-bucket demonstration is
  absent; the no-write consequence is supported only to the strength of the
  general section 9.2 rule. The Lean candidate implements the consequence at
  that approved strength; PRF-3 strength must not exceed it.
- R-5 (known SEM2-053): constant-immediate range/encoding is open; it affects
  static well-formedness only and does not change the state transition of a
  given legal instruction.

---

## 10. Gate C readiness assessment

- The Lean candidate compiles cleanly under `lake env lean` (0 errors,
  0 warnings) and its executable examples produce exactly the expected
  outputs.
- The candidate implements the Gate-B-approved semantics without semantic
  strengthening, weakening, invention, or omission within the well-formed
  state domain: value domain, modulo rule, operand order and forms,
  destination and bit bucket, minimal state, partial lookup, guard semantics,
  guard-false no-op, read-before-write aliasing, destination-only update,
  predicate preservation, and absence of invented error/UB behavior are all
  faithfully mapped (Section 4).
- Traceability comments are accurate (Section 7), and the human-approved
  modulo assumption is mapped and labeled correctly (Section 8).
- No prohibited declarations occur (Section 4 check 20).
- The candidate is therefore **ready to be presented for Human Gate C**.
  READY_FOR_HUMAN_REVIEW means only that Human Gate C may occur; it is not a
  Gate C approval and not a final acceptance. The 1 MINOR and 4 NOTE findings
  above should remain visible to the human reviewer and be addressed before
  final acceptance.

---

## 11. Critic independence statement

I, the Semantic Critic, performed this review independently. I read completely
the Gate B record, the human overflow-assumption record, the approved
architecture, the Gate-B-approved semantic interpretation, the pre-Gate-B
semantic critique, and the Lean candidate. I independently verified the
load-bearing official evidence against the whitelisted PTX ISA 9.3 HTML using
the restricted specification tools, and I verified the Lean candidate using
the restricted Lean tools (`lean_check_file`, `lean_get_diagnostics`,
`lean_run_eval`). I did not use CUDA C, LLVM, another ISA, compiler behavior,
or model prior knowledge as evidence. I did not edit, repair, rewrite, weaken,
or strengthen any reviewed artifact, including the Lean candidate. I did not
write theorem statements or proofs, and I did not approve Gate C or any human
gate. I did not modify the Lean candidate; the only artifact I created is this
review.
