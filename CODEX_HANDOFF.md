You are taking over a research/engineering project called Spec2Lean.

This is NOT a greenfield project and it is NOT merely a Lean exercise.

Before making significant changes, your responsibility is to understand the
entire repository, the research objective, the existing agentic architecture,
the verification model, the completed experiments, the performance failures,
and the current refactoring direction.

The repository is authoritative if anything in this handoff disagrees with the
actual checkout.

Do not start by rewriting the project.
Do not start by manually formalizing another instruction.
Do not start by reducing safeguards merely to make the benchmark faster.

First understand the system as a whole.

======================================================================
0. CRITICAL ROLE BOUNDARY
======================================================================

YOUR ROLE IS META-ENGINEERING.

You are NOT the PTX formalizer.

You are the software/research engineer responsible for improving the
Spec2Lean engine and its OpenCode-based agentic loop.

This distinction is fundamental.

The intended division of labor is:

CODEX:
- understands and edits the Spec2Lean repository
- improves the TypeScript orchestrator
- improves OpenCode agent definitions and prompts
- improves OpenCode tools
- builds deterministic infrastructure
- builds source indexes and caches
- builds reusable language-pack infrastructure
- builds reusable IR/schema infrastructure
- improves session/runtime lifecycle
- improves retry/recovery logic
- improves telemetry and benchmarking
- refactors framework-level reusable Lean code when necessary
- builds reusable generic Lean theorem libraries
- creates regression tests
- runs tests
- benchmarks the REAL OpenCode-driven loop

OPENCODE AGENTS:
- inspect unit-specific official specification evidence
- create unit-specific source bundles
- interpret unit-specific semantics
- critique source faithfulness
- generate unit-specific Lean formalizations
- generate unit-specific theorem obligations
- prove approved unit-specific theorems
- repair unit-specific technical failures

Codex MUST NOT replace those OpenCode agents for new benchmark units.

For a NEW PTX benchmark instruction, Codex must NOT directly hand-write:

- its semantic artifact
- its unit-specific Lean semantics file
- its theorem-obligation artifact
- its proof file
- its accepted artifact set

Doing so would invalidate the performance benchmark.

The success criterion is NOT:

    "Codex can formalize PTX instructions."

The success criterion IS:

    "Codex improves the Spec2Lean engine so that the OpenCode agentic loop
     itself can formalize a previously unseen PTX instruction correctly,
     traceably, and much faster."

Codex MAY edit reusable framework-level Lean infrastructure such as:

- Spec2Lean.PTX.Core
- shared state/guard/register types
- generic execution abstractions
- generic proof libraries
- generic theorem schemas
- test fixtures

But it must not bypass the OpenCode formalization workflow for new units.

======================================================================
1. PROJECT MISSION
======================================================================

Spec2Lean is intended to become a general-purpose, agentic,
human-in-the-loop, verification-guided, source-traceable system that reads
official language/ISA specifications from PDF or HTML and produces Lean 4
formalizations.

PTX ISA 9.3 is the first case study.

The long-term vision is broader than PTX.

Eventually the system should support multiple language/specification packs,
including examples such as:

- PTX
- SPIR-V
- C
- possibly other ISAs/languages later

The repository already contains language-pack directories such as:

    language_packs/
        ptx/
        spirv/
        c/

The eventual system should have at least two modes.

----------------------------------------------------------------------
1.1 Formalization Mode
----------------------------------------------------------------------

Input:

    official language/ISA specification
    + target bounded construct/unit

Output:

    source evidence
    -> explicit semantic interpretation
    -> Lean formal model
    -> theorem obligations
    -> machine-checked proofs
    -> traceability artifacts
    -> human-review artifacts
    -> accepted formalization

----------------------------------------------------------------------
1.2 Translation Mode
----------------------------------------------------------------------

Longer-term goal:

    formally represent multiple source/target languages
    and reason about translation correctness between them.

Translation Mode is not the current optimization target, but the architecture
should not make it impossible later.

======================================================================
2. THREE DIFFERENT NOTIONS OF CORRECTNESS
======================================================================

Spec2Lean deliberately distinguishes three notions of correctness.

This distinction must NEVER be collapsed.

----------------------------------------------------------------------
2.1 Source faithfulness
----------------------------------------------------------------------

Question:

    Does the formal model actually correspond to the official specification?

This is established through:

- official-source evidence
- evidence fragments
- explicit semantic claims
- claim classification
- independent semantic critique
- assumptions/open questions
- human review

Lean alone cannot establish source faithfulness.

----------------------------------------------------------------------
2.2 Internal formal correctness
----------------------------------------------------------------------

Question:

    Given the formal model, are its definitions/theorems internally correct?

This is established through:

- Lean elaboration
- Lean compilation
- Lean proof terms
- kernel checking
- executable examples
- theorem proofs

Lean is authoritative for this layer.

----------------------------------------------------------------------
2.3 Translation correctness
----------------------------------------------------------------------

Future question:

    Does a translation between two formalized languages preserve the intended
    semantics?

This is a later project phase.

======================================================================
3. NON-NEGOTIABLE VERIFICATION RULES
======================================================================

Never improve runtime by weakening verification.

The project forbids:

- `sorry`
- `admit`
- introducing new `axiom`s
- `unsafe` verification bypasses
- theorem weakening
- silently adding hypotheses merely to make a theorem provable
- vacuous theorems
- circular theorems
- meaningless determinism statements
- semantic invention
- claiming missing source evidence exists
- converting an OPEN_QUESTION into a SOURCE_FACT without evidence
- presenting a project design decision as an NVIDIA source fact
- silently broadening a bounded formalization beyond its approved scope

If an approved theorem cannot be proved without weakening semantics,
the correct response is BLOCKED/review, not theorem mutation.

======================================================================
4. SEMANTIC CLAIM CLASSIFICATION
======================================================================

Semantic interpretation explicitly distinguishes categories such as:

