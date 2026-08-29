# Spec2Lean V1 release audit

Audit date: 2026-08-28 (Europe/Zurich)

## 1. Release identity and verdict

- V1 tag: `v1.0.0`
- Tagged commit: `58a2b0d0c285c6284543d4fa7fb779baa39cadbf`
- Tag object: annotated tag `f6baf2740f8cfa71fafb785e60e412bcdf86c732`, dereferencing to the commit above
- Audited checkout: branch `main`, commit `58a2b0d0c285c6284543d4fa7fb779baa39cadbf`
- Initial working tree: clean; `main`, `origin/main`, and `v1.0.0` all pointed to the same commit
- Tag/history changes: none

**Final verdict: READY WITH KNOWN LIMITATIONS.**

V1 is usable for small, supervised experiments. The deterministic suite is green, the accepted PTX index is fresh and internally valid, request scoping stayed bounded in the successful samples, all seven valid sampled instructions reached non-vacuous BUILD/COVERAGE/TRACEABILITY passes, restart/resume worked, and exact source spans resolve. It is not ready for unattended semantic-quality claims: concrete instruction resolution has a demonstrated `cvt` grammar bug, the logical checks accept semantically irrelevant declaration mappings, core behavior remains unresolved or externally parameterized in two sampled translations, and repeated Phase-7 repair artifacts are overwritten.

No theorem/proof requirement was applied in this audit.

## 2. Environment and static repository health

| Item | Observed value |
| --- | --- |
| OS | Ubuntu 24.04.3 LTS, Linux 6.9.0-0-generic, x86_64 |
| Python | 3.12.3 |
| Project source/CLI version | 1.0.0 |
| Editable distribution metadata | 0.1.0 (stale local environment metadata; source defect not established) |
| OpenCode | 1.18.15 |
| Required model | `openai/gpt-5.6-sol` (installed) |
| Reasoning variant | `medium` |
| Lean | 4.33.1, commit `819816b2e0a3bf405af45ae5c7af2491d8f5bee6` |
| Lake | 5.0.0-src+819816b |
| Python dependencies | `lxml 6.1.2`, `PyMuPDF 1.28.2`, `pytest 9.1.1` |

Repository structure matches the intended phases: parsing/indexing, planning, evidence, semantics/open questions, grouped translation, checking, troubleshooting, and a top-level pipeline runner. `spec2lean` is the console entry point and the repository wrapper selects `.venv/bin/python`. There is no doctor command.

The source manifest and both official PTX 9.3 inputs are present. Generated indexes, plans, evidence, semantics, translations, checks, troubleshooting, and runs are ignored while their `.gitkeep` placeholders are tracked. The official raw PTX cache is ignored. This is consistent with the documented reproducible-artifact policy. Existing ignored experimental artifacts predated this audit; they were preserved and excluded from audit sample counts.

No unsafe `shell=True`, `os.system`, or string-built shell execution was found. OpenCode and Lean are invoked with argument arrays, bounded timeouts, isolated temporary configuration/home directories, and captured stdout/stderr. No accidental whole-document LLM handoff was observed: the Planner receives bounded Phase-1 access, Evidence sessions use bounded query tools, Semantic sessions consume one evidence bundle, and Translators consume group semantic artifacts.

Suspicious static items are classified in section 15. In particular, model/reasoning constants are repeated across phase modules; `cli.py` is 1,409 lines, `pipeline/runner.py` 731, and `checking/logical.py` 714; and `pipeline/runner.py` contains harmless duplicate statements (`return None` and a repeated local annotation). These are maintainability issues, not audit blockers.

## 3. Deterministic test result

First and only complete normal-suite run:

```text
.venv/bin/pytest -ra
118 passed in 6.02s
wall time 6.32s; maximum RSS 494,660 KiB
```

| Total | Passed | Failed | Skipped | Pytest duration |
| ---: | ---: | ---: | ---: | ---: |
| 118 | 118 | 0 | 0 | 6.02s |

The suite covers Phases 1–7 and pipeline composition. It uses faked OpenCode runners for normal tests. Relevant passing tests include:

