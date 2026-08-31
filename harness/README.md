# spec2lean harness (Rust)

The harness is everything outside the model: provider adapters, the tool
registry, the bounded agent loop, the transcript, and the deterministic work the
harness runs itself between turns.

It replaces OpenCode. Nothing needs to be on `PATH`, there is no agent
subprocess, no stdio MCP protocol, no synthesized config, and no ambient
capability to disable — a tool call is a function call in this process.

## Layout

| Crate | What it is |
|---|---|
| `harness` | Provider trait, Anthropic + OpenAI-compatible adapters, HTTP with retry, the agent loop, transcripts. Provider-agnostic and spec2lean-agnostic. |
| `spec2lean-specdb` | Read-only typed access to the Phase-1 SQLite index; typed IDs; text normalisation and stable IDs. |
| `spec2lean-evidence` | Phase 3: the nine retrieval tools, the exposure ledger, the deterministic validator, bundle reconstruction. |
| `s2l` | Command line entry point. |

## Build and test

```bash
cargo build
cargo test          # 33 tests, no network and no API key required
cargo clippy --all-targets
```

The test suite builds its own synthetic Phase-1 index in-process
(`spec2lean-specdb`'s `fixture` feature), so it needs neither Python nor a
checked-in database.

## Running a phase

```bash
export ANTHROPIC_API_KEY=...
s2l evidence run --database indexes/spec.sqlite \
                 --plan plans/plan.json --unit unit:add --out runs/add
```

Artifacts land in `--out`: `evidence-scope.json`, `exposure-trace.json`,
`evidence-bundle.json`, and `transcript.json`. The transcript is written whether
or not the session succeeded.

Offline, with no provider at all:

```bash
s2l evidence replay --database ... --plan ... --unit ... --calls calls.json
s2l evidence prompt --database ... --plan ... --unit ...
```

`replay` runs a scripted list of `{"tool": ..., "input": {...}}` calls through
the real tool set, ledger, and validator. It is how the phase is debugged
without spending a token.

## Parity with the Python implementation

`scripts/crosscheck.py` runs the same tool sequence through both
implementations and diffs the resulting bundles. They must be identical,
including every `evidenceId` — those are SHA-256 digests over canonical JSON, so
a match proves that text normalisation, canonical JSON, stable-ID construction,
provenance reconstruction, and record layout all agree across the two languages.

```bash
.venv/bin/python harness/scripts/crosscheck.py
```

`crates/specdb/schema.sql` is extracted verbatim from `spec2lean.database`; keep
it in sync when Phase 1 changes.

## Design notes

**Why the tool set owns completion.** `ToolSet::finished()` replaces the old
"did a file appear on disk" check. The loop stops when the tool set says it has
a terminal artifact, never by parsing what the model said.

**Why assistant content is replayed verbatim.** `Exchange::assistant` holds the
provider's own content object untouched. That is what keeps thinking blocks — and
any block type added after this code was written — valid on the next request. It
makes a transcript provider-bound, which `Transcript::provider` records.

**Where the cache breakpoints go.** Anthropic renders `tools → system →
messages`. A unit session's stable prefix is therefore [tools, system, the
opening prompt], and the opening prompt carries the seed nodes' exact
specification text — the bulk of the tokens, byte-identical across every step.
Two breakpoints cover all of it; growing tool results land after them.

**The deterministic-step seam.** `ToolSet::after_tools()` lets the harness run
its own work — a compiler, a checker — after each batch of tool calls and hand
the result back in the same conversation. This is the seam that lets a Lean build
failure become an inner-loop tool result instead of a Phase 6 → Phase 7 round
trip through a fresh process.

**Phase 1 stays in Python for now.** It emits a SQLite database, which is a file
artifact rather than a live protocol, so reading it from Rust introduces no
process boundary of the kind this rewrite exists to remove.

## Status

Ported: Phase 3 (evidence retrieval).
Not yet ported: Phases 2, 4, 5, 6, 7 — they still run through OpenCode in the
Python tree. Phase 1 (parse + index) is intentionally staying in Python.

The Anthropic and OpenAI adapters are covered by unit tests over their request
bodies and response parsing, but have not been exercised against the live
endpoints from this workspace (no API key present). `strict_tools` is off by
default for that reason; the typed deserialisation in each tool set is the
primary guarantee either way.
