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

## Human gates

Prepare a concise read-only brief:

```bash
./spec2lean brief --run <run-id> --gate B
```

Approve and automatically resume until the next human boundary:

```bash
./spec2lean approve --run <run-id> --gate B
```

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
3. give the Proof Engineer one missing theorem declaration (or concrete Lean
   diagnostics) per invocation;
4. re-run `lake env lean` locally;
5. keep already compiling declarations;
6. move to final critique only when all approved declarations are present,
   Lean accepts the file, and prohibited verification bypasses are absent.

This prevents long speculative proof-planning sessions from consuming the
entire model context before a proof file is written.

## Final promotion and Git milestone

After explicit final human approval moves the run to `ACCEPTED`:

```bash
./spec2lean finalize --run <run-id> --push
```

This creates the accepted artifact bundle and manifest. With `--push`, it then
stages only the unit/run/package paths, commits the milestone, and pushes
`main`. It refuses automated commit if the Git index already contains staged
changes.

## Underlying npm commands

The commands remain available directly under `engine/orchestrator/` for
engineering/debugging, but normal use should prefer `./spec2lean`.
