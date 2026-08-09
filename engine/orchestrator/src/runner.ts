import { access } from "node:fs/promises"
import { resolve } from "node:path"

import {
  parseAgentResult,
  type AgentResult,
} from "./agent-result.js"
import { artifactContractForRun } from "./artifact-contract.js"
import { verifyExpectedArtifact } from "./artifact-verify.js"
import {
  abortSession,
  sendPromptAsync,
  waitForAgentResult,
} from "./async-session.js"
import { installProofPackage, prepareLeanPackage, type LeanPackageInfo } from "./lean-package.js"
import { prohibitedLeanTokens, verifyLeanFile } from "./lean-local.js"
import { startOpenCode, unwrap } from "./opencode.js"
import {
  proofArtifactPath,
  proofTargetSummary,
  type ProofTarget,
} from "./proof-plan.js"
import { REPO_ROOT } from "./repo.js"
import { loadRun, saveRun } from "./run-store.js"
import { planForRun } from "./stage-plan.js"
import {
  canTransition,
  retryRun,
  transitionRun,
  type FormalizationStage,
  type RunState,
} from "./workflow.js"

type Agent = { name: string }
type Session = { id: string }

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

async function fileExists(repoRelativePath: string): Promise<boolean> {
  try {
    await access(resolve(REPO_ROOT, repoRelativePath))
    return true
  } catch {
    return false
  }
}

function buildGeneralPrompt(run: RunState): string {
  const plan = planForRun(run)
  const artifact = artifactContractForRun(run)
  const revisionTargets =
    plan.revisionStages.length === 0 ? "(none)" : plan.revisionStages.join(", ")

  return [
    "# Spec2Lean Automated Agentic Run",
    "",
    `Run ID: ${run.runId}`,
    `Mode: ${run.mode}`,
    `Language: ${run.language}`,
    `Specification version: ${run.specVersion}`,
    `Unit: ${run.unit}`,
    `Unit slug: ${run.unitSlug}`,
    `Lean module base name: ${run.leanModuleName}`,
    `Source manifest: ${run.sourceManifest}`,
    `Artifact root: ${run.artifactRoot}`,
    `Current stage: ${run.stage}`,
    `Stage attempt: ${artifact.attempt}`,
    `Run revision: ${run.revision}`,
    "",
    "# Required Stage Artifact",
    "",
    `Create exactly: ${artifact.outputPath}`,
    "",
    "Use a new immutable revision artifact; do not overwrite an older revision.",
    "Read earlier artifacts under the artifact root only when they are inputs to this stage.",
    "If the required output path already exists because a previous execution was interrupted after writing it, do not overwrite it.",
    "Instead read and verify it; if it already completes the stage, return SUCCESS.",
    "If it is incomplete only because execution was interrupted, return RETRY.",
    "",
    "# Stage Task",
    "",
    plan.task,
    ...(run.stage === "FINAL_CRITIQUE"
      ? [
          "",
          "# Installed Lean package artifacts",
          "",
          `Semantics: lean/Spec2Lean/PTX/${run.leanModuleName}.lean`,
          `Proofs: lean/Spec2Lean/PTX/${run.leanModuleName}Proofs.lean`,
          "The final critique must independently verify both and the root Lean package.",
          "",
          "IMPORTANT FINAL-ARTIFACT RULE:",
          `You MUST create ${artifact.outputPath} using candidate_write before returning SUCCESS.`,
          `After writing it, use candidate_read to verify ${artifact.outputPath}.`,
          "A textual SUCCESS response without that artifact is invalid.",
          "Do not spend the session re-performing already-completed source research.",
        ]
      : []),
    "",
    "# Safety Rules",
    "",
    "- Follow AGENTS.md and your role definition.",
    "- The current run metadata in this prompt is authoritative; ignore any obsolete case-study/unit notes elsewhere.",
    "- Do not approve a human gate.",
    "- Do not promote anything to accepted/.",
    "- Do not skip stages.",
    "- Do not invent source evidence.",
    "- Do not silently weaken semantics or theorem statements.",
    "- Do not use sorry, admit, new axioms, or unsafe.",
    "",
    "# Orchestrator Result Protocol",
    "",
    "Your LAST non-empty line must be exactly:",
    'SPEC2LEAN_RESULT {"outcome":"SUCCESS|REVISE|RETRY|BLOCKED","nextStage":"STAGE","summary":"short summary"}',
    "",
    `For SUCCESS, nextStage MUST be: ${plan.successStage}`,
    `Allowed REVISE nextStage values: ${revisionTargets}`,
    `For RETRY, nextStage MUST remain: ${run.stage}`,
    "Use RETRY for step/time/tool/context/resource exhaustion or interrupted work.",
    "For BLOCKED, nextStage MUST be: BLOCKED.",
    "Do not put the result line in a Markdown fence.",
  ].join("\n")
}