- source-SHA invalidation and deterministic semantic-digest rebuilds;
- complete pipeline composition and fresh-artifact resume;
- rejection of legacy/stale grouped translations and prevention of stale downstream check reuse;
- dry-run behavior and interruption persistence;
- BUILD → Troubleshooter, COVERAGE → Translator, and TRACEABILITY → Semantic Extractor routing;
- compiler-attempt history passed to the next in-memory repair;
- repeated actionable-state/dispatch guards.

No flaky retry was used.

## 4. Phase-1 PTX 9.3 validation

Commands included `index validate`, `index stats`, `PRAGMA integrity_check`, direct SHA-256 checks, and pipeline freshness checks.

| Property | Result |
| --- | --- |
| SQLite integrity | `ok` |
| Structural validation | PASS |
| Documents | 2 (official HTML and PDF) |
| Nodes | 24,352 |
| Source spans | 206,392 |
| PDF pages | 930/930 indexed |
| HTML sections | 715/715 indexed |
| HTML text coverage | 0.990607 |
| PDF text coverage | 0.989400 |
| Correlations | 663 |
| Cross-references | 2,771 resolved; 204 ambiguous; 311 unresolved |
| Semantic/index digest | `e2c43e95b5cb15de4d4b97e5fb1840e8aa8620f26701a0f30e07a2c04ec88fb0` |

Source and page-text identities:

```text
PDF  769cc12e363e7bb9cd311464f2a42edbdaf4c74ca18575de8c358e93223434fc
HTML e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856
PDF page text 5094cc99f761f14f5640109ff9aa1c559c8e761388f26e191a6891b047f1de04
```

The validator reports one accepted warning: `PDF_TEXT_MISMATCH` for `span:8c032c8680b30d2bbd607159`. No validation errors were present. HTML instruction headings used in the audit have HIGH-confidence PDF correlations based on exact section number and normalized title. The sampled evidence itself selected HTML, with official URL, document SHA, DOM path, source line, node ID, and span ID.

Fresh-index reuse was observed on every dry/real/resume run. The database mtime and size were unchanged across the first dry run (`1787788505`, 108,494,848 bytes). Validation costs about 64–72 seconds per invocation on this index.

The stale path was safely exercised by the passing synthetic test `test_sha_invalidation_is_detected`: it copies a fixture, builds a temporary index, changes only the copied source, and requires `STALE_SOURCE_SHA`. The real PTX index was not modified. The passing pipeline fixture also builds Phase 1 from a temporary hash-pinned source manifest.

## 5. CLI and pipeline behavior

- Help: top-level, `run`, and `status` help rendered successfully and listed all intended phases/options.
- Status: reconstructed persisted manifests by explicit pipeline run ID after the originating process ended.
- Dry run: invoked no OpenCode, created no run, reused Phase 1 as fresh, and reported `WOULD_BUILD` for a missing plan.
- Normal runs: four successful small requests are listed below.
- Resume after process loss: reused the plan, all three evidence artifacts, and two completed semantic artifacts; it archived only the incomplete `lop3.b32` semantic directory and rebuilt that unit.
- Resume after success: reused every phase and made zero OpenCode calls; all relevant artifact mtimes remained unchanged.
- `--from`/`--until`: `--dry-run --from check --until check` on the completed movement/conversion run required and reused all fresh upstream artifacts, reused both PASS checks, and stopped at Check.
- Stale downstream behavior: the interrupted semantic artifact was archived rather than trusted. The deterministic pipeline test also proves that a stale group translation forces checks to `WOULD_RUN` rather than reusing prior PASS results.
- Process restart: externally ending the terminal left the manifest as `RUNNING` rather than `INTERRUPTED`, as expected without a delivered `KeyboardInterrupt`; explicit-ID resume reconstructed progress correctly. A deterministic test separately confirms graceful `KeyboardInterrupt` persistence as `INTERRUPTED`.

## 6. Real sample requests and exact commands

Seven genuinely valid instructions were completed. An additional resolver-accepted but invalid spelling and one resolver-rejected valid spelling were retained as defect probes.

