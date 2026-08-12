# Spec2Lean Orchestrator

The orchestrator runs one bounded formalization workflow automatically and
stops only at explicit human-review boundaries, a genuine blocker/failure, or
a bounded retry limit.

The preferred entry point is the repository-root `./spec2lean` wrapper. It
avoids working-directory mistakes and automatically resumes the loop after a
human approve/reject decision.

## One-command start

```bash
./spec2lean formalize --language ptx --version 9.3 --unit mov.b32
```

For PTX, the source manifest is inferred from the specification version. The
run state is persisted under `runs/<run-id>/run.json`, so a closed terminal or
interrupted client does not discard workflow progress.

Before the first run for a language/version, `formalize` verifies the source
manifest and builds a deterministic local retrieval index from pinned HTML or
PDF text. Later runs reuse it only when the manifest and source hashes still
match. This is retrieval-only preprocessing, not model-generated semantics:

```bash
./spec2lean ingest --language <language> --version <version> \
  --source-manifest <repository-relative-source-manifest.json>
```

For an unattended performance benchmark, opt in at run creation:

```bash
./spec2lean formalize --language ptx --version 9.3 --unit <unit> --auto-approve
```

This does not forge human approval. Each boundary gets an immutable,
hash-bound `benchmark_gate_auto_advance` record with
`humanConfirmationRecorded: false`. The run terminates at
`BENCHMARK_COMPLETE` and cannot be finalized or promoted to `accepted/`.
Normal runs still stop at every human gate.

## Bounded-concurrency batches

Start several independent units together with a bounded worker pool:

```bash
./spec2lean formalize-batch \
  --language ptx \
  --version 9.3 \
  --units and.b64,or.b64,xor.b64 \
  --workers 2 \
  --auto-approve
```

`--auto-approve` retains the same benchmark-only, non-promoting semantics as a
single run. Every unit has its own persistent `run.json`; the batch manifest
under `runs/batches/` only coordinates those runs. Output lines are prefixed
with the unit name. The worker count defaults to 2 and is capped at 8;
`--concurrency` remains a compatibility alias for `--workers`. Shared Lean
package installation/build sections use a cross-process repository lock so
parallel agents cannot overwrite the root import module.

Resume an interrupted/incomplete batch and report aggregate performance with:

```bash
./spec2lean resume-batch --batch <batch-id> --workers 2
./spec2lean batch-report --batch <batch-id>
```

Do not put the same unit in a batch twice or start two independent batches for
the same unit artifact root.

## Stage-pipelined batches

The throughput path schedules stage ticks rather than assigning one worker to
an entire unit:

```bash
./spec2lean formalize-pipeline \
  --language ptx \
  --version 9.3 \
  --units and.b64,or.b64,xor.b64 \
  --workers 3 \
  --stage-workers evidence=2,semantic=2,lean=2,theorem=1,proof=2,critic=2 \
  --auto-approve
```

The seven pools are `architecture`, `evidence`, `semantic`, `lean`, `theorem`,
`proof`, and `critic`. `--workers` bounds total concurrent model work; pool
caps provide structural backpressure without requiring seven simultaneous
agents. Idle workers can serve a different eligible pool and keep their
OpenCode runtime alive between jobs. A durable lease prevents two workers from
executing the same run concurrently. A second controller refuses to attach
while the first controller PID is live; after a crash, persisted
`activeExecution` state remains the source of session recovery.

The batch snapshots SHA-256 identities for the source manifest and available
language-front-end artifacts (retrieval index, semantic profile, and shared
environment). A changed dependency stops resume before any agent runs; it is
never silently mixed into an in-flight batch. Human gates consume no worker
and park only the affected unit. Benchmark auto-advance uses the same
deterministic decision-record implementation as the single-run loop.

`batch-report` includes per-stage service and queue-wait mean/p95, worker
utilization, throughput, retry/revision totals, execution models, and whether
traceability-manifest creation occurred inside measured stage service time.
Every semantics/proof manifest remains unit-scoped, content-addressed,
immutable, deterministically validated, and directly consumable by the VS Code
evidence UI.

Resume preserves the saved execution mode and pool configuration; explicit
overrides are optional:

```bash
./spec2lean resume-batch --batch <batch-id> --workers 4 \
  --stage-workers evidence=2,semantic=2,lean=1,proof=2
./spec2lean batch-report --batch <batch-id>
```

