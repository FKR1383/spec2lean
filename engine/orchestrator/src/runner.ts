import {
  parseAgentResult,
} from "./agent-result.js"

import {
  startOpenCode,
  unwrap,
} from "./opencode.js"

import {
  loadRun,
  saveRun,
} from "./run-store.js"

import {
  planForRun,
} from "./stage-plan.js"

import {
  canTransition,
  transitionRun,
  type FormalizationStage,
  type RunState,
} from "./workflow.js"

type Agent = {
  name: string
}

type Session = {
  id: string
}

type Part = {
  type: string
  text?: string
}

type PromptResult = {
  parts?: Part[]
}

function argument(
  name: string,
): string | undefined {
  const index =
    process.argv.indexOf(name)

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

function buildPrompt(
  run: RunState,
): string {
  const plan =
    planForRun(run)

  const revisionTargets =
    plan.revisionStages.length === 0
      ? "(none)"
      : plan.revisionStages.join(", ")

  return [
    "# Spec2Lean Automated Agentic Run",
    "",
    `Run ID: ${run.runId}`,
    `Mode: ${run.mode}`,
    `Language: ${run.language}`,
    `Specification version: ${run.specVersion}`,
    `Unit: ${run.unit}`,
    `Current stage: ${run.stage}`,
    `Run revision: ${run.revision}`,
    "",
    "# Stage Task",
    "",
    plan.task,
    "",
    "# Safety Rules",
    "",
    "- Follow AGENTS.md and your agent definition.",
    "- Use repository artifacts as the persistent source of truth.",
    "- Do not approve a human gate.",
    "- Do not promote anything to accepted/.",
    "- Do not skip stages.",
    "- Do not invent source evidence.",
    "- Do not silently weaken semantics or theorem statements.",
    "- Do not use sorry, admit, new axioms, or unsafe.",
    "",
    "# Orchestrator Result Protocol",
    "",
    "After completing your actual stage work, your LAST non-empty line",
    "must be exactly:",
    "",
    "SPEC2LEAN_RESULT {\"outcome\":\"SUCCESS|REVISE|BLOCKED\",\"nextStage\":\"STAGE\",\"summary\":\"short summary\"}",
    "",
    `For SUCCESS, nextStage MUST be: ${plan.successStage}`,
    `Allowed REVISE nextStage values: ${revisionTargets}`,
    "For BLOCKED, nextStage MUST be: BLOCKED",
    "",
    "Do not place Markdown fences around the SPEC2LEAN_RESULT line.",
  ].join("\n")
}

function validateDecision(
  run: RunState,
  result: ReturnType<typeof parseAgentResult>,
): FormalizationStage {
  const plan =
    planForRun(run)

  const next =
    result.nextStage

  if (result.outcome === "SUCCESS") {
    if (next !== plan.successStage) {
      throw new Error(
        `Agent attempted invalid SUCCESS target: ${next}; expected ${plan.successStage}`,
      )
    }
  }

  if (result.outcome === "REVISE") {
    if (
      !plan.revisionStages.includes(next)
    ) {
      throw new Error(
        `Agent attempted invalid REVISE target: ${next}`,
      )
    }
  }

  if (result.outcome === "BLOCKED") {
    if (next !== "BLOCKED") {
      throw new Error(
        "BLOCKED outcome must target BLOCKED",
      )
    }
  }

  if (
    !canTransition(
      run.stage,
      next,
    )
  ) {
    throw new Error(
      `Workflow rejects transition ${run.stage} -> ${next}`,
    )
  }

  return next
}

async function main(): Promise<void> {
  const runId =
    required("--run")

  const dryRun =
    process.argv.includes("--dry-run")

  const run =
    await loadRun(runId)

  const plan =
    planForRun(run)

  const prompt =
    buildPrompt(run)

  if (dryRun) {
    console.log(
      JSON.stringify(
        {
          dryRun: true,
          runId: run.runId,
          stage: run.stage,
          agent: plan.agent,
          successStage:
            plan.successStage,
          revisionStages:
            plan.revisionStages,
          prompt,
        },
        null,
        2,
      ),
    )

    return
  }

  const runtime =
    await startOpenCode()

  try {
    const { client } =
      runtime.runtime

    const agents =
      unwrap<Agent[]>(
        await client.app.agents(),
      )

    if (
      !agents.some(
        (agent) =>
          agent.name === plan.agent,
      )
    ) {
      throw new Error(
        `Required agent not found: ${plan.agent}`,
      )
    }

    const session =
      unwrap<Session>(
        await client.session.create({
          body: {
            title:
              `Spec2Lean ${run.runId} ${run.stage}`,
          },
        }),
      )

    if (!session.id) {
      throw new Error(
        "OpenCode did not return a session ID",
      )
    }

    const promptResult =
      unwrap<PromptResult>(
        await client.session.prompt({
          path: {
            id: session.id,
          },

          body: {
            agent: plan.agent,

            model: {
              providerID:
                runtime.model.providerID,

              modelID:
                runtime.model.modelID,
            },

            parts: [
              {
                type: "text",
                text: prompt,
              },
            ],
          },
        }),
      )

    const response =
      (promptResult.parts ?? [])
        .filter(
          (part) =>
            part.type === "text",
        )
        .map(
          (part) =>
            part.text ?? "",
        )
        .join("\n")
        .trim()

    const result =
      parseAgentResult(response)

    const nextStage =
      validateDecision(
        run,
        result,
      )

    let nextRun =
      transitionRun(
        run,
        nextStage,
        `${plan.agent}: ${result.summary}`,
      )

    nextRun = {
      ...nextRun,

      executions: [
        ...(run.executions ?? []),

        {
          at: new Date().toISOString(),
          stage: run.stage,
          agent: plan.agent,
          sessionId: session.id,
          outcome: result.outcome,
          nextStage,
          response,
        },
      ],
    }

    await saveRun(nextRun)

    console.log(
      JSON.stringify(
        {
          ok: true,
          runId: nextRun.runId,
          agent: plan.agent,
          sessionId: session.id,
          outcome: result.outcome,
          fromStage: run.stage,
          toStage: nextRun.stage,
          revision:
            nextRun.revision,
          summary:
            result.summary,
        },
        null,
        2,
      ),
    )
  } finally {
    runtime.runtime.server.close()
  }
}

await main()