```bash
./spec2lean run --language ptx --version 9.3 \
  --instructions add.u64,shf.r.wrap.b32,lop3.b32 --timeout 600

./spec2lean run --language ptx --version 9.3 \
  --instructions add.u64,shf.r.wrap.b32,lop3.b32 \
  --resume pipeline-run:fb459fd6ff62b89bc9986475 --timeout 600

./spec2lean run --language ptx --version 9.3 \
  --instructions setp.eq.u32,selp.u32 --timeout 600

./spec2lean run --language ptx --version 9.3 \
  --instructions mov.b32,cvt.f32.s32 --timeout 600

./spec2lean run --language ptx --version 9.3 \
  --instructions mov.b32,cvt.f32.s32 \
  --resume pipeline-run:50d604fea1b16c3e4dc324af --timeout 600

./spec2lean run --language ptx --version 9.3 \
  --instructions mov.b32,cvt.f32.s32 \
  --resume pipeline-run:50d604fea1b16c3e4dc324af \
  --dry-run --from check --until check

./spec2lean run --language ptx --version 9.3 \
  --instructions cvt.rn.f32.s32 --timeout 600

./spec2lean run --language ptx --version 9.3 \
  --instructions cvt.rn.f16.f32 --timeout 600
```

The `cvt.rn.f32.s32` request failed during exact resolution before OpenCode. `cvt.f32.s32` was incorrectly accepted even though the extracted semantics correctly say an integer-to-float rounding suffix is mandatory. It is not counted among the seven valid samples.

Audit run IDs and plans:

| Scope | Pipeline run | Plan |
| --- | --- | --- |
| `add.u64,shf.r.wrap.b32,lop3.b32` | `pipeline-run:fb459fd6ff62b89bc9986475` | `plan:a96ff4dbe98e5b6dd9380acb` |
| `setp.eq.u32,selp.u32` | `pipeline-run:d5da84639502ec892d67d2b1` | `plan:00b13bb10fe4436125bc4cbf` |
| `mov.b32,cvt.f32.s32` defect probe | `pipeline-run:50d604fea1b16c3e4dc324af` | `plan:663df68c415d44ad08c1ec27` |
| valid `cvt.rn.f16.f32` | `pipeline-run:fd7667ba9b1bef3784f6f444` | `plan:1cb609ec754a456588945e63` |
| valid `cvt.rn.f32.s32` rejection | `pipeline-run:c97432047396491866a95765` | no plan |

## 7. Planner audit

The four accepted plans contain exactly their requested units, no external prerequisites, no dependencies, no cycles, and one processing layer. This is correct for the independent samples; no artificial ordering was invented. Grouping follows indexed sections:

- `add.u64` → `IntegerArithmeticInstructions`;
- `shf.r.wrap.b32` and `lop3.b32` → `LogicAndShiftInstructions`;
- `setp.eq.u32` and `selp.u32` → `ComparisonAndSelectionInstructions`;
- `mov.b32` and the generic conversion defect probe → `DataMovementAndConversion`;
- `cvt.rn.f16.f32` → `CvtConversions`.

The only strange ordering was display/execution of the conversion unit before `mov.b32`; both remained in layer 0 with no dependency edge, so this was deterministic ordering rather than invented dependency.

The important Planner defect is deterministic exact-scope resolution before the LLM. `_syntax_accepts` does not expand chained grammar definitions such as `.dtype = .atype = {...}`. Consequently it rejected valid `cvt.rn.f32.s32`. Literal matching separately accepted `cvt.f32.s32`, although Phase-4 evidence states that an integer-to-float rounding modifier is required. The smallest likely fix is to parse chained metavariable assignments and apply required-modifier semantic constraints when resolving concrete spellings; tests should cover both acceptance and rejection cases.

## 8. Evidence audit

All seven valid samples had focused core evidence for syntax, operands/types, the actual operation/algorithm, and applicable branches or edge cases. Quotations are exact Phase-1 text, not model paraphrases. Every inspected node/span exists in the accepted database and resolves to the official NVIDIA HTML source.

Highlights:

- `add.u64`: scalar syntax/type rule, destination write, and exact `d = a + b` algorithm branch.
- `shf.r.wrap.b32`: concatenation layout, `c & 0x1f`, right-shift expression, zero-count behavior, PTX version, and target.
- `lop3.b32`: 8-bit LUT domain, input ordering, fixed b32 syntax, per-bit operation, constant-false/true cases, version, and target.
- `setp.eq.u32` / `selp.u32`: source/destination types, predicate roles, equality/selection branches, optional complement/sink behavior.
- `mov.b32`: both 4×8 and 2×16 pack/unpack layouts, destination sinks, exact examples, version, and target.
- `cvt.rn.f16.f32`: scalar conversion branch, required `.rn` rule, subnormal target behavior, wider-register rules, and zero-extension.