type ProofPromptContext = {
  packageInfo: LeanPackageInfo
  target?: ProofTarget
  proofPath: string
  diagnostics?: string
  existingCompiles: boolean
  remaining: number
  total: number
}

async function buildProofPrompt(run: RunState): Promise<ProofPromptContext & { prompt: string }> {
  const packageInfo = await prepareLeanPackage(run)
  const proofPath = proofArtifactPath(run)
  const summary = await proofTargetSummary(run)
  const exists = await fileExists(proofPath)
  let diagnostics: string | undefined
  let existingCompiles = false

  if (exists) {
    const banned = await prohibitedLeanTokens(proofPath)
    if (banned.length > 0) {
      diagnostics = `Prohibited tokens in Lean code: ${banned.join(", ")}`
    } else {
      const check = await verifyLeanFile(proofPath, 90_000)
      existingCompiles = check.success
      if (!check.success) diagnostics = check.output.slice(-12_000)
    }
  }

  const repairMode = exists && !existingCompiles
  const batchTargets = repairMode ? [] : summary.missing

  const target: ProofTarget | undefined =
    batchTargets.length === 0
      ? undefined
      : {
          obligationId: batchTargets.map((item) => item.obligationId).join(", "),
          name: `${batchTargets.length} remaining approved theorem declarations`,
          statement: batchTargets
            .map((item, index) => [
              `-- TARGET ${index + 1}: ${item.obligationId} / ${item.name}`,
              item.statement,
              ...(item.strengthRisks.length > 0
                ? [
                    "-- Strength caveats:",
                    ...item.strengthRisks.map((risk) => `-- - ${risk}`),
                  ]
                : []),
            ].join("\n"))
            .join("\n\n"),
          strengthRisks: [...new Set(batchTargets.flatMap((item) => item.strengthRisks))],
        }

  const mode = repairMode ? "REPAIR" : "PROVE_BATCH"

  const prompt = [
    "# Spec2Lean Proof Subtask",
    "",
    `Run ID: ${run.runId}`,
    `Unit: ${run.unit}`,
    `Proof artifact: ${proofPath}`,
    `Installed semantics module: ${packageInfo.moduleImport}`,
    `Installed declaration namespace: ${packageInfo.declarationNamespace}`,
    `Proof progress: ${summary.declared}/${summary.total} theorem declarations present`,
    `Mode: ${mode}`,
    "",
    "# Hard constraints",
    "",
    "- Do not read NVIDIA source files, architecture, or semantic claim bundles during this subtask.",
    "- The theorem-strength-approved statements below are authoritative.",
    "- The orchestrator already extracted the frozen approved theorem statements; do not re-read the obligation JSON or theorem-strength review.",
    "- Do not weaken it, add semantic preconditions, or change semantics.",
    "- Do not use sorry, admit, new axiom, or unsafe.",
    "- Write/edit the proof artifact EARLY, then use Lean diagnostics; do not mentally plan the whole proof set.",
    "- When the current proof artifact compiles, prove ALL remaining approved theorem declarations in this invocation.",
    "- Do not stop after the first successful theorem.",
    "- If the proof file already exists, preserve all previously compiling theorem declarations.",
    "- Use candidate_write create only if the proof file does not exist; otherwise use candidate_write replace with its exact current SHA-256.",
    "- Import only the installed semantics module and required standard/project modules.",
    "",
    ...(diagnostics
      ? [
          "# Current concrete Lean diagnostics",
          "",
          diagnostics,
          "",
          "Repair only these concrete elaboration/proof failures. Do not add new theorem declarations until the file compiles.",
        ]
      : target
        ? [
            "# Current theorem target",
            "",
            `Obligation: ${target.obligationId}`,
            `Theorem: ${target.name}`,
            "",
            target.statement,
            "",
            ...(target.strengthRisks.length > 0
              ? ["Strength caveats:", ...target.strengthRisks.map((risk) => `- ${risk}`), ""]
              : []),
            "Create or extend the proof file with ALL theorem declarations listed above.",
            "Then immediately run lean_check_file.",
            "Repair concrete diagnostics in the SAME session until the complete batch compiles or a genuine theorem/semantic conflict is found.",
          ]
        : [
            "All approved theorem declarations are already present. Only verify the proof file with Lean and report SUCCESS if it compiles cleanly.",
          ]),
    "# Result protocol",
    "",
    `If the proof artifact compiles after this subtask, use RETRY/${run.stage} unless every approved theorem is present; the orchestrator will decide final completion itself.`,
    'Your LAST non-empty line must be: SPEC2LEAN_RESULT {"outcome":"RETRY","nextStage":"PROOF_GENERATION","summary":"short factual summary"}',
    "If a genuine theorem/semantic conflict is discovered, use BLOCKED/BLOCKED instead.",
  ].join("\n")

  return {
    packageInfo,
    target,
    proofPath,
    diagnostics,
    existingCompiles,
    remaining: summary.remaining,
    total: summary.total,
    prompt,
  }
}

