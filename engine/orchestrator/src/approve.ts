import {
  access,
  readFile,
} from "node:fs/promises"

import { resolve } from "node:path"

import {
  sendPromptAsync,
  waitForAgentResult,
} from "./async-session.js"

import {
  parseAgentResult,
} from "./agent-result.js"

import {
  GATES,
} from "./gates.js"

import {
  startOpenCode,
  unwrap,
} from "./opencode.js"

import {
  REPO_ROOT,
} from "./repo.js"

import {
  loadRun,
  saveRun,
} from "./run-store.js"

import {
  transitionRun,
  type GateName,
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
  value: string,
): GateName {
  const gate =
    value.toUpperCase()

  if (
    gate !== "A" &&
    gate !== "B" &&
    gate !== "C" &&
    gate !== "THEOREM_STRENGTH" &&
    gate !== "FINAL"
  ) {
    throw new Error(
      `Unsupported gate: ${value}`,
    )
  }

  return gate
}

function unitIdForRun(
  language: string,
  unitSlug: string,
): string {
  return `${language}-${unitSlug}`
}

function reviewIdForGate(
  unitId: string,
  gate: GateName,
): string {
  return [
    unitId,
    gate
      .toLowerCase()
      .replaceAll("_", "-"),
    "approval-v1",
  ].join("-")
}

function gateDirectory(
  gate: GateName,
): string {
  return gate
    .toLowerCase()
    .replaceAll("_", "-")
}

function expectedReviewPath(
  unitId: string,
  gate: GateName,
  reviewId: string,
): string {
  if (gate === "THEOREM_STRENGTH") {
    return [
      "reviews",
      unitId,
      "theorem-strength",
      `${reviewId}.json`,
    ].join("/")
  }

  return [
    "reviews",
    unitId,
    `gate-${gateDirectory(gate)}`,
    `${reviewId}.json`,
  ].join("/")
}

function reviewRecordType(
  gate: GateName,
): "human_gate_decision" | "human_theorem_strength_decision" {
  return gate === "THEOREM_STRENGTH"
    ? "human_theorem_strength_decision"
    : "human_gate_decision"
}

function reviewToolGate(
  gate: GateName,
): string {
  return gate === "THEOREM_STRENGTH"
    ? "C"
    : gate
}

