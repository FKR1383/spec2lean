# Phase 1 reset inventory

The repository was inspected before the reset and classified as follows.

## Required for Phase 1

- `documents/sources/nvidia/ptx/9.3/raw/ptx_isa_9.3.{pdf,html}`
- PTX `source-manifest.json`, `SHA256SUMS`, and `fetch.sh`
- the generic `documents/` source area

The existing ECMAScript official source and manifest were also retained as a
future parser input. They are source evidence, not old pipeline infrastructure.

## Useful generic infrastructure

- Git repository/history and branches
- Python ignore rules and the source-acquisition manifests

## Removed previous-design-only material

- `.opencode/` agents/tools and `opencode.json`
- TypeScript orchestrator and stage/workflow machinery under `engine/`
- accepted/candidate formalizations, semantic artifacts, source bundles,
  theorem artifacts, reviews, and run records
- Lean package and generated proof/formalization modules
- semantic/traceability IR schemas and language semantic profiles
- benchmark/evaluation baselines
- VS Code orchestration integration
- old semantic-IR-only test fixtures and obsolete handoff/prompt documents

The reset is recoverable from Git commit history and did not rewrite history or
remove official specification sources.