- SOURCE_FACT
- DERIVED_INTERPRETATION
- DESIGN_DEPENDENCY
- ASSUMPTION
- OPEN_QUESTION

These categories matter scientifically.

Examples:

SOURCE_FACT:
    directly stated by official NVIDIA PTX text.

DERIVED_INTERPRETATION:
    supported by source facts but requires an interpretive step.

DESIGN_DEPENDENCY:
    a formalization/modeling choice required to create a bounded Lean model.

ASSUMPTION:
    human-approved assumption that is not established by the official source.

OPEN_QUESTION:
    unresolved point that must not be silently invented.

Do not erase this classification merely to simplify the IR.

======================================================================
5. HUMAN-IN-THE-LOOP MODEL
======================================================================

The workflow contains explicit human gates.

Agents are NOT allowed to approve these gates themselves.

----------------------------------------------------------------------
Gate A
----------------------------------------------------------------------

Approves:

- bounded formalization scope
- architecture
- modeling boundaries
- important assumptions/open questions

----------------------------------------------------------------------
Gate B
----------------------------------------------------------------------

Approves:

- semantic interpretation
- source-evidence mapping
- assumptions/derived interpretations
- state behavior

----------------------------------------------------------------------
Gate C
----------------------------------------------------------------------

Approves:

- semantic-to-Lean mapping

----------------------------------------------------------------------
THEOREM_STRENGTH
----------------------------------------------------------------------

Approves:

- theorem statements
- hypotheses
- theorem strength
- non-vacuity
- intended proof obligations

This occurs BEFORE proof generation.

----------------------------------------------------------------------
FINAL
----------------------------------------------------------------------

Approves:

- complete source -> semantics -> Lean -> theorem -> proof chain.

A temporary benchmark-only auto-approval script has been used during
performance experiments.

That script exists ONLY to measure unattended end-to-end execution.

Do NOT interpret benchmark auto-approval as a requirement to remove human
gates from the real system.

For normal operation, human gates remain part of the research methodology.

======================================================================
6. OPENCODE IS THE ACTUAL AGENT EXECUTION PLATFORM
======================================================================

The current formalization agents run through OpenCode.

OpenCode version observed during development was around 1.18.x.

The active model used in experiments has been:

    opencode/deepseek-v4-flash-free

The model itself was benchmarked separately.

Observed simple model latency:

    min    ~2.2 s
    median ~6.25 s
    mean   ~6.66 s
    max    ~10.55 s

Therefore the multi-hour formalization runtime is NOT explained by raw model
latency alone.

The engine invokes OpenCode agents through the OpenCode SDK/server.

The project previously moved from synchronous prompting to asynchronous
sessions using:

    prompt_async
    + message polling
    + session status polling

because synchronous calls could hit request/header timeout behavior.

======================================================================
7. CURRENT OPENCODE SUBAGENTS
======================================================================

The repository has specialized agent definitions under:

    .opencode/agents/

Core roles include:

----------------------------------------------------------------------
7.1 spec-manager
----------------------------------------------------------------------

Workflow/coordination-oriented role.

Historically also used in some human-review recording flows.

This use should be examined because explicit human gate recording should
probably become deterministic and not require LLM reasoning.

----------------------------------------------------------------------
7.2 spec-architect
----------------------------------------------------------------------

Responsible for:

- defining bounded scope
- identifying semantic components
- defining architecture
- identifying assumptions
- identifying open questions
- identifying validation/proof families

Does NOT approve Gate A.

----------------------------------------------------------------------
7.3 source-curator
----------------------------------------------------------------------

Responsible for:

- official-source-only evidence
- source fragments
- anchors
- exact quotations
- PDF pages
- hashes
- evidence gaps

Must NOT interpret semantics.

Must NOT write Lean.

Must NOT invent missing facts.

----------------------------------------------------------------------
7.4 semantic-extractor
----------------------------------------------------------------------

Responsible for:

- turning curated evidence into explicit semantics
- state reads/writes
- operand roles
- typing
- guard behavior
- error/undefined behavior when supported
- assumptions
- derived interpretations
- open questions
- semantic pseudocode

Must NOT reacquire a new source corpus.

Must NOT write Lean.

----------------------------------------------------------------------
7.5 semantic-critic
----------------------------------------------------------------------

Used for multiple independent review stages including:

- architecture critique
- semantic critique
- Lean mapping critique
- theorem-strength critique
- final critique

This broad reuse has become a performance concern because the critic often
rechecks large amounts of already-reviewed information.

A future optimization should preserve independence while making reviews
delta-focused rather than repeatedly reviewing the full chain.

----------------------------------------------------------------------
7.6 lean-formalizer
----------------------------------------------------------------------

Responsible for:

- implementing Gate-B-approved semantics in Lean
- generating theorem obligations at the appropriate stage
- using Lean verification tools
- preserving semantics
- avoiding forbidden constructs

----------------------------------------------------------------------
7.7 proof-engineer
----------------------------------------------------------------------

Responsible for:

- proving human-approved theorem statements
- compiler-driven proof repair
- using Lean diagnostics
- preserving theorem statements
- reporting genuine theorem/semantic conflicts instead of weakening them

Proof strategy was previously changed to execution-first because the model
once spent extremely large context/reasoning effort planning proof tactics
without writing a proof.

----------------------------------------------------------------------
7.8 repair-agent
----------------------------------------------------------------------

Used for bounded technical repairs.

Must not silently change semantics.

======================================================================
8. REPOSITORY STRUCTURE
======================================================================

The repository root is approximately structured as:

    engine/
    documents/
    ir/
    language_packs/
    .opencode/
    lean/
    runs/
    candidates/
    accepted/
    reviews/
    evaluation/
    tests/
    AGENTS.md
    opencode.json
    spec2lean

Important areas:

----------------------------------------------------------------------
engine/orchestrator/
----------------------------------------------------------------------

