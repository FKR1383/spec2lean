import { access } from "node:fs/promises"
import { resolve } from "node:path"

import {
  verifyHumanDecisionRecord,
  writeHumanDecisionRecord,
  type RecordHumanDecisionInput,
} from "./human-decision-record.js"
import { REPO_ROOT } from "./repo.js"
import { loadRun, saveRun } from "./run-store.js"
import {
  transitionRun,
  type FormalizationStage,
  type GateName,
} from "./workflow.js"

const WAITING_STAGE: Record<GateName, FormalizationStage> = {
  A: "WAITING_GATE_A",
  B: "WAITING_GATE_B",
  C: "WAITING_GATE_C",
  THEOREM_STRENGTH: "WAITING_THEOREM_STRENGTH_APPROVAL",
  FINAL: "WAITING_FINAL_APPROVAL",
}

const REJECTION_TARGETS: Record<GateName, readonly FormalizationStage[]> = {
  A: ["ARCHITECTURE"],
  B: ["SOURCE_CURATION", "SEMANTIC_EXTRACTION"],
  C: ["LEAN_FORMALIZATION"],
  THEOREM_STRENGTH: ["THEOREM_GENERATION"],
  FINAL: ["BLOCKED"],
}

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

function normalizeGate(raw: string): GateName {
  const gate = raw.toUpperCase()
  if (![
    "A",
    "B",
    "C",
    "THEOREM_STRENGTH",
    "FINAL",
  ].includes(gate)) {
    throw new Error(`Unsupported gate: ${raw}`)
  }
  return gate as GateName
}

function rejectionLocation(
  unitId: string,
  gate: GateName,
  version: number,
): { reviewId: string; reviewPath: string } {
  const slug = gate.toLowerCase().replaceAll("_", "-")
  const reviewId = `${unitId}-${slug}-rejection-v${version}`
  const directory = gate === "THEOREM_STRENGTH"
    ? "theorem-strength"
    : `gate-${slug}`

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

async function selectReviewLocation(
  unitId: string,
  gate: GateName,
  historyReasons: string[],
): Promise<{
  reviewId: string
  reviewPath: string
  recoverExisting: boolean
}> {
  for (let version = 1; version < 1_000; version += 1) {
    const candidate = rejectionLocation(unitId, gate, version)
    if (!(await pathExists(candidate.reviewPath))) {
      return { ...candidate, recoverExisting: false }
    }

    const consumed = historyReasons.some((reason) =>
      reason.includes(candidate.reviewPath)
    )
    if (!consumed) {
      return { ...candidate, recoverExisting: true }
    }
  }

  throw new Error(`Too many rejection records for ${unitId} ${gate}`)
}

async function main(): Promise<void> {
  const runId = required("--run")
  const gate = normalizeGate(required("--gate"))
  const target = required("--to") as FormalizationStage
  const reason = required("--reason")
  const run = await loadRun(runId)

  if (run.stage !== WAITING_STAGE[gate]) {
    throw new Error(
      `Run is at ${run.stage}, not ${WAITING_STAGE[gate]}`,
    )
  }
  if (!REJECTION_TARGETS[gate].includes(target)) {
    throw new Error(`Illegal rejection target for Gate ${gate}: ${target}`)
  }

  const unitId = `${run.language}-${run.unitSlug}`
  const location = await selectReviewLocation(
    unitId,
    gate,
    run.history.map((event) => event.reason),
  )
  const decisionInput: RecordHumanDecisionInput = {
    run,
    gate,
    decision: "rejected",
    reviewId: location.reviewId,
    reviewPath: location.reviewPath,
    reviewer: argument("--reviewer") ?? "Human reviewer",
    rationale: reason,
  }

  if (!location.recoverExisting) {
    await writeHumanDecisionRecord(decisionInput)
  }
  await verifyHumanDecisionRecord(decisionInput)

  let next = transitionRun(
    run,
    target,
    `${location.recoverExisting ? "Recovered previously recorded" : "Recorded"} human ${gate} rejection deterministically: ${reason}; review=${location.reviewPath}`,
  )
  next = {
    ...next,
    gates: {
      ...next.gates,
      [gate]: "rejected",
    },
  }
  await saveRun(next)

  console.log(JSON.stringify({
    ok: true,
    recovered: location.recoverExisting,
    deterministic: true,
    runId,
    gate,
    decision: "rejected",
    reviewPath: location.reviewPath,
    fromStage: run.stage,
    toStage: next.stage,
    reason,
    revision: next.revision,
  }, null, 2))
}

await main()