No internet, runtime, LLM-reasoning resolution, or open-question session was used. The conversion retrievers were expensive and explored the very large `cvt` section, but their accepted bundles remained request-focused. The generic `cvt.f32.s32` defect probe produced a 34 KB evidence bundle; valid `cvt.rn.f16.f32` produced similarly broad conversion evidence. This is not whole-document context, but it is the clearest context/cost hotspot.

## 9. Semantic-extraction audit

Claim categories were used honestly in the inspected artifacts. Unsupported details were generally labeled `DESIGN_DEPENDENCY`, not `SOURCE_FACT` or `ASSUMPTION`; all seven valid samples had no assumptions.

- GOOD: `shf.r.wrap.b32`, `lop3.b32`, `selp.u32`, and `mov.b32` capture operands, roles, widths, branches, result, edge cases, and state effects.
- ACCEPTABLE: `setp.eq.u32` correctly specializes equality and models the optional complementary destination/sink; it also records predicated execution as an unbound design gap rather than inventing guard behavior.
- ACCEPTABLE but incomplete: `add.u64` explicitly says overflow/truncation is unresolved.
- ACCEPTABLE but incomplete: `cvt.rn.f16.f32` fixes `.rn`, target-specific subnormal preprocessing, and width rules, but explicitly leaves exact f32/f16 values, NaNs, infinities, signed zeros, and overflow to an unbound dependency.

The generic `cvt.f32.s32` defect probe also correctly detected that rounding is mandatory and modeled all four legal modes. That semantic recovery does not make the requested spelling valid.

## 10. Generated Lean audit and quality table

| Valid instruction | Planner | Evidence | Semantics | BUILD | COVERAGE | TRACEABILITY | Lean quality |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `add.u64` | GOOD | GOOD | ACCEPTABLE | PASS* | PASS | PASS | WEAK |
| `shf.r.wrap.b32` | GOOD | GOOD | GOOD | PASS* | PASS | PASS | GOOD |
| `lop3.b32` | GOOD | GOOD | GOOD | PASS* | PASS | PASS | GOOD |
| `setp.eq.u32` | GOOD | GOOD | ACCEPTABLE | PASS | PASS | PASS | ACCEPTABLE |
| `selp.u32` | GOOD | GOOD | GOOD | PASS | PASS | PASS | GOOD |
| `mov.b32` | GOOD | GOOD | GOOD | PASS | PASS* | PASS | ACCEPTABLE |
| `cvt.rn.f16.f32` | GOOD | GOOD | ACCEPTABLE | PASS | PASS | PASS | WEAK |

`*` means the terminal status passed after routing or a shared-group repair, not on the original Phase-6 attempt.

WEAK explanations:

- `add.u64`: `add_u64` returns `none` on overflow and `exec_add_u64` performs no write. Phase 4 explicitly did not establish that behavior. The code therefore introduces a consequential behavior absent from the source chain and makes a normal finite-width operation partial. This is not justified merely by compiling.
- `cvt.rn.f16.f32`: the actual rounded conversion is an external function argument `convertRN : F32 -> F16`. The file implements target-specific subnormal preprocessing and state/width handling, but the core conversion result is not defined.

Other observations:

- `shf.r.wrap.b32` uses `BitVec 32`, correctly wraps the count modulo 32, and handles effective count zero.
- `lop3.b32` visibly computes the indexed LUT bit at each of 32 positions. Its Nat/List fold is understandable though not especially concise.
- `setp.eq.u32` and `selp.u32` are clear and idiomatic enough. The setp execution API permits both predicate destinations to be sinks, while the evidence says the sink may replace any one destination; this is a minor under-validation of an operand-shape constraint.
- `mov.b32` models all four evidenced layouts and rejects an all-sink destination. It uses a general `(width,bits)` structure rather than finite-width types, but normalizes writes.
- Generic `Carry`, `Predicate`, register, and machine-state infrastructure is repeatedly redeclared across independent generated files. Some declarations are unused. Reuse is weak.