TypeScript orchestration engine.

----------------------------------------------------------------------
documents/
----------------------------------------------------------------------

Official specification source manifests and raw documents.

Raw PDFs/HTML may be gitignored.

----------------------------------------------------------------------
ir/
----------------------------------------------------------------------

Intended location for shared intermediate representations.

Historically underdeveloped/mostly empty.

This is now a major target for Performance Architecture v2.

----------------------------------------------------------------------
language_packs/
----------------------------------------------------------------------

Intended location for reusable language-specific knowledge.

Historically underdeveloped/mostly empty.

This is now a major target for Performance Architecture v2.

----------------------------------------------------------------------
lean/
----------------------------------------------------------------------

Lean package.

----------------------------------------------------------------------
runs/
----------------------------------------------------------------------

Persistent run state.

----------------------------------------------------------------------
candidates/
----------------------------------------------------------------------

Immutable candidate artifacts per unit/stage/revision.

----------------------------------------------------------------------
accepted/
----------------------------------------------------------------------

Human-approved final artifacts.

----------------------------------------------------------------------
reviews/
----------------------------------------------------------------------

Human approval/rejection records and other review artifacts.

----------------------------------------------------------------------
evaluation/
----------------------------------------------------------------------

Performance and correctness baselines.

======================================================================
9. CURRENT ORCHESTRATOR STATE MACHINE
======================================================================

The current formalization state machine includes stages equivalent to:

    CREATED

    ARCHITECTURE
    ARCHITECTURE_CRITIQUE
    WAITING_GATE_A

    SOURCE_CURATION
    SEMANTIC_EXTRACTION
    SEMANTIC_CRITIQUE
    WAITING_GATE_B

    LEAN_FORMALIZATION
    LEAN_MAPPING_CRITIQUE
    WAITING_GATE_C

    THEOREM_GENERATION
    THEOREM_STRENGTH_CRITIQUE
    WAITING_THEOREM_STRENGTH_APPROVAL

    PROOF_GENERATION

    FINAL_CRITIQUE
    WAITING_FINAL_APPROVAL

    ACCEPTED
    BLOCKED
    FAILED

The exact implementation is under:

    engine/orchestrator/src/workflow.ts
    engine/orchestrator/src/stage-plan.ts

Inspect actual code before making assumptions.

======================================================================
10. PERSISTENT RUN MODEL
======================================================================

Each run has persistent state under something like:

    runs/<run-id>/run.json

State includes:

- run ID
- mode
- language
- specification version
- unit
- unit slug
- Lean module name
- source manifest
- artifact root
- stage
- timestamps
- revision
- human gate statuses
- transition history
- agent execution history
- optionally active execution/session

The system is intended to be resumable after crashes or interrupted agents.

======================================================================
11. ARTIFACT CONTRACTS
======================================================================

The orchestrator uses immutable versioned artifacts.

Per-unit artifact roots look roughly like:

    candidates/ptx/9.3/units/<unit-slug>/

with subdirectories such as:

    architecture/
    source-bundles/
    semantics/
    lean/
    theorems/
    reviews/

The orchestrator calculates expected artifact paths and verifies that a
SUCCESS result actually produced the required artifact.

An LLM textual "SUCCESS" is not trusted by itself.

Deterministic artifact verification should outrank model self-reporting.

======================================================================
12. SOURCE MATERIAL
======================================================================

The first case study uses official NVIDIA PTX ISA 9.3.

Manifest:

    documents/sources/nvidia/ptx/9.3/source-manifest.json

Known official local artifacts have included:

HTML:
    documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.html

PDF:
    documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.pdf

Known SHA-256 values from the project history:

HTML:
    e2095c4ae00fe81fa18325b8e26c4a41b94965295c7affd7ff7f787fd98a8856

PDF:
    769cc12e363e7bb9cd311464f2a42edbdaf4c74ca18575de8c358e93223434fc

Raw files may be absent in some checkouts.

Do not silently substitute unofficial internet material.

======================================================================
13. SOURCE TOOLS
======================================================================

OpenCode tools under:

    .opencode/tools/

have included mechanisms such as:

- spec_search
- spec_read_span
- spec_get_context
- PDF search/read tools
- candidate_read
- candidate_write
- candidate_diff
- Lean checking/diagnostic tools
- review submission tools

Historically, source search tools repeatedly read/scan the same full PTX
source file.

PDF search could repeatedly run pdftotext.

This was identified as unnecessary overhead.

A deterministic PTX source index and `spec_fast_context` fast path were later
introduced.

Inspect their current implementation.

======================================================================
14. COMPLETED / EXPERIMENTAL PTX UNITS
======================================================================

Several PTX units have been formalized during development.

Inspect `accepted/`, `runs/`, and git history for authoritative status.

Important historical units include:

----------------------------------------------------------------------
14.1 add.u32
----------------------------------------------------------------------

First major case study.

Important lesson:

The exact overflow/modulo-2^32 behavior was not treated as an NVIDIA source
fact.

It required a human-approved project assumption.

This is an important example of the project's source-faithfulness discipline.

The unit ultimately included:

- architecture
- source bundles
- semantic interpretation
- human assumption record
- Lean model
- theorem obligations
- proofs
- final critique

----------------------------------------------------------------------
14.2 mov.b32
----------------------------------------------------------------------

Important lessons included:

- false-guard behavior was initially under-supported
- a general PTX predication clause was later found:
  "Threads with a False guard predicate do nothing."
- guard-false no-op was then treated as a derived interpretation from general
  PTX behavior, not as a mov-specific verbatim source fact

Another technical issue:

MovB32 originally collided with AddU32 because each unit independently
declared shared names such as RegId, PredId, MachineState.

MovB32 was temporarily isolated in its own namespace.

This collision was one of the signals that PTX shared Core infrastructure was
needed.

----------------------------------------------------------------------
14.3 not.b32
----------------------------------------------------------------------

