import { randomUUID } from "node:crypto"

import { makeLeanModuleName, makeUnitSlug } from "./artifact-contract.js"
import { saveRun } from "./run-store.js"
import type { RunState, WorkflowMode } from "./workflow.js"

export type CreateRunInput = {
  mode?: WorkflowMode
  language: string
  specVersion: string
  unit: string
  sourceManifest: string
  benchmarkAutoApprove?: boolean
  sourceAcquisition?: RunState["sourceAcquisition"]
}

export async function createRun(input: CreateRunInput): Promise<RunState> {
  const mode = input.mode ?? "formalization"
  if (mode !== "formalization") {
    throw new Error("Translation mode is not implemented yet")
  }

  const unitSlug = makeUnitSlug(input.unit)
  const leanModuleName = makeLeanModuleName(input.unit)
  const artifactRoot = `candidates/${input.language}/${input.specVersion}/units/${unitSlug}`
  const now = new Date().toISOString()
  const runId = `${input.language}-${input.specVersion}-${input.unit}-${randomUUID().slice(0, 8)}`
    .replace(/[^A-Za-z0-9._-]/g, "-")

  const run: RunState = {
    schemaVersion: 1,
    qualityContractVersion: 1,
    runId,
    mode,
    language: input.language,
    specVersion: input.specVersion,
    unit: input.unit,
    unitSlug,
    leanModuleName,
    sourceManifest: input.sourceManifest,
    sourceAcquisition: input.sourceAcquisition,
    artifactRoot,
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
    ...(input.benchmarkAutoApprove
      ? {
          benchmark: {
            autoApprove: true as const,
            startedAtUtc: now,
          },
        }
      : {}),
  }

  await saveRun(run)
  return run
}