There are no theorems, and none were required.

## 11. Phase-6 and Phase-7 audit

Final checks are non-vacuous:

| Instruction | BUILD duration | Covered items | Valid declaration mappings |
| --- | ---: | ---: | ---: |
| `add.u64` | 470 ms | 13 | 10 |
| `shf.r.wrap.b32` | 462 ms | 13 | 17 shared-group mappings |
| `lop3.b32` | 462 ms | 14 | 17 shared-group mappings |
| `setp.eq.u32` | 606 ms | 10 | 13 shared-group mappings |
| `selp.u32` | 606 ms | 8 | 13 shared-group mappings |
| `mov.b32` | 1,248 ms | 12 | 31 shared-group mappings |
| `cvt.rn.f16.f32` | 702 ms | 15 | 16 |

All final uncovered and broken-mapping lists are empty. The passes are not caused by empty semantic or mapping sets.

Observed original failures and routing:

- `add.u64`: BUILD failed on invalid subtype projections and a non-decidable opaque availability test. BUILD → Troubleshooter. One repair dispatch, then all checks passed.
- shared `shf.r.wrap.b32` / `lop3.b32`: BUILD failed. BUILD → Troubleshooter. Three compiler-guided dispatches were needed; final code passed for both units.
- generic `cvt.f32.s32`: COVERAGE failed for unmapped `typed-form` and `rounding-required`. COVERAGE → Translator. One mapping-only revision made that unit pass.
- `mov.b32`: COVERAGE then failed for version/target claims in the same group. COVERAGE → Translator. A second mapping-only group revision made it pass.
- TRACEABILITY → Semantic Extractor was verified with synthetic fixtures in the deterministic suite; no valuable real artifact was corrupted to force it.
- The repeated-state guard was verified by `test_resolver_stops_on_repeated_actionable_state_instead_of_looping`, which stops at `NO_PROGRESS` after one unchanged revision/check cycle.

The two movement/conversion revisions did not change Lean source; they only added mappings for already existing declarations. Processing the two uncovered units serially forced two expensive whole-group Translator revision sessions. This is avoidable repeated group-level LLM work.

The logical checks have a material limitation: they prove identifier existence, source provenance, and coverage through declared links, but not whether a declaration is semantically related to the claim it cites. Real manifests map unused `Carry`/`Predicate` declarations to unrelated syntax or operation claims and still pass. Thus TRACEABILITY PASS means structurally complete provenance, not meaningful semantic correspondence for every mapping.

## 12. End-to-end traceability examples

The following declarations were traversed manually with `spec2lean trace` and source inspection:

1. Core operation: `Spec2Lean.Ptx.IntegerArithmeticInstructions.add_u64` → `claim:scalar`, `claim:types`, and `claim:overflow-dependency` → exact syntax/type/algorithm evidence → HTML nodes `node:6911ca0ff4b0cd319f6bb850`, `node:9d676c8821c3b62a83c81ae8`, `node:31490dca8a612e2a57162e61` → DOM spans in official PTX section 9.7.1.1. The chain resolves, but it does not justify returning `none` on overflow.
2. Type declaration: `Spec2Lean.Ptx.ComparisonAndSelectionInstructions.U32Value` → setp/selp type claims → exact `.u32` syntax and operand-type evidence → official PTX sections 9.7.6.2/9.7.6.3. The finite-width choice is reasonable.
3. Edge/branch operation: `Spec2Lean.Ptx.LogicAndShiftInstructions.shf_r_wrap_b32` → layout/count/right-result/zero-count claims → exact `c & 0x1f` and shift algorithm evidence → `node:13d925597c3636284ec0cb60` and `node:b9c9743751a82c7cab9a4cc9` → official PTX section 9.7.8.7. The Lean expression is reasonably justified.
4. State/edge execution: `Spec2Lean.Ptx.DataMovementAndConversion.execute_mov_b32` → pack/unpack and sink claims → exact packing equations and sink rule → official PTX section 9.7.9.4. The all-sink rejection and optional writes are justified.

Evidence IDs are content-addressed globally. When the same exact evidence appeared in earlier plans, `trace` sometimes printed the identical record from an older plan directory because `find_evidence` returns the first globally identical match after checking content identity. Source facts remain identical, but the displayed bundle path is not request-local and output can be confusing.