Used as the first real unattended/auto-approved loop test.

The loop successfully performed:

- architecture creation
- architecture critique/revision
- source curation
- semantic extraction
- semantic critique
- Lean generation
- Lean critique
- theorem generation
- theorem-strength review
- proof generation
- final critique
- acceptance

However the proof stage exposed a retry-policy bug.

Proof generation initially worked approximately one theorem per invocation.

The loop incorrectly counted progress-making RETRY outcomes as stalled retries.

The retry scheduler was then modified to recognize proof progress.

not.b32 eventually reached ACCEPTED.

----------------------------------------------------------------------
14.4 xor.b32
----------------------------------------------------------------------

Used as a later performance benchmark after:

- proof batching
- performance telemetry
- initial source indexing optimizations

xor.b32 also reached ACCEPTED.

----------------------------------------------------------------------
14.5 and.b32
----------------------------------------------------------------------

Used to test additional fast source/semantic experiments.

It eventually reached ACCEPTED.

Its final review reported no blocker/major/minor issue and its Lean/proof chain
compiled.

However its runtime exposed serious remaining performance problems.

======================================================================
15. LEAN ENVIRONMENT
======================================================================

Observed environment:

    Lean 4.32.2
    Lake 5.0.0

Toolchain:

    leanprover/lean4:v4.32.2

Lean package root:

    lean/

Root module:

    lean/Spec2Lean.lean

Main PTX modules have included:

    AddU32.lean
    AddU32Proofs.lean
    MovB32.lean
    MovB32Proofs.lean
    NotB32.lean
    NotB32Proofs.lean
    XorB32.lean
    XorB32Proofs.lean
    AndB32.lean
    AndB32Proofs.lean

The existing Lean work has generally been technically strong.

Do not assume that because runtime is bad the Lean artifacts are bad.

The Lean compiler/kernel has repeatedly rejected invalid refactor attempts
rather than silently accepting them, which is expected and desirable.

======================================================================
16. IMPORTANT LEAN TRUST BOUNDARY
======================================================================

The existing Lean files can be trusted for:

    "these theorems follow from this formal model"

when they compile and contain no bypasses.

They do NOT independently establish:

    "this model is exactly what NVIDIA meant"

That second statement depends on:

- official source evidence
- semantic interpretation
- critic review
- human decisions

Preserve both layers.

======================================================================
17. PERFORMANCE BASELINES
======================================================================

Performance became the main engineering problem.

The project owner and supervisor both believe a simple instruction over an
already-ingested PTX specification should normally complete in approximately
1-3 minutes on the warm path.

This is not a hard timeout for genuinely difficult units.

A source ambiguity, missing evidence, semantic conflict, or hard proof may
legitimately trigger a slower path.

----------------------------------------------------------------------
17.1 not.b32 baseline
----------------------------------------------------------------------

Approximately:

    wall clock:       12,239 seconds
    agent executions: 31
    retry executions: 18

Proof stage alone:

    ~6,776 seconds
    ~17 proof executions

This was obviously unacceptable for a simple NOT instruction.

----------------------------------------------------------------------
17.2 xor.b32 benchmark
----------------------------------------------------------------------

After early optimization:

    wall clock:       ~5,231 seconds
    agent executions: 14
    retry executions: 3

Major stages included roughly:

    semantic extraction ~1,232 s
    source curation      ~992 s
    proof generation     ~424 s
    theorem critique     ~414 s
    semantic critique    ~295 s
    Lean generation      ~288 s
    Lean mapping critique~289 s
    final critique       ~221 s

Proof batching drastically reduced proof invocation count.

But runtime remained far too large.

----------------------------------------------------------------------
17.3 and.b32 benchmark
----------------------------------------------------------------------

Approximately:

    wall clock:       ~6,590 seconds
    agent executions: 18
    retry executions: 5

Major stages:

    semantic extraction ~2,699 s
    proof generation     ~907 s
    source curation      ~452 s
    semantic critique    ~412 s
    architecture         ~390 s
    architecture critique~348 s
    Lean mapping critique~328 s
    theorem critique     ~321 s
    theorem generation   ~210 s
    final critique       ~193 s
    Lean formalization   ~191 s

Again, unacceptable for a simple bitwise AND instruction.

======================================================================
18. PERFORMANCE LESSON: MODEL LATENCY IS NOT THE MAIN PROBLEM
======================================================================

Direct five-run model benchmark of:

    opencode/deepseek-v4-flash-free

gave approximately:

    10.55 s
    6.25 s
    2.20 s
    8.63 s
    5.69 s

median:

    ~6.25 s

mean:

    ~6.66 s

Therefore a 1-2 hour pipeline is mostly orchestration/repeated-work overhead,
not merely provider response latency.

Do not prematurely solve the problem by changing the model.

Provider/model benchmarking is fine later, but first eliminate architectural
waste.

======================================================================
19. PERFORMANCE WORK ALREADY ATTEMPTED
======================================================================

Several optimizations have already been tried.

Understand which ones exist in the current repo before duplicating them.

----------------------------------------------------------------------
19.1 Async OpenCode transport
----------------------------------------------------------------------

The orchestrator moved to async sessions:

    prompt_async
    -> poll messages/status

This fixed earlier timeout/header issues.

----------------------------------------------------------------------
19.2 Tolerant result protocol / recovery
----------------------------------------------------------------------

Agents sometimes fail to emit a valid final:

    SPEC2LEAN_RESULT {...}

The parser/recovery system was made more tolerant.

A separate protocol-recovery session may classify an otherwise completed
attempt.

This itself may be a source of overhead.

----------------------------------------------------------------------
19.3 Artifact verification
----------------------------------------------------------------------

The orchestrator verifies required artifacts after model SUCCESS.

This is good and should stay.

----------------------------------------------------------------------
19.4 Proof execution-first discipline
----------------------------------------------------------------------

