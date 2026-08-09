import { access } from "node:fs/promises"
import { resolve } from "node:path"

import { GATES } from "./gates.js"
import {
  verifyHumanDecisionRecord,
  writeHumanDecisionRecord,
  type RecordHumanDecisionInput,
} from "./human-decision-record.js"
import { REPO_ROOT } from "./repo.js"
import { loadRun, saveRun } from "./run-store.js"
import { transitionRun, type GateName } from "./workflow.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

function normalizeGate(value: string): GateName {
  const gate = value.toUpperCase()
  if (![
    "A",
    "B",
    "C",
    "THEOREM_STRENGTH",
    "FINAL",
  ].includes(gate)) {
    throw new Error(`Unsupported gate: ${value}`)
  }
  return gate as GateName
}

function gateDirectory(gate: GateName): string {
  return gate.toLowerCase().replaceAll("_", "-")
}

function approvalLocation(
  unitId: string,
  gate: GateName,
): { reviewId: string; reviewPath: string } {
  const reviewId = `${unitId}-${gateDirectory(gate)}-approval-v1`
  const directory = gate === "THEOREM_STRENGTH"
    ? "theorem-strength"
    : `gate-${gateDirectory(gate)}`

  return {
    reviewId,
    reviewPath: `reviews/${unitId}/${directory}/${reviewId}.json`,
  }
}

async function pathExists(path: string): Promise<boolean> {
  try {
    await access(resolve(REPO_ROOT, path))
    return true
  } catch {
    return false
  }
}

async function main(): Promise<void> {
  const runId = required("--run")
  const gate = normalizeGate(required("--gate"))
  const run = await loadRun(runId)
  const plan = GATES[gate]

  if (run.stage !== plan.waitingStage) {
    throw new Error(
      `Run is not waiting at Gate ${gate}. Current=${run.stage}; expected=${plan.waitingStage}`,
    )
  }
  if (run.gates[gate] === "approved") {
    throw new Error(`Gate ${gate} is already approved`)
  }

  const unitId = `${run.language}-${run.unitSlug}`
  const { reviewId, reviewPath } = approvalLocation(unitId, gate)
  const rationale = argument("--rationale") ??
    [
      `The human operator explicitly approved Gate ${gate} for run ${run.runId}`,
      "after the automated workflow reached its human-review boundary.",
      "This deterministic record authorizes only the next workflow stage",
      "and is not final acceptance unless gate=FINAL.",
    ].join(" ")

  const decisionInput: RecordHumanDecisionInput = {
    run,
    gate,
    decision: "approved",
    reviewId,
    reviewPath,
    reviewer: argument("--reviewer") ?? "Human reviewer",
    rationale,
  }

  const recovered = await pathExists(reviewPath)
  if (!recovered) {
    await writeHumanDecisionRecord(decisionInput)
  }
  await verifyHumanDecisionRecord(decisionInput)

  let next = transitionRun(
    run,
    plan.approvedStage,
    `${recovered ? "Recovered previously recorded" : "Recorded"} human ${gate} approval deterministically; review=${reviewPath}`,
  )
  next = {
    ...next,
    gates: {
      ...next.gates,
      [gate]: "approved",
    },
  }
  await saveRun(next)

  console.log(JSON.stringify({
    ok: true,
    recovered,
    deterministic: true,
    runId,
    gate,
    decision: "approved",
    reviewPath,
    fromStage: run.stage,
    toStage: next.stage,
    revision: next.revision,
  }, null, 2))
}

await main()
