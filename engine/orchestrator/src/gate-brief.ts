import {
  sendPromptAsync,
  waitForAssistantText,
} from "./async-session.js"

import {
  GATES,
} from "./gates.js"

import {
  startOpenCode,
  unwrap,
} from "./opencode.js"

import {
  loadRun,
} from "./run-store.js"

import type {
  GateName,
} from "./workflow.js"

type Session = {
  id: string
}

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

function normalizeGate(
  raw: string,
): GateName {
  const gate = raw.toUpperCase()

  if (
    gate !== "A" &&
    gate !== "B" &&
    gate !== "C" &&
    gate !== "THEOREM_STRENGTH" &&
    gate !== "FINAL"
  ) {
    throw new Error(
      `Unsupported gate: ${raw}`,
    )
  }

  return gate
}

async function main(): Promise<void> {
  const runId =
    required("--run")

  const gate =
    normalizeGate(
      required("--gate"),
    )

  const run =
    await loadRun(runId)

  const plan =
    GATES[gate]

  if (run.stage !== plan.waitingStage) {
    throw new Error(
      [
        `Run is not waiting at Gate ${gate}.`,
        `Current=${run.stage}`,
        `Expected=${plan.waitingStage}`,
      ].join(" "),
    )
  }

  const runtime =
    await startOpenCode()

  try {
    const session =
      unwrap<Session>(
        await runtime.runtime.client.session.create({
          body: {
            title:
              `Spec2Lean Gate ${gate} human brief ${run.runId}`,
          },
        }),
      )

    const prompt = [
      "# Spec2Lean Human Gate Brief",
      "",
      `Run ID: ${run.runId}`,
      `Language: ${run.language}`,
      `Specification version: ${run.specVersion}`,
      `Unit: ${run.unit}`,
      `Gate: ${gate}`,
      `Artifact root: ${run.artifactRoot}`,
      "",
      "You are the Spec Manager.",
      "",
      "This is READ-ONLY human review preparation.",
      "Do not edit artifacts.",
      "Do not call review_submit.",
      "Do not approve or reject the gate.",
      "Do not advance workflow state.",
      "",
      `Read runs/${run.runId}/run.json and the latest artifacts relevant to Gate ${gate}`,
      `under ${run.artifactRoot}.`,
      "",
      "Produce a concise human gate brief containing exactly these sections:",
      "",
      "1. WHAT IS BEING APPROVED",
      "2. CRITIC VERDICT",
      "3. BLOCKER / MAJOR / MINOR / NOTE COUNTS",
      "4. HUMAN ASSUMPTIONS REQUIRING EXPLICIT ACCEPTANCE",
      "5. OPEN QUESTIONS",
      "6. STATE-AFFECTING UNRESOLVED GAPS",
      "7. SOURCE-FAITHFULNESS RISKS",
      "8. WHAT THIS APPROVAL AUTHORIZES",
      "9. WHAT THIS APPROVAL DOES NOT AUTHORIZE",
      "10. RECOMMENDATION: APPROVE / DO NOT APPROVE",
      "",
      "For every human assumption:",
      "- quote or closely preserve its artifact wording",
      "- give its claim/assumption ID if present",
      "- state whether it is source-supported, derived, design-level, or human-assumed",
      "- state whether it affects resulting machine state",
      "",
      "Do not hide uncertainty.",
      "Do not reinterpret an assumption as a source fact.",
      "",
      "Keep the brief under 1200 words.",
    ].join("\n")

    await sendPromptAsync(
      runtime.runtime.server.url,
      session.id,
      {
        agent: "spec-manager",

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
    )

    /*
      This task intentionally does not use SPEC2LEAN_RESULT.
      Poll session messages directly until the assistant has produced
      a substantive review brief.
    */

    const response =
      await waitForAssistantText(
        runtime.runtime.server.url,
        session.id,
        {
          pollMs: 2_000,
          maxWaitMs: 10 * 60 * 1000,
        },
      )

    console.log(response)
  } finally {
    runtime.runtime.server.close()
  }
}

await main()