## 13. Resume/reuse result

Successful explicit-ID resume command:

```bash
./spec2lean run --language ptx --version 9.3 \
  --instructions mov.b32,cvt.f32.s32 \
  --resume pipeline-run:50d604fea1b16c3e4dc324af --timeout 600
```

| Measure | Initial run | Successful resume |
| --- | ---: | ---: |
| Wall time | about 789.6s | 63.89s |
| OpenCode sessions | 8 | 0 |
| Phase-1 disposition | REUSED/FRESH | REUSED/FRESH |
| Plan/evidence/semantics/translation/check | built/revised/checked | all REUSED |
| Artifact mtimes | created/changed | unchanged |

Resume/reuse worked. The remaining 63.89 seconds is almost entirely full Phase-1 validation. The earlier recovery from an externally ended process also reused every atomically complete artifact and rebuilt only the incomplete semantic unit.

## 14. Performance and model-cost observations

All model-backed sessions used `openai/gpt-5.6-sol`, reasoning `medium`, OpenCode 1.18.15. No automatic retry session was reported. No monetary cost was exposed (`cost: 0` in events).

| Real request | Wall time | Planner | Evidence | Semantics | Initial translation | Phase 7 | OpenCode sessions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3-unit arithmetic/logic | 7,550s manifest elapsed* | 26s | 117s | 215s | 197s | 243s | 13 |
| 2-unit comparison/selection | 415s | 14s | 84s | 138s | 100s | none | 6 |
| 2-unit movement/generic-conversion probe | about 789.6s | 23s | 142s | 165s | 183s | 192s in Translator revisions | 8 |
| valid `cvt.rn.f16.f32` | 385s | 19s | 92s | 103s | 98s | none | 4 |

`*` The first run's manifest elapsed time includes the externally ended process and a long resume/transport gap; its phase sums are the useful active-work measure.

Across the four completed requests, 31 OpenCode sessions ran. Artifacts for 29 retained sessions expose 108 `step_finish` token records totaling 2,131,165 reported tokens: 688,117 input, 77,214 output, 14,154 reasoning, and 1,351,680 cache-read. These are sums of OpenCode's per-step reported counters, not an independent billing calculation. Two earlier shf repair-session artifacts were overwritten, so a complete token total is unavailable.

The largest retained contexts were Evidence retrieval for generic `cvt.f32.s32` (431,033 total-reported tokens across 11 steps, mostly cache reads) and valid `cvt.rn.f16.f32` (381,045 across 12). Conversion evidence is the principal cost hotspot. Translation takes roughly 89–183 seconds per group. Phase 6 itself is cheap.

Repeated work observations:

- fresh resume performs no model work but always spends about a minute validating the full index;
- two separate coverage failures in one movement/conversion group caused two full group Translator revision sessions even though both revisions changed mappings only;
- three build-repair calls were needed for the logic/shift group;
- no repeated Planner/Evidence/Semantic work occurred on successful resume.

## 15. Implementation-quality findings

### CRITICAL

None observed.

### MAJOR

1. **Concrete syntax resolution is unsound for `cvt`.** Valid `cvt.rn.f32.s32` was rejected while invalid `cvt.f32.s32` was accepted. Responsible phase: Phase 2 deterministic scope resolution. Smallest likely fix: correctly expand chained grammar metavariable definitions and enforce semantically mandatory modifiers; add positive/negative concrete-spelling tests.
2. **Coverage/Traceability accept semantically irrelevant links.** The checks validate declaration/claim/evidence existence and provenance but cannot determine that a declaration implements the cited claim. Real unused generic declarations demonstrate false-confidence PASS mappings. Responsible phases: Phase 5 mapping generation and Phase 6 logical checks. Smallest likely improvement without a new phase: strengthen deterministic role/use constraints and translator validation for unused generic declarations; manual semantic review remains necessary.
3. **Core semantics may pass while unresolved.** `add.u64` invents partial overflow behavior, and `cvt.rn.f16.f32` delegates the core conversion to a caller-supplied function. Both compile and pass coverage/traceability. Responsible phases: Phase 4 design-dependency handling and Phase 5 translation policy. Smallest likely fix: do not permit an unresolved dependency to be silently presented as a complete operation; either bind it from indexed evidence/shared definitions or preserve an explicit incomplete status that cannot become full PASS.
4. **Repeated Phase-7 artifacts are overwritten.** A three-dispatch repair leaves one `troubleshoot.json` and one current `check.json`; the resolution file records run IDs/statuses but not the earlier diagnostics, source snapshots, token logs, or changes. The same issue makes current `translator-run.json` represent the latest revision rather than the original translation (before-copies partially mitigate Translator revisions). Responsible phase: Phase 7 stores. Smallest fix: content-addressed/per-dispatch subdirectories plus immutable references from `resolution.json`.
5. **Generated `add.u64` overflow behavior is not source-justified.** Returning `none` and skipping the destination write is a consequential semantic choice absent from Phase 4. Responsible phase: Phase 5 output quality. A minimal correction requires first resolving the finite-width result rule from authoritative indexed context; it should not be guessed in the audit.

