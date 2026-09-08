# Rust runtime for Spec2Lean

Build once with Rust 1.88 or newer:

```sh
cargo build --release --manifest-path harness/Cargo.toml
./spec2lean run --language ptx --version 9.3 --instructions and.b32
```

The normal CLI defaults to `rust-harness`. Its phase model and reasoning settings
remain those of the Python pipeline. Install/authenticate the Codex CLI to provide
model replies; OpenCode is not needed. `--runtime opencode` or
`SPEC2LEAN_RUNTIME=opencode` selects the previous runtime explicitly.
`SPEC2LEAN_CODEX` can name the Codex executable; it does not change the model.

Check the provider from the same terminal where you run Spec2Lean:

```sh
codex --version
codex login status
```

If Codex is installed outside that terminal's PATH (for example, bundled with an
editor extension), set `export SPEC2LEAN_CODEX=/absolute/path/to/codex` before
running Spec2Lean. Otherwise install and authenticate the
[Codex CLI](https://learn.chatgpt.com/docs/codex/cli). Rust runtime failures report
the provider error directly. A completed index can be reused by repeating the
same pipeline command with `--resume RUN_ID` after correcting provider setup.

The supervisor's generic `harness` crate supplies the bounded task/tool loop,
provider adapters, persistent Codex conversation, diagnostic/resubmission loop,
step limits, token accounting and transcripts. The `runtime` crate adapts that
loop to the current Python phase MCP servers. Each phase/unit or translation
group keeps main's existing session boundary. A rejected submission returns
main's validation diagnostics to the same session. Only an accepted submit tool
ends the loop. Calls after acceptance cannot overwrite its artifact.

If the model ends a turn without an accepted submission, the loop sends a
corrective reminder and continues the same task within its existing step/time
limits. The reminder is recorded as `feedback` in the transcript. Explicit
terminal reasons, such as refusal or token limits, remain failures.

The Python pipeline still owns all seven phases, prompts, evidence exposure,
claims, shared-core behavior, Lean checks, manifests and GUI mappings. The old
Rust phase implementations and standalone `s2l` task/artifact architecture are
not used. Main's existing run/resume loop remains the outer task scheduler.
The transport consumes the existing session config through a small Python adapter;
its legacy internal `opencode_config` names are retained for compatibility.

`planner-run.json`, `retriever-run.json` and the other phase session records keep
their existing locations and shapes. Their runtime identity can now be
`rust-harness`; their `stdout` contains a JSON transcript with every tool call,
validator response, outcome and token usage. Existing `opencode` metadata remains
valid. The historical `opencodeVersion` field remains readable; on Rust sessions
it records the harness executable version.

The adapter preserves each configured MCP namespace, so the model sees the tool
names already used by the phase prompts, such as `translation_submit_translation`
and `semantics_get_evidence`. Calls are mapped to the underlying server's exact
tool name before dispatch; arbitrary prefixes are not accepted.

Codex replies use native JSON argument objects to avoid a second escaping layer
around complete Lean files. Legacy `arguments_json` replies remain readable.
Malformed replies execute no tools and receive formatting diagnostics in the same
Codex conversation. Their raw output and usage are recorded, and every correction
consumes a step within the existing session/time limits. Only the phase validator
can accept an artifact; response recovery never invents missing arguments or
weakens a validation rule.

The Codex transport disables shell, local-image reads, web search, apps, plugins and multi-agent
features and clears its configured MCP server map. Only the harness dispatches
phase tools. Configuration references:
[Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference).
Timeouts and interrupts terminate the runtime process group, including workers.

```sh
cargo test --manifest-path harness/Cargo.toml
python -m pytest tests/test_runtime.py
```

Provenance: the generic crate was ported from supervisor branch tip
`caddab184e208d6b6e82cfcb57c0e556903c85a6`, preserved by main's history merge
`91e173aad97912fbde00ff4b90e2da34fa384fa9`. The adapter and compatibility changes
are a separate feature commit, based on healthy main
`ac312d534e5441d21980a1bf3633a000b7c0c4ea`.
