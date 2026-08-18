import {
  recordBenchmarkAutoAdvance,
  type BenchmarkSemanticAssumption,
} from "./benchmark-decision-record.js"
import { GATES } from "./gates.js"
import {
  buildProvenanceCatalog,
  collectArchitectureProvenanceClaims,
  latestVersionedArtifact,
} from "./provenance-catalog.js"
import { parseArchitectureQuestionTriage } from "./architecture-review.js"
import { readFile } from "node:fs/promises"
import { resolve } from "node:path"
import { REPO_ROOT } from "./repo.js"
import { saveRun } from "./run-store.js"
import {
  transitionRun,
  type FormalizationStage,
  type GateName,
  type RunState,
} from "./workflow.js"

const GATE_FOR_WAIT_STAGE = new Map<FormalizationStage, GateName>(
  Object.entries(GATES).map(([gate, plan]) => [
    plan.waitingStage,
    gate as GateName,
  ]),
)

export function waitingGateForStage(stage: FormalizationStage): GateName | undefined {
  return GATE_FOR_WAIT_STAGE.get(stage)
}

export type BenchmarkGateParking = {
  reason: "PARKED_SEMANTIC_REVIEW"
  gate: GateName
  issues: string[]
}

export type BenchmarkGateAssessment = {
  blockingIssues: string[]
  semanticAssumptions: BenchmarkSemanticAssumption[]
}

export async function benchmarkGateAssessment(
  run: RunState,
): Promise<BenchmarkGateAssessment> {
  const gate = waitingGateForStage(run.stage)
  if (gate === undefined || run.benchmark?.autoApprove !== true) {
    return { blockingIssues: [], semanticAssumptions: [] }
  }
  try {
    const architectureSource = gate === "A"
      ? await readFile(resolve(REPO_ROOT, await latestVersionedArtifact(
          `${run.artifactRoot}/architecture`,
          [/^foundation-v(\d+)\.md$/],
        )), "utf8")
      : undefined
    const claims = architectureSource !== undefined
      ? collectArchitectureProvenanceClaims(architectureSource, "architecture")
      : gate === "B"
        ? (await buildProvenanceCatalog(run)).claims
        : []
    const openQuestions = claims.filter((claim) =>
      claim.classification === "OPEN_QUESTION" &&
      claim.stateAffecting === true &&
      claim.unresolved
    )
    if (openQuestions.length === 0) {
      return { blockingIssues: [], semanticAssumptions: [] }
    }

    if (gate === "B") {
      return {
        blockingIssues: [],
        semanticAssumptions: openQuestions.map((claim) => ({
          semanticId: claim.semanticId,
          statement: claim.statement,
          rationale: "The Gate-B semantic authority preserves this question as unresolved.",
          policy: "CONSERVATIVE_BOUNDED_SCOPE",
          unresolved: true,
          humanApproved: false,
        })),
      }
    }
    if (gate !== "A") {
      return {
        blockingIssues: openQuestions.map((claim) => `${claim.semanticId}: ${claim.statement}`),
        semanticAssumptions: [],
      }
    }

    const review = await readFile(resolve(REPO_ROOT, await latestVersionedArtifact(
      `${run.artifactRoot}/reviews`,
      [/^architecture-critic-v(\d+)\.md$/],
    )), "utf8")
    const triage = parseArchitectureQuestionTriage(review)
    if (triage === undefined) {
      return {
        blockingIssues: ["architecture critique lacks deterministic open-question triage"],
        semanticAssumptions: [],
      }
    }
    const rationales = new Map(triage.entries.map((entry) => [entry.semanticId, entry]))
    const blockingIssues: string[] = []
    const semanticAssumptions: BenchmarkSemanticAssumption[] = []
    for (const claim of openQuestions) {
      const triaged = rationales.get(claim.semanticId)
      if (triaged?.disposition !== "GENUINE_HUMAN_REVIEW") {
        blockingIssues.push(
          `${claim.semanticId}: open question was not deterministically classified for benchmark continuation`,
        )
        continue
      }
      semanticAssumptions.push({
        semanticId: claim.semanticId,
        statement: claim.statement,
        rationale: triaged.rationale,
        policy: "CONSERVATIVE_BOUNDED_SCOPE",
        unresolved: true,
        humanApproved: false,
      })
    }
    return { blockingIssues, semanticAssumptions }
  } catch (error) {
    return gate === "A" || gate === "B"
      ? {
          blockingIssues: [
            `deterministic semantic readiness check failed: ${error instanceof Error ? error.message : String(error)}`,
          ],
          semanticAssumptions: [],
        }
      : { blockingIssues: [], semanticAssumptions: [] }
  }
}

export async function benchmarkGateReadinessIssues(run: RunState): Promise<string[]> {
  return (await benchmarkGateAssessment(run)).blockingIssues
}

export async function benchmarkGateParking(
  run: RunState,
): Promise<BenchmarkGateParking | undefined> {
  const gate = waitingGateForStage(run.stage)
  if (gate === undefined || run.benchmark?.autoApprove !== true) return undefined
  const issues = await benchmarkGateReadinessIssues(run)
  return issues.length === 0
    ? undefined
    : { reason: "PARKED_SEMANTIC_REVIEW", gate, issues }
}

/**
 * Advances benchmark-only gates without turning them into human approvals.
 *
 * This is shared by the single-run loop and the pipelined batch scheduler so
 * both controllers write the exact same deterministic decision record.
 */
export async function advanceBenchmarkGate(
  run: RunState,
): Promise<{
  run: RunState
  gate: GateName
  reviewPath: string
  recovered: boolean
  semanticAssumptions: BenchmarkSemanticAssumption[]
} | undefined> {
  const gate = waitingGateForStage(run.stage)
  if (gate === undefined || run.benchmark?.autoApprove !== true) return undefined
  const assessment = await benchmarkGateAssessment(run)
  if (assessment.blockingIssues.length > 0) return undefined

  const decision = await recordBenchmarkAutoAdvance(
    run,
    gate,
    assessment.semanticAssumptions,
  )
  const target = gate === "FINAL"
    ? "BENCHMARK_COMPLETE"
    : GATES[gate].approvedStage
  let next = transitionRun(
    run,
    target,
    `${decision.recovered ? "Recovered" : "Recorded"} benchmark-only ${gate} auto-advance; review=${decision.reviewPath}; humanConfirmationRecorded=false`,
  )
  next = {
    ...next,
    gates: {
      ...next.gates,
      [gate]: "benchmark_auto_advanced",
    },
  }
  await saveRun(next)
  return {
    run: next,
    gate,
    reviewPath: decision.reviewPath,
    recovered: decision.recovered,
    semanticAssumptions: assessment.semanticAssumptions,
  }
}