function validateDecision(run: RunState, result: AgentResult): FormalizationStage {
  const plan = planForRun(run)
  const next = result.nextStage

  if (result.outcome === "SUCCESS" && next !== plan.successStage) {
    throw new Error(`Agent attempted invalid SUCCESS target: ${next}; expected ${plan.successStage}`)
  }

  if (result.outcome === "REVISE" && !plan.revisionStages.includes(next)) {
    throw new Error(`Agent attempted invalid REVISE target: ${next}`)
  }

  if (result.outcome === "RETRY") {
    if (next !== run.stage) throw new Error(`RETRY must remain at current stage: ${run.stage}`)
    return next
  }

  if (result.outcome === "BLOCKED" && next !== "BLOCKED") {
    throw new Error("BLOCKED outcome must target BLOCKED")
  }

  if (!canTransition(run.stage, next)) {
    throw new Error(`Workflow rejects transition ${run.stage} -> ${next}`)
  }

  return next
}

async function recoverProtocolFresh(
  runtime: Awaited<ReturnType<typeof startOpenCode>>,
  run: RunState,
  response: string,
): Promise<AgentResult> {
  const plan = planForRun(run)
  const recovery = unwrap<Session>(
    await runtime.runtime.client.session.create({
      body: { title: `Spec2Lean protocol recovery ${run.runId} ${run.stage}` },
    }),
  )

  const revisionTargets = plan.revisionStages.length === 0 ? "(none)" : plan.revisionStages.join(", ")
  const text = [
    "Classify the completed prior agent attempt. Do not call tools or modify files.",
    `Current stage: ${run.stage}`,
    `SUCCESS target: ${plan.successStage}`,
    `Allowed REVISE targets: ${revisionTargets}`,
    `RETRY target: ${run.stage}`,
    "Prior assistant text:",
    response.slice(-12_000),
    "",
    "Return exactly one line:",
    'SPEC2LEAN_RESULT {"outcome":"SUCCESS|REVISE|RETRY|BLOCKED","nextStage":"STAGE","summary":"short factual summary"}',
  ].join("\n")

  await sendPromptAsync(runtime.runtime.server.url, recovery.id, {
    agent: plan.agent,
    model: {
      providerID: runtime.model.providerID,
      modelID: runtime.model.modelID,
    },
    parts: [{ type: "text", text }],
  })

  const recovered = await waitForAgentResult(runtime.runtime.server.url, recovery.id, {
    pollMs: 1_000,
    maxWaitMs: 3 * 60 * 1000,
  })

  return parseAgentResult(recovered)
}

