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
| `spec2lean-planning` | Phase 2: scope resolution, plan validation, dependency-graph derivation. |
| `spec2lean-evidence` | Phase 3: the nine retrieval tools, the exposure ledger, the deterministic validator, bundle reconstruction. |
| `spec2lean-semantics` | Phase 4: evidence-bounded extraction, the claim taxonomy, deterministic artifact validation. |
| `spec2lean-lean` | Invokes the Lean toolchain, parses diagnostics, and audits axiom dependencies. No phase knowledge. |
| `spec2lean-checking` | Phase 6: coverage forward, and traceability backward to the index. |
| `spec2lean-shared-core` | The frozen shared core: one agreed representation for concepts several units depend on. |
| `spec2lean-translation` | Phase 5: group translation to Lean 4, with the compiler in the loop. |
| `s2l` | Command line entry point. |

## Build and test

```bash
cargo build
cargo test          # 202 tests, no network and no API key required
cargo clippy --all-targets
```

One of those tests drives every phase in a single process — plan, evidence,
semantics, core, translate, check — against real `lean`, with nothing mocked but
the model's choices. Each phase has its own tests; that one exists for what
they cannot see, which is the seam between them.

The test suite builds its own synthetic Phase-1 index in-process
(`spec2lean-specdb`'s `fixture` feature), so it needs neither Python nor a
checked-in database. Tests that need `lean` skip themselves when it is absent.

## Running a phase

One command, request to checked Lean:

```bash
export ANTHROPIC_API_KEY=...
s2l run --database indexes/spec.sqlite --language ptx --version 8.5 \
        --family "integer arithmetic" --out runs/2026-09-01
```

A machine that can run Claude Code already has a usable credential, so no second
login is needed. `ANTHROPIC_AUTH_TOKEN` is sent as an OAuth bearer token:

```bash
export ANTHROPIC_AUTH_TOKEN=$(python3 -c \
  "import json,pathlib;print(json.loads(pathlib.Path.home().joinpath('.claude/.credentials.json').read_text())['claudeAiOauth']['accessToken'])")
```

That token carries the `user:inference` scope, but the Messages API accepts it
only for Claude Code itself: another client is refused with a 429 whose body
carries no rate-limit headers. Dressing this harness up as Claude Code to get
past that is not worth an account, so the supported answer for a machine
without an API key is `--provider codex`.

### `--provider codex`

Codex is an agent, not an endpoint, so the adapter uses only the part of it
that is one: `codex exec` for a single turn whose reply a JSON schema
constrains. Codex's own loop, tools and sandbox stay unused, because the
harness must keep its loop — the exposure ledger, the submission gates and the
deterministic step after each tool call are the pipeline, not decoration.

```bash
s2l plan run --database indexes/pcie-transport-1.0d-fixed.sqlite \
             --language PCIe --version 1.0d \
             --subtree node:479046a24ddb9b29573b62dd \
             --out runs/resets/plan --provider codex
```

The conversation lives in one codex thread, resumed per turn, so each turn
sends only the tool results the thread has not seen. The first version opened a
fresh `codex exec` every turn; on the same PCIe plan that cost 71.5k input
tokens across 4 turns with a 0% cache hit, because a new process rebuilds
codex's own preamble ahead of ours and the stable prefix never lands at a
stable offset. Holding one thread brought the same plan to 53.9k tokens in 2
turns at a 30% cache hit.

A process start per turn is still the standing cost, and codex's own harness
prompt — about 14k tokens of instructions and tool schemas the adapter does not
want — rides underneath every request. An OpenAI API key would remove both by
letting `--provider openai` talk to the model directly.

It plans, then retrieves and extracts per unit, freezes a shared core if the
plan needs one, translates each group whose units all completed, and checks the
result. A unit that fails stops that unit, not the run — three units formalized
and one reported as insufficient is a more useful outcome than "failed". `run.json`
records what each phase did.

Or a phase at a time:

```bash
# Phase 2: turn a request into a validated plan.
s2l plan run --database indexes/spec.sqlite --language ptx --version 8.5 \
             --family "integer arithmetic" --out plans

# Phase 3: retrieve evidence for one planned unit.
s2l evidence  run --database indexes/spec.sqlite \
                  --plan plans/plan.json --unit unit:add --out runs/add

# Phase 4: extract semantics from that unit's evidence bundle.
s2l semantics run --plan plans/plan.json \
                  --bundle runs/add/evidence-bundle.json \
                  --unit unit:add --out runs/add

# Shared core: one representation for the concepts several units depend on.
s2l core run --plan plans/plan.json --semantics runs --out runs/core

# Phase 5: translate a group of semantic artifacts into Lean 4.
s2l translate run --plan plans/plan.json --semantics runs \
                  --group add --core runs/core --out runs/group-add
```

Artifacts land in `--out`: `evidence-scope.json`, `exposure-trace.json`,
`evidence-bundle.json`, `semantic-scope.json`, `semantic-artifact.json`, and
`transcript.json`. The transcript is written whether or not the session
succeeded.

Offline, with no provider at all:

```bash
s2l plan      replay --database ... --language ... --version ... --calls calls.json
s2l evidence  replay --database ... --plan ... --unit ... --calls calls.json
s2l semantics replay --plan ... --bundle ... --unit ... --calls calls.json
s2l core      replay --plan ... --semantics ... --calls calls.json --out ...
s2l translate replay --plan ... --semantics ... --group ... --calls calls.json
s2l lean check --file Add.lean

# Phase 6: check a finished group against its inputs and the index.
s2l check --database indexes/spec.sqlite --group-dir runs/group-add \
          --units runs --core runs/core
```

`replay` runs a scripted list of `{"tool": ..., "input": {...}}` calls through
the real tool set and validator. It is how a phase is debugged without spending
a token.

## Parity with the Python implementation

`scripts/crosscheck.py` runs the same tool sequences through both
implementations and diffs the resulting artifacts.

Phase 2 plans must be byte-identical. Unit IDs, shared dependency IDs, and the
processing layers are all *derived*, so a match proves the derivations agree —
not merely that both accepted the same submission.

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

## Using it as an EDLab tool

EDLab's mechanism is *agents propose, tools decide*: every verdict a user sees
comes from a deterministic tool run rather than a model's judgment. That is the
principle this harness is built on, so it fits there as a tool rather than as an
agent. Any command accepts `--verdict <workspace>`:

```bash
s2l check --database ... --group-dir ... --units ... --verdict .
# .edlab/verdicts.jsonl
# {"tool":"spec2lean-check","passed":false,
#  "summary":"check failed: traceability: FAIL (1 broken)"}
```

One JSON line per run, and an exit code that says whether it passed. The
container needs `lean` on PATH and a Phase-1 index; everything else is in the
binary.

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

**Phase 2 selects, deterministic code derives.** The planner owns judgement —
which units, which groups, which shared concepts, which dependencies, and why.
It never owns identity: unit IDs, shared dependency IDs, prerequisite IDs, the
processing layers, and the cycle report are all derived from what it submitted
and checked against the index. Every node ID it cites must exist, and a
translation group must be justified by structure its members actually sit under,
not a section that merely sounds related.

**Compiling is not the soundness check; the kernel is — and it must be asked
across an import.**  A Lean file full of
`sorry` compiles perfectly and asserts nothing, and a textual scan for `sorry`
or `axiom` can always be evaded — a raw string, an interpolated expression. So
after a successful build the harness runs `#print axioms` over every mapped
declaration and rejects anything depending on `sorryAx` or on an axiom outside
Lean's standard classical foundation (`propext`, `Classical.choice`,
`Quot.sound`). It sees through imports, so a hole in the shared core fails every
group that uses it. The textual scan remains as a fast, legible first pass.

