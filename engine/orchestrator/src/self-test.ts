import { randomUUID } from "node:crypto"
import { readFile, unlink } from "node:fs/promises"
import { resolve } from "node:path"

import { parseAgentResult } from "./agent-result.js"
import { makeLeanModuleName, makeUnitSlug } from "./artifact-contract.js"
import {
  artifactPathsForGate,
  verifyHumanDecisionRecord,
  writeHumanDecisionRecord,
} from "./human-decision-record.js"
import { proofTargets } from "./proof-plan.js"
import { REPO_ROOT } from "./repo.js"
import { runSemanticIrSelfTests } from "./semantic-ir-self-test.js"
import { canTransition, type RunState } from "./workflow.js"

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`SELF_TEST_FAILED: ${message}`)
}

assert(makeUnitSlug("mov.b32") === "mov-b32", "unit slug")
assert(makeLeanModuleName("mov.b32") === "MovB32", "Lean module name")
assert(canTransition("ARCHITECTURE_CRITIQUE", "WAITING_GATE_A"), "Gate A transition")
assert(!canTransition("ARCHITECTURE", "LEAN_FORMALIZATION"), "illegal stage skip rejected")

const semanticIrMetrics = await runSemanticIrSelfTests()

const parsed = parseAgentResult(
  'prefix\nSPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"ARCHITECTURE_CRITIQUE","summary":"ok"}',
)
assert(parsed.outcome === "SUCCESS", "result parsing")

const retrievalProfile = JSON.parse(
  await readFile(
    resolve(
      REPO_ROOT,
      "language_packs/ptx/9.3/retrieval-profile.json",
    ),
    "utf8",
  ),
) as {
  specificationVersion?: string
  context?: { sharedSections?: unknown[] }
  policy?: {
    interpretationPerformed?: boolean
    humanApprovalImplied?: boolean
  }
}
assert(
  retrievalProfile.specificationVersion === "9.3",
  "PTX retrieval profile version",
)
assert(
  retrievalProfile.context?.sharedSections?.length === 7,
  "PTX shared retrieval sections",
)
assert(
  retrievalProfile.policy?.interpretationPerformed === false &&
    retrievalProfile.policy?.humanApprovalImplied === false,
  "retrieval profile does not claim semantic approval",
)

const runPath = resolve(REPO_ROOT, "runs/ptx-9.3-mov.b32-f910feea/run.json")
try {
  const run = JSON.parse(await readFile(runPath, "utf8")) as RunState
  const targets = await proofTargets(run)
  assert(targets.length === 16, "mov.b32 proof target extraction")
  assert(new Set(targets.map((x) => x.name)).size === targets.length, "proof target names unique")

  const proofPath = resolve(REPO_ROOT, "candidates/ptx/9.3/units/mov-b32/lean/MovB32Proofs-v1.lean")
  try {
    const proof = await readFile(proofPath, "utf8")
    assert(proof.includes("namespace MovB32"), "mov.b32 proof namespace isolated")
    for (const target of targets) {
      assert(proof.includes(`theorem ${target.name}`), `seed proof contains ${target.name}`)
    }
  } catch (error) {
    if ((error as { code?: string }).code !== "ENOENT") throw error
  }

  const gateArtifacts = await artifactPathsForGate(run, "B")
  assert(
    gateArtifacts[0] ===
      "candidates/ptx/9.3/units/mov-b32/semantics/semantics-v2.json",
    "deterministic Gate B candidate selection",
  )
  assert(
    gateArtifacts[1] ===
      "candidates/ptx/9.3/units/mov-b32/reviews/semantics-critic-v2.md",
    "deterministic Gate B critic selection",
  )

  await verifyHumanDecisionRecord({
    run,
    gate: "B",
    decision: "approved",
    reviewId: "ptx-mov-b32-b-approval-v1",
    reviewPath:
      "reviews/ptx-mov-b32/gate-b/ptx-mov-b32-b-approval-v1.json",
    reviewer: "Human reviewer",
    rationale: "Existing record compatibility check.",
  })

  const reviewId = `controller-decision-self-test-${randomUUID()}`
  const reviewPath = `reviews/tool-tests/${reviewId}.json`
  const decisionInput = {
    run,
    gate: "B" as const,
    decision: "approved" as const,
    reviewId,
    reviewPath,
    reviewer: "Self-test reviewer",
    rationale: "Self-test of deterministic hash-bound human decision recording.",
  }

  try {
    await writeHumanDecisionRecord(decisionInput)
    await verifyHumanDecisionRecord(decisionInput)
    const record = JSON.parse(
      await readFile(resolve(REPO_ROOT, reviewPath), "utf8"),
    ) as { provenance?: { controller?: string }; artifacts?: unknown[] }
    assert(
      record.provenance?.controller === "spec2lean-cli",
      "deterministic decision provenance",
    )
    assert(record.artifacts?.length === 2, "decision artifact fingerprints")
  } finally {
    await unlink(resolve(REPO_ROOT, reviewPath)).catch(() => undefined)
  }
} catch (error) {
  if ((error as { code?: string }).code !== "ENOENT") throw error
}

for (const controller of ["approve", "reject"]) {
  const text = await readFile(
    resolve(REPO_ROOT, `engine/orchestrator/src/${controller}.ts`),
    "utf8",
  )
  assert(!text.includes("startOpenCode"), `${controller} does not start OpenCode`)
  assert(
    text.includes("writeHumanDecisionRecord"),
    `${controller} records decisions deterministically`,
  )
}

const runLoopSource = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/run-loop.ts"),
  "utf8",
)
assert(!runLoopSource.includes("npm\""), "run loop does not spawn npm ticks")
assert(!runLoopSource.includes("spawn("), "run loop executes ticks in-process")
assert(
  runLoopSource.includes("runtime ??= await startOpenCode()"),
  "run loop reuses one lazy OpenCode runtime",
)
assert(
  runLoopSource.includes("await executeTick(runId, { runtime })"),
  "run loop passes the shared runtime into each tick",
)

for (const agent of [
  "lean-formalizer",
  "proof-engineer",
  "semantic-extractor",
  "source-curator",
  "spec-architect",
]) {
  const text = await readFile(resolve(REPO_ROOT, `.opencode/agents/${agent}.md`), "utf8")
  assert(!text.includes("# First Formalization Unit"), `${agent} obsolete first-unit block removed`)
  assert(!text.includes("Do not formalize another PTX instruction."), `${agent} no stale unit lock`)
  assert(!text.includes("Do not prove properties for another PTX instruction."), `${agent} no stale proof lock`)
}

console.log(JSON.stringify({
  ok: true,
  test: "orchestrator-self-test",
  semanticIr: semanticIrMetrics,
}, null, 2))