The Proof Engineer previously spent excessive reasoning/context planning proof
tactics before writing code.

Agent instructions were changed to:

    write early
    compile
    inspect diagnostics
    repair concrete failures

This is correct direction.

----------------------------------------------------------------------
19.5 Proof batching
----------------------------------------------------------------------

Originally one theorem could require one expensive proof-agent invocation.

For not.b32 this led to many repeated proof sessions.

Proof generation was later changed to batch many remaining approved theorem
statements.

This reduced invocation count substantially.

However all-theorems-in-one-session can still take many minutes.

The next design should prefer ADAPTIVE BATCHING:

    small bounded batch
    -> Lean check
    -> repair only failing batch

Avoid both extremes:

    one theorem per LLM call
    all theorems in one giant uncontrolled call

----------------------------------------------------------------------
19.6 Progress-aware retry handling
----------------------------------------------------------------------

The run loop was modified so proof-generation RETRY outcomes that actually add
new theorem declarations do not count as stalled retries.

Good idea; preserve the concept.

----------------------------------------------------------------------
19.7 Performance reporting
----------------------------------------------------------------------

A `perf-report` command was added.

It reports things like:

- total wall-clock
- per-stage duration
- execution count
- retry count

Telemetry is still incomplete.

----------------------------------------------------------------------
19.8 PTX deterministic source index
----------------------------------------------------------------------

A PTX source index was introduced under a local cache.

Goal:

    ingest official PTX once
    then retrieve bounded sections cheaply

This is the correct architectural direction.

----------------------------------------------------------------------
19.9 spec_fast_context
----------------------------------------------------------------------

A fast OpenCode source tool was added.

It returns:

- target instruction section
- shared contexts
- source hash verification

It is intended to reduce repeated broad searching.

This helped, but the tool/context design may still send too much duplicated
HTML/text to agents.

----------------------------------------------------------------------
19.10 Fast source-curator / semantic-extractor experiments
----------------------------------------------------------------------

Experimental fast agents were introduced.

The source fast path sometimes performed well.

Example:

    and.b32 source-curator-fast created a bounded source bundle in roughly
    around one minute.

However the fast Semantic Extractor repeatedly failed by:

- announcing an intention to write
- not actually writing the artifact
- returning an incomplete protocol template

Therefore "make a smaller prompt/step budget" is NOT sufficient.

Do not continue stacking more prompt-only fast agents.

======================================================================
20. WHAT THE PERFORMANCE EXPERIMENTS REVEALED
======================================================================

The central problem is architectural duplication.

Spec2Lean currently behaves too much like:

    "repeat the entire research workflow from scratch for every instruction"

instead of:

    "compile a small instruction-specific delta against an already-ingested,
     reviewed, formalized PTX language model."

This must change.

======================================================================
21. MAJOR ARCHITECTURAL DUPLICATION
======================================================================

Across simple PTX units such as:

- mov.b32
- not.b32
- xor.b32
- and.b32

a large amount of content is repeated.

Examples of shared Lean concepts:

- B32
- bit width/domain size
- RegId
- PredId
- Destination
- Guard
- MachineState
- evalGuard
- updateDestination
- ExecOutcome
- mkB32
- state constructors

These should not be regenerated for every instruction.

Likewise generic semantics repeat:

- `.b32` width
- register representation
- predicate representation
- guard semantics
- false-guard behavior
- bit-bucket behavior
- partial state lookup conventions
- minimal state model
- frame conventions

Likewise generic proofs repeat:

- guard evaluation theorems
- destination write behavior
- unrelated-register frame properties
- predicate-file preservation
- bit-bucket state preservation
- generic execution relation/function correspondence patterns

These should not be reproved independently for every instruction.

======================================================================
22. HUGE PER-UNIT ARTIFACTS
======================================================================

Simple instructions have historically produced surprisingly large artifact
chains.

Semantic artifacts can contain around 70+ claims and exceed ~100 KB.

Architecture artifacts can also be tens of KB.

Theorem-obligation artifacts can be large.

Then critics reread these artifacts.

Then revisions sometimes regenerate nearly the entire artifact just to change a
small semantic point.

This is a major performance anti-pattern.

A future architecture should represent:

    shared language semantics
    +
    instruction-specific delta

not duplicate the full shared semantics inside every unit.

======================================================================
23. LANGUAGE PACKS AND IR ARE CURRENTLY UNDERUSED
======================================================================

The repository already conceptually anticipated:

    language_packs/
    ir/

but historically these were largely empty/underdeveloped.

This is now the obvious home for Performance Architecture v2.

Potential structure:

    language_packs/ptx/9.3/
        architecture/
        shared-evidence/
        shared-semantics/
        theorem-families/
        policies/

    ir/ptx/
        unit-delta.schema.json
        semantic-delta.schema.json
        theorem-delta.schema.json

Do not blindly copy this exact shape if a better design emerges.

But the principle is required:

    common PTX knowledge must be reusable and versioned.

======================================================================
24. PTX LEAN CORE REFACTOR
======================================================================

A refactor has begun to extract common Lean machinery.

Inspect current files.

Likely files include:

    lean/Spec2Lean/PTX/Core.lean
    lean/Spec2Lean/PTX/CoreProofs.lean

The intended Core contains common definitions such as:

- b32Bits
- b32DomainSize
- B32
- RegId
- PredId
- Destination
- Guard
- MachineState
- evalGuard
- updateDestination
- ExecOutcome
- mkB32
- mkState

CoreProofs contains reusable properties such as:

- evalGuard_unguarded_true
- evalGuard_atPos_true
- evalGuard_atPos_false
- evalGuard_atNeg_true_when_pred_false
- evalGuard_atNeg_false_when_pred_true

Additional generic destination-update theorems are the correct next direction.

Conceptually useful lemmas include:

    updateDestination_reg_same
    updateDestination_reg_other
    updateDestination_reg_pred_unchanged
    updateDestination_bitBucket_preserves_state