## Lean-to-source evidence manifests

The VS Code evidence UI consumes a deterministic manifest instead of parsing
or semantically interpreting Lean on its own. Build and verify that manifest
for a run with:

```bash
./spec2lean traceability build --run <run-id> --pdf-boxes
./spec2lean traceability validate \
  --manifest runs/<run-id>/traceability/evidence-<manifest-sha256>.json
```

The generator joins the claim IDs attached to Lean declarations to the
structured semantic document, reviewed architecture decisions, and hash-bound
source-bundle fragments. Missing links and unknown IDs fail deterministic
validation instead of producing a promotion-safe manifest. Successful `LEAN_FORMALIZATION` now emits this
immutable manifest automatically; rebuilding identical evidence reuses the
same content-addressed file. A later PDF rendition is another immutable view,
not an overwrite. Human feedback recorded through the UI is an
immutable `human_traceability_feedback` record with
`gateApprovalPerformed: false`; it cannot approve or promote a unit.

## Human gates

Prepare a concise read-only brief:

```bash
./spec2lean brief --run <run-id> --gate B
```

Approve and automatically resume until the next human boundary:

```bash
./spec2lean approve --run <run-id> --gate B
```

The approval command itself is the explicit human decision. The controller
deterministically selects the latest candidate and independent critique for
that gate, records their SHA-256 hashes in an immutable `reviews/` record,
verifies the record, and only then advances the state machine. Recording a
decision does not invoke an LLM and never promotes an artifact.

Reject and route back to an allowed revision stage; the wrapper automatically
resumes the revision loop:

```bash
./spec2lean reject \
  --run <run-id> \
  --gate B \
  --to SOURCE_CURATION \
  --reason "Search official evidence before accepting this assumption."
```

Add `--no-resume` to approve/reject when only the decision transition is
wanted.

## Status, recovery, diagnostics

```bash
./spec2lean status --run <run-id>
./spec2lean doctor --run <run-id>
./spec2lean resume --run <run-id> --max-ticks 50
./spec2lean self-test
./spec2lean typecheck
```

An active agent session is persisted before the orchestrator waits for it.
After client interruption, the next tick first attempts to recover that
session instead of blindly starting duplicate work.

Session completion uses OpenCode message `step-finish` information as well as
session status; a terminal `length`/resource outcome is therefore detected
without waiting for a long artificial timeout.

OpenCode provider backoff is distinct from a Spec2Lean semantic `RETRY`.
Provider retry waits are bounded to 60 seconds by default, then the stalled
session is aborted and recorded with failure class
`PROVIDER_RETRY_BUDGET_EXCEEDED`. Override the bound explicitly when needed:

```bash
./spec2lean resume --run <run-id> --provider-retry-budget-seconds 90
```

The performance report counts these provider failures separately from agent
retry outcomes. New executions also record their start time, so
`activeAgentSeconds` excludes human-gate pauses and offline time; historical
executions without start timestamps remain visible as `unmeasuredExecutions`.

One `formalize`/`resume` loop keeps a single OpenCode server alive across all
agent stages until it reaches a human or terminal boundary. Each stage still
uses a separate persisted session, and the standalone `tick` command still
owns and closes its own runtime, so crash recovery and bounded diagnostics do
not depend on an in-memory session object.

Non-proof retries advance to a fresh immutable artifact revision only when the
attempt actually wrote an artifact; provider/protocol failures before a write
reuse the same version number. Historical records without this marker remain
conservative. Completed candidate files are never overwritten.
Malformed JSON is rejected before atomic candidate publication, so a partial
artifact cannot poison later retries. Proof generation intentionally retains
its checked progress file. `formalize` also verifies every file, size, and
SHA-256 pinned by the selected source manifest before creating a run.

Only a terminal assistant turn may supply `SPEC2LEAN_RESULT`; tool-call and
compaction turns are ignored. Invalid outcome/target combinations become a
bounded same-stage `RETRY`, and no second model call is used merely to guess or
repair protocol intent.

Critic disposition is severity-bound: unresolved `BLOCKER`/`MAJOR` findings
request revision, while `MINOR`/`NOTE` findings remain visible in the review
packet and proceed to the human boundary. The orchestrator deterministically
normalizes only the internally inconsistent case where a critic explicitly
labels every finding `MINOR`/`NOTE` but returns `REVISE`. A stage is also
bounded to three critic-requested revision cycles by default; override with
`--max-stage-revisions N` only after inspecting the latest review artifact.

