import { randomUUID } from "node:crypto"

import {
  loadRun,
  saveRun,
} from "./run-store.js"

import {
  transitionRun,
  type RunState,
  type WorkflowMode,
} from "./workflow.js"

function argument(
  name: string,
): string | undefined {
  const index = process.argv.indexOf(name)

  if (index === -1) {
    return undefined
  }

  return process.argv[index + 1]
}

function required(
  name: string,
): string {
  const value = argument(name)

  if (!value) {
    throw new Error(
      `Missing required argument: ${name}`,
    )
  }

  return value
}

async function init(): Promise<void> {
  const mode =
    (argument("--mode") ??
      "formalization") as WorkflowMode

  if (mode !== "formalization") {
    throw new Error(
      "Translation mode is not implemented yet",
    )
  }

  const language =
    required("--language")

  const specVersion =
    required("--version")

  const unit =
    required("--unit")

  const now =
    new Date().toISOString()

  const runId =
    `${language}-${specVersion}-${unit}-${randomUUID()
      .slice(0, 8)}`
      .replace(/[^A-Za-z0-9._-]/g, "-")

  const run: RunState = {
    schemaVersion: 1,

    runId,
    mode,

    language,
    specVersion,
    unit,

    stage: "CREATED",

    createdAt: now,
    updatedAt: now,

    revision: 0,

    gates: {
      A: "pending",
      B: "pending",
      C: "pending",
      THEOREM_STRENGTH: "pending",
      FINAL: "pending",
    },

    history: [
      {
        at: now,
        from: null,
        to: "CREATED",
        reason: "run initialized",
      },
    ],
  }

  await saveRun(run)

  console.log(
    JSON.stringify(run, null, 2),
  )
}

async function show(): Promise<void> {
  const runId =
    required("--run")

  const run =
    await loadRun(runId)

  console.log(
    JSON.stringify(run, null, 2),
  )
}

async function advance(): Promise<void> {
  const runId =
    required("--run")

  const to =
    required("--to")

  const reason =
    argument("--reason") ??
    "manual orchestrator transition"

  const run =
    await loadRun(runId)

  const next =
    transitionRun(
      run,
      to as RunState["stage"],
      reason,
    )

  await saveRun(next)

  console.log(
    JSON.stringify(next, null, 2),
  )
}

const command =
  process.argv[2]

switch (command) {
  case "init":
    await init()
    break

  case "show":
    await show()
    break

  case "advance":
    await advance()
    break

  default:
    throw new Error(
      [
        "Usage:",
        "",
        "  run.ts init --language ptx --version 9.3 --unit add.u32",
        "  run.ts show --run <run-id>",
        "  run.ts advance --run <run-id> --to ARCHITECTURE",
      ].join("\n"),
    )
}