======================================================================
25. AND.B32 CANARY MIGRATION
======================================================================

AndB32 is being used as a canary for Core migration.

The migration goal is:

    preserve behavior
    preserve theorem API/strength
    reuse Core implementation

Instead of maintaining independent copies of:

    B32
    RegId
    PredId
    Guard
    Destination
    MachineState
    evalGuard
    updateDestination

AndB32 should reuse the shared Core.

Compatibility aliases may temporarily preserve old names.

Important observed result:

After rebuilding the Core-migrated AndB32 module, all 17 executable examples
continued producing the expected outputs.

However AndB32Proofs initially failed.

The first failure was a type mismatch caused by stale build artifacts.

After rebuilding dependencies, that type mismatch disappeared.

Remaining proof failures were implementation-level proof-script failures such
as:

    goal:
      updateDestination ... .valueRegs r = some value

    goal:
      unrelated register remains unchanged

    goal:
      predicate register remains unchanged

    goal:
      bit-bucket update returns original state

This is exactly why these should become CoreProofs lemmas.

Do NOT solve these failures by:

- casts
- theorem weakening
- reintroducing duplicate implementation
- unsafe tricks

The correct fix is reusable Core theorem abstraction.

Inspect current build state because the repository may already have progressed
beyond this description.

======================================================================
26. BASELINE / REGRESSION POLICY
======================================================================

Before Performance Architecture v2 work, pre-v2 baselines were created under:

    evaluation/baselines/

They may include:

- Lean SHA-256 fingerprints
- theorem counts
- forbidden-token checks
- not.b32 performance report
- xor.b32 performance report
- and.b32 performance report

Use them.

For Lean refactors, success requires:

- `lake build` green
- no new `sorry`
- no new `admit`
- no new axiom
- no unsafe verification bypass
- executable examples unchanged
- theorem statements/strength preserved unless explicitly reviewed
- source semantics not silently changed

Implementation refactoring is allowed.

Semantic weakening is not.

======================================================================
27. GATE APPROVAL RECORDING IS PROBABLY TOO EXPENSIVE
======================================================================

Inspect the current approval implementation.

Historically:

    ./spec2lean approve --run ... --gate ...

could involve an OpenCode/spec-manager session just to write a review record.

This is conceptually unnecessary.

Once a human explicitly executes an approval command, the decision is already
made.

The software can deterministically write a structured signed/hashed approval
record from:

- run ID
- gate
- latest reviewed artifact hashes
- timestamp
- decision
- optional rationale

No additional LLM reasoning is necessary merely to record the user's decision.

This could save multiple serial LLM calls per run.

Do NOT remove review gates.

Only eliminate unnecessary LLM work used to RECORD a human decision.

======================================================================
28. OPENCODE RUNTIME LIFECYCLE MAY BE WASTEFUL
======================================================================

Inspect current runner/run-loop behavior carefully.

Historically the loop spawned a separate tick process for each stage.

Each runner could start OpenCode, execute one stage, and then shut it down.

If this is still true, it causes:

- repeated process startup
- repeated server startup
- loss of in-memory caches
- loss of connection/session reuse
- extra latency

The preferred architecture may be:

    one orchestrator process
    one OpenCode runtime/server
    multiple stage sessions

for the lifetime of a run.

Do not implement this blindly without checking OpenCode SDK lifecycle and
crash recovery requirements.

Persistent runtime must not destroy resumability.

======================================================================
29. SOURCE FAST-PATH SHOULD BE DETERMINISTIC, NOT JUST PROMPT-BASED
======================================================================

The goal is:

    official source
        ↓ one-time ingestion
    versioned/indexed facts
        ↓
    unit-specific deterministic retrieval
        ↓
    LLM only handles genuine interpretation

A source agent should not repeatedly search the full PTX manual for:

- `.b32` width
- general predication
- register model
- bit-bucket rules
- universal instruction rules

if those have already been reviewed and versioned.

However instruction-specific source facts must still be traceable to official
source locations and hashes.

======================================================================
30. SHARED SEMANTIC IR
======================================================================

This is a major missing component.

A simple instruction should NOT produce ~70 mostly-repeated semantic claims
from scratch.

Instead think in terms of:

    PTX shared semantic environment
        +
    instruction-specific semantic delta

Example shared semantics:

    B32 = 32-bit bit domain
    register model
    predicate model
    guard evaluation
    false-guard no-op derivation
    state-frame model
    partial lookup convention
    destination model
    common evidence references

Example `and.b32` delta:

    instruction syntax
    operand roles
    source-b legality
    bitwise-AND semantic operator
    instruction-specific examples
    instruction-specific ambiguity
    instruction-specific restrictions

Critics should review the DELTA plus any risky dependency edges.

They should not rereview 70 unchanged facts every time.

======================================================================
31. DELTA CRITICS
======================================================================

Independent semantic criticism is a core quality property and must remain.

But independence does NOT mean:

    reread every accepted shared fact from scratch for every instruction.

A better critic input could be conceptually:

    55 shared claims
        immutable
        previously human-approved
        hash verified

    10 deterministic instantiated claims
        schema checked

    5 new source facts
        review

    3 derived interpretations
        deep review

    2 open questions
        deep review

The critic should independently evaluate new/derived/risky content.

If a shared dependency changed, invalidate/review affected units.

======================================================================
32. GENERIC THEOREM LIBRARY
======================================================================

Many theorem obligations are generic.

Examples:

- guard false preserves state
- guard positive behavior
- guard negative behavior
- destination register gets written value
- unrelated registers preserved
- predicate registers preserved
- bit bucket preserves state
- relational/function correspondence schemas

These should be proved once when possible.

A new instruction should instantiate generic theorems and only require new
proofs for genuinely instruction-specific semantic content.

Do not mechanically force everything into generic abstraction if that makes
proofs opaque or brittle.