async function verifyReviewRecord(
  relativePath: string,
  expectedGate: string,
  requireGateApprovalPerformed: boolean,
): Promise<void> {
  const absolutePath =
    resolve(
      REPO_ROOT,
      relativePath,
    )

  await access(absolutePath)

  const body =
    await readFile(
      absolutePath,
      "utf8",
    )

  const record =
    JSON.parse(body) as {
      decision?: string
      gate?: string
      humanConfirmationRecorded?: boolean
      gateApprovalPerformed?: boolean
    }

  if (
    record.decision !==
    "approved"
  ) {
    throw new Error(
      "Review record does not contain decision=approved",
    )
  }

  if (
    record.gate !== expectedGate
  ) {
    throw new Error(
      `Gate mismatch in review record: expected ${expectedGate}, got ${record.gate}`,
    )
  }

  if (
    record.humanConfirmationRecorded !== true
  ) {
    throw new Error(
      "Human confirmation was not recorded",
    )
  }

  if (
    requireGateApprovalPerformed &&
    record.gateApprovalPerformed !== true
  ) {
    throw new Error(
      "Gate approval was not performed",
    )
  }
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

  if (
    run.stage !==
    plan.waitingStage
  ) {
    throw new Error(
      [
        `Run is not waiting at Gate ${gate}.`,
        `Current stage=${run.stage}.`,
        `Expected=${plan.waitingStage}.`,
      ].join(" "),
    )
  }

  if (
    run.gates[gate] ===
    "approved"
  ) {
    throw new Error(
      `Gate ${gate} is already approved`,
    )
  }

  const unitId =
    unitIdForRun(
      run.language,
      run.unitSlug,
    )

  const reviewId =
    reviewIdForGate(
      unitId,
      gate,
    )

  const reviewPath =
    expectedReviewPath(
      unitId,
      gate,
      reviewId,
    )

  // Idempotent recovery:
  // review_submit records are immutable. If a previous invocation successfully
  // wrote the human decision but the controller crashed afterward, reuse that
  // verified record instead of submitting it again.
  let reviewAlreadyExists = false

  try {
    await access(
      resolve(
        REPO_ROOT,
        reviewPath,
      ),
    )

    reviewAlreadyExists = true
  } catch {
    reviewAlreadyExists = false
  }

  if (reviewAlreadyExists) {
    await verifyReviewRecord(
      reviewPath,
      reviewToolGate(gate),
      gate !== "THEOREM_STRENGTH",
    )

    let recovered =
      transitionRun(
        run,
        plan.approvedStage,
        `Recovered previously recorded human ${gate} approval; review=${reviewPath}`,
      )

    recovered = {
      ...recovered,
      gates: {
        ...recovered.gates,
        [gate]: "approved",
      },
    }

    await saveRun(recovered)

    console.log(
      JSON.stringify(
        {
          ok: true,
          recovered: true,
          runId,
          gate,
          decision: "approved",
          reviewPath,
          fromStage: run.stage,
          toStage: recovered.stage,
          revision: recovered.revision,
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
    const session =
      unwrap<Session>(
        await runtime.runtime.client.session.create({
          body: {
            title:
              `Spec2Lean Gate ${gate} approval ${run.runId}`,
          },
        }),
      )

    if (!session.id) {
      throw new Error(
        "OpenCode did not return a session ID",
      )
    }

    const prompt = [
      "# Spec2Lean Explicit Human Approval",
      "",
      `Run ID: ${run.runId}`,
      `Language: ${run.language}`,
      `Specification version: ${run.specVersion}`,
      `Unit: ${run.unit}`,
      `Artifact root: ${run.artifactRoot}`,
      `Current stage: ${run.stage}`,
      `Human gate: ${gate}`,
      "",
      `The human operator explicitly invoked the approval command for Gate ${gate}.`,
      "This invocation is the explicit human APPROVE decision.",
      "",
      "You are the Spec Manager.",
      "",
      "Before recording the decision:",
      `- read runs/${run.runId}/run.json`,
      `- inspect the latest relevant artifacts under ${run.artifactRoot}`,
      "- confirm the workflow is at the stated human waiting stage",
      "",
      "Then call review_submit exactly once.",
      "",
      "Use:",
      `recordType: ${reviewRecordType(gate)}`,
      `reviewId: ${reviewId}`,
      `unitId: ${unitId}`,
      `gate: ${reviewToolGate(gate)}`,
      "decision: approved",
      "reviewer: Human reviewer",
      "",
      "rationale:",
      `The human operator explicitly approved Gate ${gate} for run ${run.runId} after the automated workflow reached its human-review boundary. This authorizes only the next workflow stage and is not final acceptance unless gate=FINAL.`,
      "",
      "Include the latest relevant candidate artifact and independent critique",
      "for this gate in artifactPaths.",
      "Only use paths accepted by review_submit.",
      "",
      "humanConfirmation:",
      "I_CONFIRM_THIS_IS_AN_EXPLICIT_HUMAN_DECISION",
      "",
      "Do not promote anything.",
      "Do not execute the next workflow stage.",
      "",
      "Your LAST non-empty line must be exactly:",
      `SPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"${plan.approvedStage}","summary":"Human Gate ${gate} approval recorded"}`,
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

    const response =
      await waitForAgentResult(
        runtime.runtime.server.url,
        session.id,
        {
          pollMs: 2_000,
          maxWaitMs:
            10 * 60 * 1000,
        },
      )

    const result =
      parseAgentResult(response)

    if (
      result.outcome !==
      "SUCCESS"
    ) {
      throw new Error(
        `Gate recording failed: outcome=${result.outcome}`,
      )
    }

    if (
      result.nextStage !==
      plan.approvedStage
    ) {
      throw new Error(
        [
          "Spec Manager returned invalid post-gate stage.",
          `Expected=${plan.approvedStage}`,
          `Got=${result.nextStage}`,
        ].join(" "),
      )
    }

    await verifyReviewRecord(
      reviewPath,
      reviewToolGate(gate),
      gate !== "THEOREM_STRENGTH",
    )

    let next =
      transitionRun(
        run,
        plan.approvedStage,
        `Human Gate ${gate} approved; review=${reviewPath}`,
      )

    next = {
      ...next,

      gates: {
        ...next.gates,
        [gate]: "approved",
      },
    }

    await saveRun(next)

    console.log(
      JSON.stringify(
        {
          ok: true,
          runId,
          gate,
          decision: "approved",
          reviewPath,
          fromStage: run.stage,
          toStage: next.stage,
          revision: next.revision,
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
