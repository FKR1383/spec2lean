# Spec2Lean

Spec2Lean is an agentic, human-in-the-loop compiler from prose language
specifications to executable and proved Lean 4 models. A run starts from a
hash-pinned official specification (HTML and/or PDF), curates bounded evidence,
extracts explicit semantics, implements those semantics in Lean, proposes and
proves reviewed theorem obligations, and produces declaration-level provenance
for human inspection.

The OpenCode agents perform the research, interpretation, Lean implementation,
critique, and proof work. The TypeScript orchestrator owns the deterministic
parts: stage transitions, immutable artifact paths, schema and hash validation,
Lean checks, human-gate records, retry limits, traceability manifests, and final
promotion. Agents cannot approve a human gate or silently promote their own
output.

## Pipeline

```text
official HTML/PDF specification
        │
        ├─ one-time hash verification and retrieval indexing
        ▼
bounded architecture ── independent architecture critique ── Human Gate A
        ▼
source bundle ── semantic extraction/delta ── semantic critique ── Human Gate B
        ▼
Lean mapping ── mapping critique ── Human Gate C
        ▼
exact theorem declarations ── strength critique ── Human theorem gate
        ▼
compiler-driven proofs ── final aggregation critique ── Human final gate
        ▼
accepted, hash-pinned artifact bundle
```

Every stage is resumable. Candidate revisions are immutable, provider failures
that write nothing do not inflate artifact versions, and proof work is split
into bounded batches. Exact theorem statements are checked deterministically,
so a compiling proof cannot add assumptions or weaken an approved result.

## Requirements

- Linux or another environment capable of running Bash
- Node.js and npm
- the `opencode` CLI plus access to the model configured in `opencode.json`
- Lean 4/Lake through Elan
- VS Code 1.95+ and its `code` CLI for the evidence UI
- Poppler's `pdftotext` for PDF indexing and bounding boxes (HTML-only review
  remains available without it)

Install the repository dependencies:

```bash
npm --prefix engine/orchestrator install
npm --prefix .opencode install
npm --prefix editors/vscode install

cd lean
lake build
cd ..
```

For the bundled PTX 9.3 language pack, fetch the pinned official sources:

```bash
./documents/sources/nvidia/ptx/9.3/fetch.sh
```

The raw files are local cache material and are verified against
`documents/sources/nvidia/ptx/9.3/source-manifest.json` before a run starts.

## One-time specification ingestion

`formalize` performs ingestion automatically. It can also be run explicitly:

```bash
./spec2lean ingest \
  --language ptx \
  --version 9.3 \
  --source-manifest documents/sources/nvidia/ptx/9.3/source-manifest.json
```

Ingestion verifies every manifest artifact and builds a local deterministic
index from pinned HTML, or from locally extracted PDF text when HTML is not
available. Repeated calls are cache hits while all hashes remain unchanged.
The index locates bounded evidence; it does not generate semantic facts or
imply human approval.

For another language, register its official files in a source manifest with
local paths, SHA-256 hashes, and sizes, then pass that manifest explicitly to
`ingest`, `formalize`, or `formalize-batch`.

## Formalizing one unit

Start a normal human-reviewed run:

```bash
./spec2lean formalize \
  --language ptx \
  --version 9.3 \
  --unit or.b64
```

The command prints a `runId` and continues until it reaches a human boundary,
a genuine blocker, or a bounded retry limit. Inspect the current state and a
compact gate brief with:

```bash
./spec2lean status --run <run-id>
./spec2lean brief --run <run-id> --gate A
```

Approve the artifact currently pinned to a human gate and resume automatically:

```bash
./spec2lean approve --run <run-id> --gate A
./spec2lean approve --run <run-id> --gate B
./spec2lean approve --run <run-id> --gate C
./spec2lean approve --run <run-id> --gate THEOREM_STRENGTH
./spec2lean approve --run <run-id> --gate FINAL
```

Rejecting requires an explicit legal return stage and rationale:

```bash
./spec2lean reject \
  --run <run-id> \
  --gate C \
  --to LEAN_FORMALIZATION \
  --reason "Describe the concrete semantic or traceability defect."
```

Resume an interrupted run without creating a new one:

```bash
./spec2lean resume --run <run-id> --max-ticks 50
```

After real human final approval, create the accepted bundle:

```bash
./spec2lean finalize --run <run-id>
```

`finalize` accepts only the exact hashes recorded by all five human approvals,
complete Lean/source traceability, and the source bundles pinned by the
approved semantics. Add `--push` only when the resulting unit milestone should
also be committed and pushed from the current branch.