But obvious repeated structural theorems should be reused.

======================================================================
33. ADAPTIVE PROOF BATCHING
======================================================================

Historical bad design #1:

    1 theorem
    -> 1 LLM session
    repeated ~16 times

Historical bad design #2:

    all 16 theorems
    -> one huge LLM proof session
    could still take ~15 minutes

Desired design:

    frozen theorem set
       ↓
    classify generic/reusable vs residual
       ↓
    generic obligations discharged deterministically/library reuse
       ↓
    remaining proof targets grouped into small batches
       ↓
    LLM writes proof batch
       ↓
    Lean compile
       ↓
    only failing declarations/batch repaired

Possible batch size might be around 3-6 but must be empirically determined.

Do not hard-code a number purely from intuition.

Measure.

======================================================================
34. TELEMETRY REQUIREMENTS
======================================================================

Current performance reporting is useful but insufficient.

A research-quality performance system should ideally track:

Per run:
- total wall time

Per stage:
- start time
- end time
- duration
- outcome

Per LLM call:
- agent
- model
- prompt size/tokens if available
- output size/tokens if available
- duration
- retry/provider events

Per tool:
- tool call count
- tool time where feasible

Lean:
- compile/check duration
- proof repair rounds

Artifacts:
- bytes generated
- revisions generated

Caching:
- cache hits
- cache misses

Workflow:
- stage transitions
- revision loops
- reason for fallback

Then optimizations can be scientifically justified.

======================================================================
35. PRIMARY PERFORMANCE TARGET
======================================================================

For a SIMPLE PTX instruction over an ALREADY-INGESTED PTX 9.3 environment:

Desired mature warm path:

    approximately 1-3 minutes

An early intermediate target <= 5 minutes is acceptable while the architecture
is being refactored.

This is NOT a universal hard timeout.

Slow fallback is allowed for:

- missing source evidence
- specification ambiguity
- conflicting evidence
- new architectural feature
- difficult theorem
- proof failure
- human rejection/revision

Quality takes precedence over blindly meeting a stopwatch target.

======================================================================
36. WHAT MUST NOT BE DONE TO HIT THE PERFORMANCE TARGET
======================================================================

Do NOT obtain 1-3 minute runtime by:

- skipping source traceability
- deleting semantic criticism
- removing theorem-strength review
- removing Lean proof checking
- adding `sorry`
- adding axioms
- weakening theorem statements
- hardcoding benchmark instruction semantics
- prewriting benchmark Lean files
- letting Codex itself produce benchmark-unit artifacts
- suppressing errors
- silently treating unknown facts as assumptions
- reducing every agent to superficial output

The correct improvement is architectural reuse.

======================================================================
37. DESIRED FINAL USER EXPERIENCE
======================================================================

The user eventually wants something close to:

    ./spec2lean formalize \
      --language ptx \
      --version 9.3 \
      --unit <instruction>

Then Spec2Lean/OpenCode should autonomously proceed until:

- a genuine human gate
- a genuine semantic conflict
- a genuine source gap
- a genuine proof blocker
- final completion

For benchmark-only automation, a flag such as:

    --auto-approve

could eventually automate human gates.

But normal mode remains human-in-the-loop.

The user does NOT want to manually run:

    npm run tick
    hand-edit run.json
    inspect individual sessions
    repeatedly repair trivial protocol failures

Those are implementation details the engine should absorb.

======================================================================
38. FINALIZATION / GIT MILESTONES
======================================================================

The system has a `finalize` flow intended to:

- promote artifacts
- generate accepted manifest
- commit
- optionally push

Example:

    ./spec2lean finalize --run <run-id> --push

This workflow has already been used successfully for accepted PTX units.

Preserve reproducible finalization.

======================================================================
39. CURRENT DEVELOPMENT BRANCH / HISTORY
======================================================================

The project has used feature/performance branches such as:

    perf/hot-path-v1
    perf/architecture-v2

Do not assume exact branch names.

Run:

    git branch --show-current
    git status --short
    git log --oneline --decorate -20

before editing.

Several meaningful historical commits include work around:

- accepting mov.b32
- orchestrator hardening
- accepting not.b32
- batching Lean proofs
- indexed PTX retrieval
- fast-first experiments
- progress-aware proof retries
- accepting xor.b32
- accepting and.b32
- freezing pre-v2 baselines
- PTX Core extraction

Use git history as evidence.

======================================================================
40. FIRST THING YOU MUST DO
======================================================================

Do not start coding immediately.

Perform a repository-wide audit.

Read at minimum:

    AGENTS.md
    CODEX_HANDOFF.md
    README files

    spec2lean
    opencode.json

    .opencode/agents/
    .opencode/tools/

    engine/orchestrator/package.json
    engine/orchestrator/src/

    lean/lean-toolchain
    lean/lakefile.*
    lean/Spec2Lean.lean
    lean/Spec2Lean/
    lean/Spec2Lean/PTX/

    documents/sources/nvidia/ptx/9.3/source-manifest.json

    language_packs/
    ir/

    evaluation/baselines/

    representative accepted units:
        add-u32
        mov-b32
        not-b32
        xor-b32
        and-b32

    representative runs:
        not.b32
        xor.b32
        and.b32

Inspect only enough historical artifacts to understand the architecture;
do not burn huge context reading every generated artifact in full.

======================================================================
41. RUN BASELINE COMMANDS
======================================================================

Before major refactoring, run appropriate checks such as:

    git branch --show-current
    git status --short
    git log --oneline --decorate -20

TypeScript:

    ./spec2lean typecheck

or equivalent package typecheck.

Self-tests:

    npm --prefix engine/orchestrator run self-test

Lean:

    cd lean
    lake build

Performance baseline files:

    evaluation/baselines/

Inspect current failure state rather than assuming this handoff is current.

======================================================================
42. YOUR REQUIRED INITIAL REPORT
======================================================================