The queries run from a *separate* file that imports the compiled module, not
appended to the source. Appending them lets the audited source print into the
same stream, and  is
indistinguishable from Lean's own answer. An imported module's  does not
run, so probing across the import removes the channel; the probe's exit status
is checked as a second defence.

**One representation for shared concepts.** When several units depend on the
same concept, each group formalizing it independently produces Lean that agrees
only by accident. The core gives it one representation, compiled and audited
once, then frozen; groups import it and must bind to the declarations it
registered. A group with shared concepts and no core is refused rather than
translated against a representation nothing agreed on.

**Traceability is verified, not assumed.** Phase 6 walks backward from every
Lean declaration through its claims to its evidence, and re-derives that
evidence's exact text from the index to compare byte for byte. Artifacts are
written at different times and an index can be rebuilt underneath them; this is
what catches a passage that has since changed, a document that was reindexed,
and a bundle edited by hand. Forward, it checks that every claim *and* every
piece of evidence those claims rest on reaches at least one declaration —
including declarations that live in the frozen core.

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

Ported: Phase 2 (planning), Phase 3 (evidence retrieval), Phase 4 (semantic
extraction), the shared core, Phase 5 (group translation, including the build
loop that absorbs Phase 7 for the build-failure case), and Phase 6 (coverage and
reverse traceability).

Exercised end to end on a real specification: the NVM Express PCIe Transport
Specification 1.0d, indexed from the published PDF, planned, retrieved,
extracted, cored, translated into Lean that compiles and passes the axiom audit,
and checked — with every declaration traceable back through its claim to the
exact page of the source. Two runs:

- **Reset semantics** (section 3.3, prose). Controller Level Reset frozen as one
  shared representation; the group formalizes the register-space rule and its
  single exception.
- **Doorbell registers** (section 3.1.2, bit-field tables). Two units — the
  submission-queue tail and completion-queue head doorbells — sharing one
  register layout, each traced back to the `Bits / Type / Reset / Description`
  table on page 10.

And once on a dual-rendition source, the NVIDIA PTX ISA 9.3 (930-page PDF plus
HTML, 24,352 nodes): `add.u32`, section 9.7.1.1. An exact-instruction request
resolves it to one unit carrying both renditions, and the both-renditions rule
then holds throughout — every SOURCE_FACT and DERIVED_INTERPRETATION cites the
matching HTML *and* PDF passage. Pairing an HTML syntax block with an unrelated
PDF paragraph is refused.

Ported: the frozen shared core, and a kernel-level axiom audit that has no
counterpart in the Python tree.

Not yet ported:

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

## Two index modes

The index is full-text, which finds passages sharing words with the query. A
specification rarely obliges: the section that answers "what happens when the
controller is restarted" is headed *Controller Level Reset*, and shares not one
of those words. On this index that query returns nothing lexically and the right
section at 0.611 semantically.

Embeddings are optional and live in the same SQLite file, so an index either
carries them or does not:

```bash
python3 -m spec2lean.embeddings --database indexes/pcie-transport-1.0d-fixed.sqlite
```

`spec` then takes a `mode`. `lexical` matches words and needs the
specification's own vocabulary. `semantic` matches meaning and reaches
paraphrase, but drifts toward the merely topical. `hybrid` is the default
wherever embeddings exist, and fuses the two rankings by reciprocal rank rather
than by score, because a similarity and a full-text relevance are not the same
quantity. An index built without embeddings keeps working, lexically, and a
`semantic` search against one is refused rather than quietly answered the other
way.