## Unattended benchmark mode

To evaluate the agentic loop without stopping at gates:

```bash
./spec2lean formalize \
  --language ptx \
  --version 9.3 \
  --unit or.b64 \
  --auto-approve
```

This creates explicit `benchmark_gate_auto_advance` records, not fake human
approvals. The terminal state is `BENCHMARK_COMPLETE`; benchmark runs cannot be
promoted to `accepted/`. If a run stops because of a bounded provider or stage
retry, inspect and resume the same run:

```bash
./spec2lean doctor --run <run-id>
./spec2lean resume --run <run-id> --max-ticks 50
```

Generate performance and semantic-path reports:

```bash
./spec2lean perf-report --run <run-id>
./spec2lean semantic-report --run <run-id>
```

## Batches and worker count

Each unit remains an independent persistent run. `--workers` controls how many
runs are active concurrently and is capped at eight:

```bash
./spec2lean formalize-batch \
  --language ptx \
  --version 9.3 \
  --units and.b64,or.b64,xor.b64 \
  --workers 2 \
  --auto-approve
```

```bash
./spec2lean resume-batch --batch <batch-id> --workers 2
./spec2lean batch-report --batch <batch-id>
```

For a large corpus, use a bounded worker pool rather than launching every unit
at once. Start with two workers and increase only after observing model quota,
memory, and Lean-package lock contention.

## VS Code evidence GUI

The GUI does not rediscover evidence. It consumes the immutable manifest
produced by the pipeline and shows the relationship between a Lean declaration,
semantic/design claims, exact HTML lines, and matching PDF pages/bounding boxes.

The simplest launcher packages and installs the local extension, opens the
repository, and opens a candidate Lean file:

```bash
./spec2lean gui \
  candidates/ptx/9.3/units/or-b32/lean/OrB32-v7.lean
```

This works in a local checkout and in VS Code Remote SSH/container sessions;
run it in the environment that contains the repository. The evidence panel
opens automatically beside the first mapped declaration. In the opened Lean
file:

When the launcher reports an extension version update, run
`Developer: Restart Extension Host` once in an already-open Remote window.
Later launcher calls keep the active matching version and require no restart.

1. click the `Spec2Lean` CodeLens above a declaration;
   alternatively click the persistent `Spec2Lean Evidence` status-bar item;
2. inspect claims and hash-verified evidence in the side panel;
3. select a PDF evidence item to see the cited page and highlighted box;
4. optionally record `Confirm mapping`, `Request change`, or `Question`
   feedback. Feedback is immutable but never approves a gate.

New runs generate semantics and proof manifests automatically. For an older
run, open its candidate Lean file and run this exact Command Palette command:

```text
Spec2Lean: Build Evidence Manifest for Current Run
```

Declarations with missing or unresolved provenance remain visible with a
warning CodeLens. They are not silently treated as complete. More extension
details are in [editors/vscode/README.md](editors/vscode/README.md).

## Traceability CLI

```bash
./spec2lean traceability build --run <run-id> --pdf-boxes
./spec2lean traceability build --run <run-id> --document proofs --pdf-boxes
./spec2lean traceability validate --manifest <manifest-path>
./spec2lean traceability audit
```

A promotion-safe manifest requires every discovered Lean declaration to have
resolved semantic, source, theorem-obligation, or reviewed architecture-design
provenance. Older incomplete runs remain inspectable but fail validation until
their provenance is reviewed and repaired.

## Development checks

```bash
./spec2lean typecheck
./spec2lean self-test

cd editors/vscode
npm run check
cd ../..

cd lean
lake build
```

The main implementation guide is [engine/orchestrator/README.md](engine/orchestrator/README.md).
Semantic IR and traceability contracts are documented in
[ir/semantic/README.md](ir/semantic/README.md) and
[ir/traceability/README.md](ir/traceability/README.md).

## Safety model

- Official source evidence outranks model memory and prior artifacts.
- SOURCE_FACT, DERIVED_INTERPRETATION, DESIGN_DEPENDENCY, ASSUMPTION, and
  OPEN_QUESTION are kept distinct.
- Agents cannot approve human gates, modify accepted artifacts, or use
  `sorry`, `admit`, new axioms, or `unsafe` as verification bypasses.
- Compilation proves Lean consistency, not source faithfulness; independent
  semantic critique and explicit human decisions remain mandatory for an
  accepted artifact.
- Auto-approval is benchmark-only and can never perform promotion.