Before making a major rewrite, produce a concise but technically specific
"Spec2Lean Current State Audit".

Include:

1. Current git branch and dirty/untracked state.

2. Which PTX units are actually accepted.

3. Current OpenCode agent architecture.

4. Current orchestrator lifecycle and state machine.

5. Current source-index/cache implementation.

6. Current artifact/revision system.

7. Current proof-generation strategy.

8. Current gate-record implementation.

9. Current Lean module architecture.

10. Whether Core.lean/CoreProofs.lean exist and compile.

11. Exact current AndB32 Core-migration state.

12. Exact current `lake build` result.

13. Current duplicated definitions across PTX units.

14. Current duplicated theorem families.

15. Current state of `language_packs/` and `ir/`.

16. Which Performance Architecture v2 ideas are:
    - already implemented
    - partially implemented
    - not implemented

17. Major discrepancies between this handoff and the actual repository.

18. Your recommended implementation order.

Do not merely repeat this handoff.
Base the audit on repository evidence.

======================================================================
43. IMPLEMENTATION PRIORITY
======================================================================

After the audit, unless repository evidence suggests otherwise, the likely
implementation order should be roughly:

MILESTONE 1
    stabilize current Lean/Core migration
    restore full green `lake build`

MILESTONE 2
    extract reusable PTX Core + CoreProofs properly
    migrate one canary without semantic/theorem regression

MILESTONE 3
    deterministic gate recording
    remove unnecessary LLM calls for explicit human decisions

MILESTONE 4
    persistent OpenCode runtime/session lifecycle
    remove per-stage startup overhead

MILESTONE 5
    real versioned PTX language pack
    shared evidence + shared semantics

MILESTONE 6
    semantic delta IR
    deterministic materialization/validation

MILESTONE 7
    delta-focused critics

MILESTONE 8
    generic theorem library
    adaptive residual proof batching

MILESTONE 9
    stronger telemetry

MILESTONE 10
    benchmark on a PREVIOUSLY UNSEEN simple instruction through the REAL
    OpenCode loop

Do not blindly follow this order if the actual code suggests a dependency
change.

Explain deviations.

======================================================================
44. BENCHMARK INTEGRITY
======================================================================

The eventual benchmark must be a unit not manually preformalized by Codex.

For example, choose a simple PTX unit that is not already accepted and whose
unit-specific artifacts have not been hand-created during optimization.

The benchmark command must go through the real system, conceptually:

    ./spec2lean formalize \
      --language ptx \
      --version 9.3 \
      --unit <UNSEEN_UNIT>

OpenCode subagents must create:

- unit source evidence
- unit semantic delta/interpretation
- unit Lean formalization
- theorem obligations
- residual proofs
- critiques

Codex may observe/debug the engine, but it must not write those unit artifacts
for the benchmark.

======================================================================
45. ACCEPTANCE CRITERIA FOR PERFORMANCE ARCHITECTURE V2
======================================================================

Correctness:

- full Lean package build green
- no new sorry/admit/axiom/unsafe
- source traceability retained
- semantic classifications retained
- explicit assumptions/open questions retained
- theorem strength not weakened
- Lean proofs kernel checked
- critics still capable of blocking bad artifacts
- human gates preserved in normal mode

Maintainability:

- common PTX concepts no longer duplicated per instruction
- shared facts versioned
- unit delta explicit
- reusable theorem library present
- failure/fallback paths understandable

Performance:

For a simple warm PTX instruction:

    target normal runtime ~1-3 minutes

Early architecture milestone:

    <=5 minutes can be accepted as substantial progress

Measure:

- total duration
- agent calls
- retries
- proof rounds
- source time
- semantic time
- critic time
- Lean verification time
- artifact size

Compare to pre-v2 baselines.

======================================================================
46. RESEARCH PRINCIPLE
======================================================================

The scientific argument for the optimization should be:

NOT:

    "we made agents think less."

Instead:

    "we separated invariant, reusable, mechanically verifiable information
     from instruction-specific semantic reasoning."

Spec2Lean should increasingly behave like a compiler pipeline:

    specification ingestion
          ↓
    reviewed language environment
          ↓
    instruction-specific delta
          ↓
    formal IR
          ↓
    Lean generation
          ↓
    generic theorem instantiation
          ↓
    residual proof search
          ↓
    Lean verification

rather than a set of agents repeatedly rediscovering the whole language.

======================================================================
47. IMPORTANT ENGINEERING STYLE
======================================================================

Prefer:

- deterministic validation
- typed schemas
- explicit invariants
- versioned caches
- content hashes
- reproducible artifacts
- clear fallback paths
- small coherent commits
- tests after each meaningful change

Avoid:

- prompt-only hacks
- unexplained magic retry counts
- brittle regexes when structured parsing is available
- hidden semantic assumptions
- massive rewrites without regression protection

======================================================================
48. AUTONOMY
======================================================================

After the initial audit and plan:

Continue implementation autonomously unless you reach:

- an actual semantic decision requiring human judgment
- a source-faithfulness ambiguity
- a theorem-strength decision requiring human approval
- a destructive repository operation
- an architectural choice with materially different research implications

Do not stop after every trivial code edit asking for approval.

The project owner wants the engineering loop to make progress independently.

======================================================================
49. FINAL REMINDER
======================================================================

The most important thing to understand is this:

Spec2Lean is NOT a project whose goal is to manually formalize five PTX
instructions.

Those instructions are experiments for building a GENERAL AGENTIC ENGINE.

The engine must eventually be able to take a new formalization target and
cause specialized OpenCode subagents to:

    retrieve source evidence
    reason about semantics
    construct Lean
    design meaningful theorems
    prove them
    critique the result
    involve humans at the right points

reliably and efficiently.

The current research bottleneck is that too much shared PTX knowledge is
rediscovered and regenerated per instruction.

Your job is to fix THAT ENGINE.

Do not replace it.
