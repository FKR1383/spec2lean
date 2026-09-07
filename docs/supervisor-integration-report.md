# Supervisor integration audit — 2026-09-07

Healthy local main remains the architectural baseline. Both supervisor PRs were
accepted through history-only `ours` merges, followed by separate feature commits.
No squash, rebase, force-push, or tag modification was used.

## Recorded Git identities

| Item | SHA |
| --- | --- |
| MAIN_BASE_SHA | `ac312d534e5441d21980a1bf3633a000b7c0c4ea` |
| Original rust-harness PR head | `caddab184e208d6b6e82cfcb57c0e556903c85a6` |
| Original semantic-index PR head | `8836d0422ea6201237ceec5da5aa44cba7dcc3e6` |
| PR #1 history merge | `91e173aad97912fbde00ff4b90e2da34fa384fa9` |
| PR #2 history merge | `1a56347979e6ba90290a43a1efd5431ccb1955c8` |
| Rust feature | `9b7bb4c633b9c2f416733c50d623a4726931ea8f` |
| Semantic feature | `f609aa2309cb377fc4edf91dfba95cdd15e350df` |
| Integration hardening | `58813fb764e5463d089d106cb33f751fe45ea786` |

The safety branch `safety/main-before-supervisor-integration-20260907` points to
MAIN_BASE_SHA. Both history merge trees equal its tree:
`650e9161f5271ae5ad785d276ff061aff6fada46`.
`git rev-list origin/rust-harness origin/semantic-index --not HEAD` returned
nothing: every supervisor ancestor is reachable from main, preserving authorship.