## PTX source retrieval profile

PTX 9.3 deterministic retrieval policy is versioned in
`language_packs/ptx/9.3/retrieval-profile.json`. It identifies the pinned
source manifest, local index schema/cache path, context bounds, and shared
section anchors used by `spec_fast_context`. The profile explicitly performs
retrieval only; it is not a semantic interpretation or human approval.

Rebuild the local hash-verified index with:

```bash
npm --prefix engine/orchestrator run ptx-index -- --version 9.3
```

## Semantic environment and delta IR

The typed semantic composition layer is documented in
`ir/semantic/README.md`. It validates hash-pinned shared semantic environments
and instruction deltas, materializes a deterministic complete review view, and
prepares a compact classification-grouped critic packet while retaining the
full-view fallback.

```bash
./spec2lean semantic-ir validate-delta <environment.json> <delta.json>
./spec2lean semantic-ir materialize <environment.json> <delta.json>
./spec2lean semantic-ir review-packet <environment.json> <delta.json>
```

The PTX 9.3 language pack points to the first explicitly human-approved shared
environment for the bounded scalar `.b32` register/predicate core. Its approval
record remains distinct from the supporting per-unit approvals, and units
outside its declared capability envelope fall back to full semantic review.

The immutable review packet and deterministic approval command are:

```bash
less reviews/shared-semantics/ptx-9.3/shared-environment-first-human-review-v1.md
./spec2lean approve-shared --language ptx --version 9.3 \
  --reviewer "<human reviewer>" \
  --rationale "<explicit shared-scope approval rationale>"
```

The approval command is deterministic, invokes no OpenCode agent, verifies
all pinned files, writes immutable review/environment artifacts, and changes
the profile pointer only after the approved environment validates.

The real workflow evaluates
`language_packs/<language>/<version>/semantic-profile.json` when entering
semantic extraction. A bounded, human-approved environment uses the
`semantic-extractor-delta` agent; the orchestrator then verifies the delta,
source-bundle fragments, official source hashes, and state-affecting gaps
before writing the full view and compact critic packet. Semantic Critic sees
the packet first and can explicitly request full review.

An ineligible environment, missing dependency, invalid or ungrounded delta,
state-affecting open question, unsupported unit feature, or critic revision is
recorded in `run.json` as `LEGACY_FALLBACK`. The subsequent extraction uses the
existing full semantic artifact and agent path. Normal Gate B behavior is
unchanged.

Inspect v2 routing and size telemetry with:

```bash
./spec2lean semantic-report --run <run-id>
./spec2lean perf-report --run <run-id>
```

## Lean package integration

New instruction modules are isolated under a unit namespace such as
`Spec2Lean.PTX.MovB32`. They import `Spec2Lean.Basic` instead of the root module.
This prevents declaration collisions between independently generated units
until a separately reviewed shared PTX core is introduced.

The orchestrator installs the Gate-C-approved mapping into the local Lean
package before proof work and checks `lake build` deterministically.

## Proof generation

Proof work is compiler-driven and incremental rather than one giant LLM
session:

1. extract the human-approved theorem declarations from the obligation artifact;
2. locally check any existing proof artifact first;
3. give the Proof Engineer a bounded batch (at most four declarations and a
   fixed statement-size budget), or concrete diagnostics for a noncompiling
   batch;
4. re-run `lake env lean` locally;
5. keep already compiling declarations;
6. move to final critique only when all approved declarations are present,
   Lean accepts the file, and prohibited verification bypasses are absent.

Exact canonical theorem statements are checked against the human-approved
obligation artifact before completion, so a compiling proof cannot silently
add assumptions or weaken a result. This also prevents long speculative
proof-planning sessions from consuming the entire model context before a proof
file is written.

## Final promotion and Git milestone

After explicit final human approval moves the run to `ACCEPTED`:

```bash
./spec2lean finalize --run <run-id> --push
```

This creates the accepted bundle only from artifacts whose exact hashes occur
in the five human approval records, plus complete traceability manifests and
their pinned source bundles. With `--push`, it stages only the unit/run/package
paths, commits the milestone, and pushes the current branch. It refuses an
automated commit if the Git index already contains staged changes.

## Underlying npm commands

The commands remain available directly under `engine/orchestrator/` for
engineering/debugging, but normal use should prefer `./spec2lean`.