### MINOR

1. Generated groups duplicate `Carry`, `Predicate`, register, machine-state, version, and target infrastructure; several declarations are unused.
2. `setp.eq.u32` execution can represent two sink destinations despite evidence allowing the sink in any one destination position.
3. The trace CLI's global content-addressed evidence lookup can display an identical record from an unrelated older plan directory.
4. Phase-1 validation dominates no-op/dry/resume latency (64–72 seconds).
5. Model/reasoning configuration is duplicated across Planner, Retriever, Extractor/question handler, Translator, and Troubleshooter modules.
6. Large modules and two obvious duplicate statements in `pipeline/runner.py` increase maintenance risk, although orchestration still delegates phase work rather than reimplementing it.
7. Top-level phase 2–5 metadata does not consistently record OpenCode version even though the executable/version is available elsewhere.
8. The local editable installation reports package metadata 0.1.0 while source/CLI reports 1.0.0; this appears environment-specific and should be cleared by reinstalling the tagged package.

### NOTE

1. The accepted index has one known PDF text mismatch warning and 515 non-resolved cross-references (204 ambiguous, 311 unresolved).
2. Index manifests/database rows contain absolute local paths. Generated indexes are intentionally local/ignored, so this is a portability limitation rather than a tracked-release defect.
3. Stable IDs are content-derived or include creation timestamps where run uniqueness is intended. No unexpected random semantic IDs were observed.
4. Logging around expensive calls is detailed (start/finish, command, model/reasoning, session ID, stdout/stderr), but overwrite behavior prevents complete multi-dispatch audit history.

## 16. Limitations and bugs discovered

- This audit establishes observed compilation and structured provenance, not formal semantic correctness.
- Seven valid instructions were tested; all seven reached terminal BUILD/COVERAGE/TRACEABILITY PASS. Five had no manually assigned WEAK/FAIL quality grade. `add.u64` and `cvt.rn.f16.f32` are the material weak outputs.
- The invalid `cvt.f32.s32` probe also reached terminal PASS, illustrating why a terminal pipeline status is insufficient.
- Valid `cvt.rn.f32.s32` could not enter planning due to the resolver bug and made no model call.
- No natural TRACEABILITY failure occurred, so that real LLM revision route was not quota-tested; deterministic synthetic routing passed.
- No runtime probe, internet resolution, or LLM-reasoning supplement was exercised because no open question was raised.
- The audit did not run the full PTX specification and did not modify the V1 implementation.

## 17. Reproduction summary

```text
V1 tag: v1.0.0
V1 SHA: 58a2b0d0c285c6284543d4fa7fb779baa39cadbf
OS: Ubuntu 24.04.3 LTS x86_64
Python: 3.12.3
Lean: 4.33.1 (819816b2e0a3bf405af45ae5c7af2491d8f5bee6)
Lake: 5.0.0-src+819816b
OpenCode: 1.18.15
Model: openai/gpt-5.6-sol
Reasoning: medium
PTX PDF SHA: 769cc12e363e7bb9cd311464f2a42edbdaf4c74ca18575de8c358e93223434fc
PTX HTML SHA: e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856
Phase-1 digest: e2c43e95b5cb15de4d4b97e5fb1840e8aa8620f26701a0f30e07a2c04ec88fb0
```

The exact real commands are in section 6. No credentials, API keys, or authentication material are recorded here.
