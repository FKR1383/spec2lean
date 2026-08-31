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
| `spec2lean-semantics` | Phase 4: evidence-bounded extraction, the claim taxonomy, deterministic artifact validation. |
| `spec2lean-lean` | Invokes the Lean toolchain and parses its diagnostics. No phase knowledge. |
| `spec2lean-translation` | Phase 5: group translation to Lean 4, with the compiler in the loop. |
| `s2l` | Command line entry point. |

## Build and test

```bash
cargo build
cargo test          # 78 tests, no network and no API key required
cargo clippy --all-targets
```

The test suite builds its own synthetic Phase-1 index in-process
(`spec2lean-specdb`'s `fixture` feature), so it needs neither Python nor a
checked-in database. Tests that need `lean` skip themselves when it is absent.

## Running a phase

```bash
export ANTHROPIC_API_KEY=...

# Phase 3: retrieve evidence for one planned unit.
s2l evidence  run --database indexes/spec.sqlite \
                  --plan plans/plan.json --unit unit:add --out runs/add

# Phase 4: extract semantics from that unit's evidence bundle.
s2l semantics run --plan plans/plan.json \
                  --bundle runs/add/evidence-bundle.json \
                  --unit unit:add --out runs/add

# Phase 5: translate a group of semantic artifacts into Lean 4.
s2l translate run --plan plans/plan.json --semantics runs \
                  --group add --out runs/group-add
```

Artifacts land in `--out`: `evidence-scope.json`, `exposure-trace.json`,
`evidence-bundle.json`, `semantic-scope.json`, `semantic-artifact.json`, and
`transcript.json`. The transcript is written whether or not the session
succeeded.

Offline, with no provider at all:

```bash
s2l evidence  replay --database ... --plan ... --unit ... --calls calls.json
s2l semantics replay --plan ... --bundle ... --unit ... --calls calls.json
s2l translate replay --plan ... --semantics ... --group ... --calls calls.json
s2l lean check --file Add.lean
```

`replay` runs a scripted list of `{"tool": ..., "input": {...}}` calls through
the real tool set and validator. It is how a phase is debugged without spending
a token.

## Parity with the Python implementation

`scripts/crosscheck.py` runs the same tool sequences through both
implementations and diffs the resulting artifacts.

Phase 3 bundles must be byte-identical, including every `evidenceId` — those are
SHA-256 digests over canonical JSON, so a match proves that text normalisation,
canonical JSON, stable-ID construction, provenance reconstruction, and record
layout all agree across the two languages. Phase 4 artifacts must match except
for the `extractor` block (see below).

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

**Four cache breakpoints, deliberately placed.** End of system; end of the
opening prompt; end of the first exchange's tool results; and a rolling one at
the previous exchange. The third matters for Phase 4, which hands the model its
whole evidence bundle through `get_evidence` rather than the prompt — without a
breakpoint there, that bundle is re-sent uncached on every step of the session.

## Deliberate divergences from the Python implementation

**`extractor` provenance.** Python hardcoded `provider: "opencode"` and
validated against a fixed model list. Rust records the provider and model that
actually ran. The crosscheck normalises this block away before diffing.

**`result` is optional for non-instruction units.** Python validated `result`
unconditionally:

```python
result = _component(value.get("result"), "result", "$.result", ...)
```

so an absent `result` produced `EXPECTED_OBJECT` for *every* unit, including
`LANGUAGE_CONSTRUCT` and `SHARED_CONCEPT` units that have no result. Two
consequences: extractors were pushed into inventing a result for concepts that
do not have one, and the instruction-specific `MISSING_RESULT` diagnostic — which
explains the actual problem — became unreachable. Rust requires `result` only
where the code always meant to: for instructions. `identity` remains mandatory
for every unit kind, as before.

## Status

Ported: Phase 3 (evidence retrieval), Phase 4 (semantic extraction), Phase 5
(group translation, including the build loop that absorbs Phases 6 and 7 for the
build-failure case).

Not yet ported:

- **Phase 2 (planner).** Plans must be supplied as JSON.
- **The frozen shared core.** A group with shared prerequisites is refused with
  an explicit error rather than translated against an unagreed representation.
- **Phase 6's logical checking** (`checking/logical.py`, ~900 lines): reverse
  traceability and group-wide coverage beyond what Phase 5 validates per group.
- **Phase 7's semantic routing.** The build-failure path is now an inner loop;
  routing a *semantic* failure back upstream is not ported.
- **Phase 4's open-question handler.** The validator handles `resolutions`
  already present in a bundle, but nothing produces them yet.

Phase 1 (parse + index) is intentionally staying in Python.

The Anthropic and OpenAI adapters are covered by unit tests over their request
bodies and response parsing, but have not been exercised against the live
endpoints from this workspace (no API key present). `strict_tools` is off by
default for that reason; the typed deserialisation in each tool set is the
primary guarantee either way.