GitHub confirms [PR #1](https://github.com/FKR1383/spec2lean/pull/1) and
[PR #2](https://github.com/FKR1383/spec2lean/pull/2) are merged, with the history
merge SHAs above. PR #2 originally targeted rust-harness and was retargeted to
main before the history merges were pushed. Baseline and history pushes were
normal fast-forward pushes. The final commit and final push result are reported
in the accompanying completion message, after this audit is committed.

## Features accepted and architecture preserved

Rust: the supervisor's generic bounded session/tool loop, persistent Codex MCP
conversation, ordered tool dispatch, validation/resubmission, step limits, usage
accounting and transcripts. A small Rust/Python adapter drives current main's
existing bounded MCP servers. The normal CLI defaults to Rust and preserves the
current phase/unit/group scheduling. The existing pipeline remains the outer
task loop; the supervisor's standalone s2l artifact/task workflow was not imported.

Semantic index: the supervisor's MiniLM node embeddings, title-prefixed text,
4,000-character ranking input, normalized float32 SQLite storage and cosine
ranking. The current Phase1Query exposes semantic ranking beside unchanged FTS
and hierarchical navigation. Model/revision and freshness metadata, atomic rebuilds,
validation, CLI selection, and mode-aware plan/resume matching are added.
The MCP worker caches the embedding model; it does not start an embedder per query.

Deliberately rejected: alternate Rust planning/evidence/semantics/translation/
checking/shared-core/specdb crates and their legacy schemas, standalone s2l CLI
and task artifacts, old phase prompts and Python architecture changes, alternate
GUI, parser and validator changes, unrelated source files and branch documentation,
and a hybrid retrieval default. Main's lexical default wins.

All current-main prompt files are byte-for-byte unchanged. GUI code and APIs,
parsers, canonical database schema, evidence models/validation, group ownership,
translation storage, planner validation and Phase-6 checks are unchanged.
The existing group/shared declarations and their unit-scoped claim references
remain the shared-core contract. Only provider identity is extended to accept
`rust-harness` alongside `opencode`; pipeline manifests add optional `indexMode`.
Model IDs and reasoning settings remain those of main. Legacy artifact validation
and reuse continue to work.

## Verification

- Final Python suite: **162 passed**, no skipped tests.
- Ported Rust core suite: **60 passed**, no ignored tests; HTTP tests used localhost.
- Rust release build, `cargo fmt --all --check`, and Clippy with `-D warnings`: passed.
- Runtime integration tests exercised current planner rejection/acceptance, Phase-7
  mandatory context reads and repair submission, manifest preservation, timeout
  process-group cleanup and injectable command runners.
- Semantic tests covered exact identity/provenance preservation, model revision,
  filters, stale/missing/corrupt vectors, failed rebuild preservation, dry run,
  mode selection, and resume/plan compatibility.
- Existing CLI, multi-unit group, GUI, Check, open-question and revision tests passed.

Two real `./spec2lean run` invocations formalized PTX 9.3 `and.b32`, using the
Rust runtime and the unchanged main phase prompts/model settings:

| Mode | Pipeline run | Result | Lean / Coverage / Traceability | Claims / evidence / mapped declarations |
| --- | --- | --- | --- | --- |
| lexical | `pipeline-run:ce6cc08debd3340dcc04d002` | COMPLETE | PASS / PASS / PASS | 4 / 8 / 6 |
| semantic | `pipeline-run:76c39eabf33ee0f7dcae0d3c` | COMPLETE | PASS / PASS / PASS | 4 / 6 / 7 |

Both compiled with real Lean **4.33.1**. Successful active attempts took about
6m09s and 8m31s respectively. The semantic test first exposed an incomplete test
index copy lacking PDF page-text companions; it was interrupted, corrected and
resumed through the existing pipeline mechanism. No source validator was relaxed.
Both completed runs were then resumed again: plans, evidence, semantics,
translations and checks were reused with no new model sessions. `status` and
`plan units` also succeeded. Phase 7 correctly required no repair after PASS;
its Rust repair route was separately exercised by the deterministic bridge test.

A real MiniLM search for “bitwise conjunction of two source operands” returned
zero lexical hits and ranked the official PDF and HTML “Bitwise AND” nodes first
in semantic mode (cosine approximately 0.5974). The exact instruction-scoped
pipeline runs could use direct node navigation; this separate query explicitly
exercised semantic ranking. The copied PTX index contains 24,049 vectors of 384
dimensions. The recorded MiniLM revision is
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.

Both runs passed the actual Chromium GUI regression: Lean selection → claims →
evidence → exact source nodes/spans, PDF preview rendering, reverse mappings,
Build/Coverage/Traceability views, and run/unit navigation. No JavaScript errors
or HTTP error responses occurred. The checker retains the GUI's actual source
repository boundary while allowing isolated artifact directories.

Local artifacts and browser screenshots are under
`tmp/supervisor-integration/{lexical,semantic}` and
`tmp/supervisor-integration/{lexical,semantic}-gui.png`.
Test logs and retrieval/GUI summaries are under
`tmp/supervisor-integration/validation/`. These remain ignored generated artifacts.

Reproduce the browser/API check with optional Playwright installed:

```sh
PYTHONPATH=src python scripts/verify_integrated_run.py \
  --root tmp/supervisor-integration/semantic --browser
```

## User-facing workflow

```sh
./spec2lean run --language ptx --version 9.3 --instructions and.b32
./spec2lean run --language ptx --version 9.3 --instructions and.b32 --index-mode semantic
./spec2lean run --language ptx --version 9.3 --instructions and.b32 --resume
./spec2lean status --run PIPELINE_RUN_ID
./spec2lean index embed --language ptx --version 9.3
./spec2lean index search --language ptx --version 9.3 --index-mode semantic --query 'bitwise conjunction'
```

Build Rust once as documented in [harness/README.md](../harness/README.md).
Semantic dependencies are optional: `pip install -e '.[semantic]'`.
`--runtime opencode` explicitly selects the legacy runtime; existing per-phase,
status, trace, inspection, dry-run and resume commands remain available.
Semantic resume uses the same `--index-mode semantic` selection as the original run.

## Final file review

Every changed file was reviewed against MAIN_BASE_SHA. Changes are confined to
the Rust runtime, semantic retrieval, their compatibility adapters, and tests/docs.
The following inventory records the purpose of each changed file.

| File | Purpose |
| --- | --- |
| `.gitignore` | Ignore compiled Rust output. |
| `README.md` | Feature usage, provenance and validation documentation. |
| `docs/semantic-index.md` | Feature usage, provenance and validation documentation. |
| `docs/supervisor-integration-report.md` | Feature usage, provenance and validation documentation. |
| `harness/Cargo.lock` | Minimal Rust workspace and locked dependencies. |
| `harness/Cargo.toml` | Minimal Rust workspace and locked dependencies. |
| `harness/README.md` | Feature usage, provenance and validation documentation. |
| `harness/crates/harness/Cargo.toml` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/clock.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/error.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/lib.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/provider/anthropic.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/provider/codex.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/provider/codex_mcp.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/provider/http.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/provider/mod.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/provider/openai.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/provider/recorded.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/session.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/tool.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/harness/src/transcript.rs` | Ported generic Rust runtime and its unit tests. |
| `harness/crates/runtime/Cargo.toml` | Rust adapter to current-main MCP tools. |
| `harness/crates/runtime/src/main.rs` | Rust adapter to current-main MCP tools. |
| `pyproject.toml` | Optional semantic embedding dependency. |
| `schemas/open-question-result.schema.json` | Additive runtime identity or optional retrieval-mode metadata. |
| `schemas/pipeline-run.schema.json` | Additive runtime identity or optional retrieval-mode metadata. |
| `schemas/semantic-artifact.schema.json` | Additive runtime identity or optional retrieval-mode metadata. |
| `schemas/translation-manifest.schema.json` | Additive runtime identity or optional retrieval-mode metadata. |
| `schemas/troubleshoot-result.schema.json` | Additive runtime identity or optional retrieval-mode metadata. |
| `scripts/verify_integrated_run.py` | Real artifact, GUI API and browser validation. |
| `src/spec2lean/cli.py` | Add runtime/index selection and index embed command. |
| `src/spec2lean/embeddings.py` | Atomic node-vector storage, validation and cosine retrieval. |
| `src/spec2lean/evidence/runner.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/pipeline/runner.py` | Ensure semantic vectors and preserve mode-aware reuse/resume. |
| `src/spec2lean/planning/runner.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/planning/scope.py` | Optional semantic ranking in the existing query interface. |
| `src/spec2lean/runtime.py` | Runtime selection, current session-config adapter and process cleanup. |
| `src/spec2lean/semantics/models.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/semantics/question_mcp.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/semantics/question_runner.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/semantics/revision.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/semantics/runner.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/semantics/validation.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/translation/models.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/translation/revision.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/translation/runner.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/translation/validation.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/troubleshooting/opencode.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `src/spec2lean/troubleshooting/runner.py` | Minimal runtime dispatch/identity compatibility; retrieval metadata where applicable. |
| `tests/test_embeddings.py` | Feature, compatibility or runtime-identity regression tests. |
| `tests/test_runtime.py` | Feature, compatibility or runtime-identity regression tests. |
| `tests/test_semantics.py` | Feature, compatibility or runtime-identity regression tests. |
| `tests/test_translation.py` | Feature, compatibility or runtime-identity regression tests. |