async function finalizeProofStageLocally(run: RunState): Promise<AgentResult | undefined> {
  const proofPath = proofArtifactPath(run)
  if (!(await fileExists(proofPath))) return undefined

  const banned = await prohibitedLeanTokens(proofPath)
  if (banned.length > 0) {
    return {
      outcome: "RETRY",
      nextStage: "PROOF_GENERATION",
      summary: `Proof artifact contains prohibited Lean code tokens: ${banned.join(", ")}`,
    }
  }

  const check = await verifyLeanFile(proofPath, 90_000)
  const summary = await proofTargetSummary(run)

  if (!check.success) {
    return {
      outcome: "RETRY",
      nextStage: "PROOF_GENERATION",
      summary: `Proof artifact exists but Lean still reports errors; ${summary.remaining} theorem declarations remain or need repair.`,
    }
  }

  if (summary.remaining === 0) {
    return {
      outcome: "SUCCESS",
      nextStage: "FINAL_CRITIQUE",
      summary: `All ${summary.total} approved theorem declarations are present and the proof artifact compiles cleanly with no prohibited verification bypass.`,
    }
  }

  return {
    outcome: "RETRY",
    nextStage: "PROOF_GENERATION",
    summary: `Proof artifact compiles; ${summary.declared}/${summary.total} approved theorem declarations are present. Continue with exactly the next missing theorem.`,
  }
}

