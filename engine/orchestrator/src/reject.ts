import { access, readFile } from "node:fs/promises"
import { resolve } from "node:path"

import { sendPromptAsync, waitForAgentResult } from "./async-session.js"
import { parseAgentResult } from "./agent-result.js"
import { startOpenCode, unwrap } from "./opencode.js"
import { REPO_ROOT } from "./repo.js"
import { loadRun, saveRun } from "./run-store.js"
import { transitionRun, type FormalizationStage, type GateName } from "./workflow.js"

type Session = { id: string }

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
  const i = process.argv.indexOf(name)
  return i === -1 ? undefined : process.argv[i + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

function gateName(raw: string): GateName {
  const gate = raw.toUpperCase()
  if (!["A", "B", "C", "THEOREM_STRENGTH", "FINAL"].includes(gate)) {
    throw new Error(`Unsupported gate: ${raw}`)
  }
  return gate as GateName
}

function toolGate(gate: GateName): string {
  return gate === "THEOREM_STRENGTH" ? "C" : gate
}

function recordType(gate: GateName): string {
  return gate === "THEOREM_STRENGTH"
    ? "human_theorem_strength_decision"
    : "human_gate_decision"
}

function reviewLocation(
  unitId: string,
  gate: GateName,
  version: number,
): { reviewId: string; reviewPath: string } {
  const slug = gate.toLowerCase().replaceAll("_", "-")
  const reviewId = `${unitId}-${slug}-rejection-v${version}`
  const directory = gate === "THEOREM_STRENGTH" ? "theorem-strength" : `gate-${slug}`
  return {
    reviewId,
    reviewPath: `reviews/${unitId}/${directory}/${reviewId}.json`,
  }
}

async function selectReviewLocation(
  unitId: string,
  gate: GateName,
  historyReasons: string[],
): Promise<{ reviewId: string; reviewPath: string; recoverExisting: boolean }> {
  for (let version = 1; version < 1000; version += 1) {
    const candidate = reviewLocation(unitId, gate, version)
    let exists = false
    try {
      await access(resolve(REPO_ROOT, candidate.reviewPath))
      exists = true
    } catch {}

    if (!exists) {
      return { ...candidate, recoverExisting: false }
    }

    const consumed = historyReasons.some((reason) => reason.includes(candidate.reviewPath))
    if (!consumed) {
      return { ...candidate, recoverExisting: true }
    }
  }

  throw new Error(`Too many rejection records for ${unitId} ${gate}`)
}

async function verifyRejected(path: string, expectedGate: string): Promise<void> {
  const record = JSON.parse(
    await readFile(resolve(REPO_ROOT, path), "utf8"),
  ) as {
    decision?: string
    gate?: string
    humanConfirmationRecorded?: boolean
  }

  if (record.decision !== "rejected") throw new Error("Rejection record is not rejected")
  if (record.gate !== expectedGate) throw new Error(`Rejection record gate mismatch: ${record.gate}`)
  if (record.humanConfirmationRecorded !== true) throw new Error("Human rejection confirmation missing")
}

async function main(): Promise<void> {
  const runId = required("--run")
  const gate = gateName(required("--gate"))
  const target = required("--to") as FormalizationStage
  const reason = required("--reason")
  const run = await loadRun(runId)

  if (run.stage !== WAITING_STAGE[gate]) {
    throw new Error(`Run is at ${run.stage}, not ${WAITING_STAGE[gate]}`)
  }
  if (!REJECTION_TARGETS[gate].includes(target)) {
    throw new Error(`Illegal rejection target for Gate ${gate}: ${target}`)
  }

  const unitId = `${run.language}-${run.unitSlug}`
  const { reviewId, reviewPath, recoverExisting } = await selectReviewLocation(
    unitId,
    gate,
    run.history.map((event) => event.reason),
  )

  // Immutable-record recovery for interrupted controller executions. A later
  // human rejection at the same gate receives a fresh vN record.
  if (recoverExisting) {
    await verifyRejected(reviewPath, toolGate(gate))
    let next = transitionRun(
      run,
      target,
      `Recovered previously recorded human ${gate} rejection; review=${reviewPath}`,
    )
    next = { ...next, gates: { ...next.gates, [gate]: "rejected" } }
    await saveRun(next)
    console.log(JSON.stringify({
      ok: true,
      recovered: true,
      runId,
      gate,
      decision: "rejected",
      reviewPath,
      fromStage: run.stage,
      toStage: next.stage,
      reason,
    }, null, 2))
    return
  }

  const runtime = await startOpenCode()
  try {
    const session = unwrap<Session>(
      await runtime.runtime.client.session.create({
        body: { title: `Spec2Lean Gate ${gate} rejection ${runId}` },
      }),
    )

    const prompt = [
      "# Explicit Human Gate Rejection",
      `Run ID: ${runId}`,
      `Gate: ${gate}`,
      `Unit: ${run.unit}`,
      `Current stage: ${run.stage}`,
      `Requested revision target: ${target}`,
      "",
      "The human operator explicitly REJECTS approval at this boundary.",
      `Human reason: ${reason}`,
      "",
      "You are the Spec Manager. Read the run state and latest relevant artifacts, then call review_submit exactly once.",
      `recordType: ${recordType(gate)}`,
      `reviewId: ${reviewId}`,
      `unitId: ${unitId}`,
      `gate: ${toolGate(gate)}`,
      "decision: rejected",
      "reviewer: Human reviewer",
      `rationale: ${reason}`,
      "humanConfirmation: I_CONFIRM_THIS_IS_AN_EXPLICIT_HUMAN_DECISION",
      "Do not promote anything and do not execute revision work.",
      "",
      "Your LAST non-empty line must be exactly:",
      `SPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"${target}","summary":"Human ${gate} rejection recorded"}`,
    ].join("\n")

    await sendPromptAsync(runtime.runtime.server.url, session.id, {
      agent: "spec-manager",
      model: { providerID: runtime.model.providerID, modelID: runtime.model.modelID },
      parts: [{ type: "text", text: prompt }],
    })

    const response = await waitForAgentResult(runtime.runtime.server.url, session.id, {
      pollMs: 2_000,
      maxWaitMs: 10 * 60 * 1000,
    })
    const result = parseAgentResult(response)
    if (result.outcome !== "SUCCESS" || result.nextStage !== target) {
      throw new Error(`Invalid rejection result: ${result.outcome} -> ${result.nextStage}`)
    }

    await verifyRejected(reviewPath, toolGate(gate))
    let next = transitionRun(run, target, `Human ${gate} rejected: ${reason}; review=${reviewPath}`)
    next = { ...next, gates: { ...next.gates, [gate]: "rejected" } }
    await saveRun(next)

    console.log(JSON.stringify({
      ok: true,
      runId,
      gate,
      decision: "rejected",
      reviewPath,
      fromStage: run.stage,
      toStage: next.stage,
      reason,
    }, null, 2))
  } finally {
    runtime.runtime.server.close()
  }
}

await main()