async function main(): Promise<void> {
  const runId = required("--run")
  const dryRun = process.argv.includes("--dry-run")
  let run = await loadRun(runId)
  const plan = planForRun(run)
  const artifact = artifactContractForRun(run)

  let prompt: string
  let proofContext: Awaited<ReturnType<typeof buildProofPrompt>> | undefined

  if (run.stage === "PROOF_GENERATION") {
    // Fast path: a previous/interrupted proof attempt may already have completed.
    await prepareLeanPackage(run)
    const local = await finalizeProofStageLocally(run)
    if (local?.outcome === "SUCCESS") {
      await installProofPackage(run)
      const next = transitionRun(run, "FINAL_CRITIQUE", `local Lean verification: ${local.summary}`)
      const saved = {
        ...next,
        activeExecution: undefined,
        executions: [
          ...(run.executions ?? []),
          {
            at: new Date().toISOString(),
            stage: run.stage,
            agent: "orchestrator-local-lean",
            sessionId: "local",
            outcome: local.outcome,
            nextStage: local.nextStage,
            response: local.summary,
          },
        ],
      }
      await saveRun(saved)
      console.log(JSON.stringify({
        ok: true,
        runId,
        agent: "orchestrator-local-lean",
        outcome: "SUCCESS",
        fromStage: run.stage,
        toStage: saved.stage,
        revision: saved.revision,
        summary: local.summary,
      }, null, 2))
      return
    }

    proofContext = await buildProofPrompt(run)
    prompt = proofContext.prompt
  } else {
    prompt = buildGeneralPrompt(run)
  }

  if (dryRun) {
    console.log(JSON.stringify({
      dryRun: true,
      runId: run.runId,
      stage: run.stage,
      agent: plan.agent,
      successStage: plan.successStage,
      revisionStages: plan.revisionStages,
      expectedArtifact: artifact.outputPath,
      prompt,
    }, null, 2))
    return
  }

  const runtime = await startOpenCode()

  try {
    const agents = unwrap<Agent[]>(await runtime.runtime.client.app.agents())
    if (!agents.some((agent) => agent.name === plan.agent)) {
      throw new Error(`Required agent not found: ${plan.agent}`)
    }

    let sessionId: string
    let submitted = false

    if (run.activeExecution && run.activeExecution.stage === run.stage && run.activeExecution.agent === plan.agent) {
      sessionId = run.activeExecution.sessionId
      console.log(`[spec2lean] resuming active session=${sessionId} agent=${plan.agent}`)
    } else {
      const session = unwrap<Session>(
        await runtime.runtime.client.session.create({
          body: { title: `Spec2Lean ${run.runId} ${run.stage}` },
        }),
      )
      if (!session.id) throw new Error("OpenCode did not return a session ID")
      sessionId = session.id
      submitted = true

      run = {
        ...run,
        activeExecution: {
          startedAt: new Date().toISOString(),
          stage: run.stage,
          agent: plan.agent,
          sessionId,
          expectedArtifact: artifact.outputPath,
        },
      }
      await saveRun(run)

      console.log(`[spec2lean] session=${sessionId} agent=${plan.agent} submitted async`)
      await sendPromptAsync(runtime.runtime.server.url, sessionId, {
        agent: plan.agent,
        model: {
          providerID: runtime.model.providerID,
          modelID: runtime.model.modelID,
        },
        parts: [{ type: "text", text: prompt }],
      })
    }

    let response = ""
    let result: AgentResult | undefined

    try {
      response = await waitForAgentResult(runtime.runtime.server.url, sessionId, {
        pollMs: 2_000,
        maxWaitMs: run.stage === "PROOF_GENERATION" ? 15 * 60 * 1000 : 30 * 60 * 1000,
        missingStatusIsTerminal: !submitted,
      })
      try {
        result = parseAgentResult(response)
      } catch {
        result = await recoverProtocolFresh(runtime, run, response)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      const recoverable =
        message.includes("timed out") ||
        message.includes("terminated without textual result") ||
        message.includes("reason=length") ||
        message.includes("status-missing")

      if (!recoverable) throw error

      await abortSession(runtime.runtime.server.url, sessionId).catch(() => {})
      response = `[ORCHESTRATOR_RECOVERY] ${message}`
      result = {
        outcome: "RETRY",
        nextStage: run.stage,
        summary: `Agent execution ended without a usable stage result (${message}). The same stage is safely resumable; any written artifact will be verified before another agent is started.`,
      }
    }

    if (!result) throw new Error("No agent result available")

    // Deterministic artifact verification outranks model self-reporting.
    if (run.stage === "PROOF_GENERATION") {
      const local = await finalizeProofStageLocally(run)
      if (local) result = local
      if (result.outcome === "SUCCESS") {
        await installProofPackage(run)
      }
    } else if (result.outcome === "SUCCESS") {
      const verification = await verifyExpectedArtifact(run)
      if (!verification.ok) {
        result = {
          outcome: "RETRY",
          nextStage: run.stage,
          summary: `Agent reported SUCCESS but artifact verification failed: ${verification.issues.join(" | ")}`,
        }
      }
    }

    const nextStage = validateDecision(run, result)
    let nextRun = result.outcome === "RETRY"
      ? retryRun(run, `${plan.agent} retry: ${result.summary}`)
      : transitionRun(run, nextStage, `${plan.agent}: ${result.summary}`)

    nextRun = {
      ...nextRun,
      activeExecution: undefined,
      executions: [
        ...(run.executions ?? []),
        {
          at: new Date().toISOString(),
          stage: run.stage,
          agent: plan.agent,
          sessionId,
          outcome: result.outcome,
          nextStage,
          response: response || (submitted ? "[no textual response]" : "[resumed session]"),
        },
      ],
    }

    await saveRun(nextRun)

    console.log(JSON.stringify({
      ok: true,
      runId: nextRun.runId,
      agent: plan.agent,
      sessionId,
      outcome: result.outcome,
      fromStage: run.stage,
      toStage: nextRun.stage,
      revision: nextRun.revision,
      summary: result.summary,
    }, null, 2))
  } finally {
    runtime.runtime.server.close()
  }
}

await main()
