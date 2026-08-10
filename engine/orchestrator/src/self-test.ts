import { readFile, readdir } from "node:fs/promises"
import { resolve } from "node:path"

import { parseAgentResult } from "./agent-result.js"
import { normalizeAgentDecision } from "./agent-decision.js"
import {
  artifactContractForRun,
  makeLeanModuleName,
  makeUnitSlug,
} from "./artifact-contract.js"
import {
  DEFAULT_PROVIDER_RETRY_BUDGET_MS,
  ProviderRetryBudgetExceededError,
  findCompletedResponse,
  providerRetryBudgetExceeded,
} from "./async-session.js"
import { verifyLeanFile } from "./lean-local.js"
import { packageTransform } from "./lean-package.js"
import { proofTargets, theoremDeclarationNames } from "./proof-plan.js"
import { loadProjectModel, REPO_ROOT } from "./repo.js"
import { canTransition, type RunState } from "./workflow.js"

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`SELF_TEST_FAILED: ${message}`)
}

assert(makeUnitSlug("mov.b32") === "mov-b32", "unit slug")
assert(makeLeanModuleName("mov.b32") === "MovB32", "Lean module name")
assert(canTransition("ARCHITECTURE_CRITIQUE", "WAITING_GATE_A"), "Gate A transition")
assert(!canTransition("ARCHITECTURE", "LEAN_FORMALIZATION"), "illegal stage skip rejected")
assert(
  !providerRetryBudgetExceeded(1_000, 60_999, DEFAULT_PROVIDER_RETRY_BUDGET_MS),
  "provider retry remains active before the bounded budget",
)
assert(
  providerRetryBudgetExceeded(1_000, 61_000, DEFAULT_PROVIDER_RETRY_BUDGET_MS),
  "provider retry stops at the bounded budget",
)
const providerRetryError = new ProviderRetryBudgetExceededError({
  attempt: 2,
  providerMessage: "rate limited",
  nextRetryAt: 70_000,
  retryElapsedMs: DEFAULT_PROVIDER_RETRY_BUDGET_MS,
  retryBudgetMs: DEFAULT_PROVIDER_RETRY_BUDGET_MS,
})
assert(
  providerRetryError.attempt === 2 &&
    providerRetryError.providerMessage === "rate limited",
  "provider retry diagnostics preserve structured status",
)
assert(
  findCompletedResponse([{
    info: { role: "assistant" },
    parts: [
      {
        type: "text",
        text: 'compaction copy: SPEC2LEAN_RESULT {"outcome":"BLOCKED","nextStage":"BLOCKED","summary":"stale"}',
      },
      { type: "step-finish", reason: "tool-calls" },
    ],
  }]) === undefined,
  "tool-call and compaction turns cannot masquerade as terminal protocol output",
)
assert(
  findCompletedResponse([{
    info: { role: "assistant" },
    parts: [
      {
        type: "text",
        text: 'SPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"ARCHITECTURE_CRITIQUE","summary":"done"}',
      },
      { type: "step-finish", reason: "stop" },
    ],
  }])?.includes('"outcome":"SUCCESS"'),
  "terminal assistant turn supplies protocol output",
)

const baseArtifactRun: RunState = {
  schemaVersion: 1,
  runId: "artifact-retry-self-test",
  mode: "formalization",
  language: "ptx",
  specVersion: "9.3",
  unit: "or.b32",
  unitSlug: "or-b32",
  leanModuleName: "OrB32",
  sourceManifest: "documents/sources/nvidia/ptx/9.3/source-manifest.json",
  artifactRoot: "candidates/ptx/9.3/units/or-b32",
  stage: "SEMANTIC_EXTRACTION",
  createdAt: "2026-01-01T00:00:00.000Z",
  updatedAt: "2026-01-01T00:00:00.000Z",
  revision: 1,
  gates: {
    A: "approved",
    B: "pending",
    C: "pending",
    THEOREM_STRENGTH: "pending",
    FINAL: "pending",
  },
  history: [],
}
const normalizedInvalidDecision = normalizeAgentDecision(baseArtifactRun, {
  outcome: "BLOCKED",
  nextStage: "ARCHITECTURE",
  summary: "invalid target",
})
assert(
  normalizedInvalidDecision.outcome === "RETRY" &&
    normalizedInvalidDecision.nextStage === "SEMANTIC_EXTRACTION",
  "invalid agent workflow decisions become safe retries",
)
assert(
  artifactContractForRun(baseArtifactRun).outputPath.endsWith("semantics-v1.json"),
  "first semantic attempt uses v1",
)
const afterMalformedArtifactRetry: RunState = {
  ...baseArtifactRun,
  executions: [{
    at: "2026-01-01T00:01:00.000Z",
    stage: "SEMANTIC_EXTRACTION",
    agent: "semantic-extractor",
    sessionId: "self-test-session",
    outcome: "RETRY",
    nextStage: "SEMANTIC_EXTRACTION",
    response: "invalid JSON",
  }],
}
assert(
  artifactContractForRun(afterMalformedArtifactRetry).outputPath.endsWith("semantics-v2.json"),
  "retry advances immutable semantic artifact revision",
)
assert(
  artifactContractForRun({
    ...afterMalformedArtifactRetry,
    stage: "PROOF_GENERATION",
    executions: [{
      ...afterMalformedArtifactRetry.executions![0]!,
      stage: "PROOF_GENERATION",
      nextStage: "PROOF_GENERATION",
    }],
  }).outputPath.endsWith("OrB32Proofs-v1.lean"),
  "incremental proof retry retains its progress artifact",
)
assert(
  theoremDeclarationNames([
    "theorem AtColumnZero : True := by trivial",
    " theorem WithLeadingSpace : True := by trivial",
    "\ttheorem WithLeadingTab : True := by trivial",
  ].join("\n")).size === 3,
  "proof progress recognizes indented top-level theorem declarations",
)

const parsed = parseAgentResult(
  'prefix\nSPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"ARCHITECTURE_CRITIQUE","summary":"ok"}',
)
assert(parsed.outcome === "SUCCESS", "result parsing")

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
} catch (error) {
  if ((error as { code?: string }).code !== "ENOENT") throw error
}

const projectModel = await loadProjectModel()
const projectConfig = JSON.parse(
  await readFile(resolve(REPO_ROOT, "opencode.json"), "utf8"),
) as { enabled_providers?: unknown[] }
assert(
  projectConfig.enabled_providers?.includes(projectModel.providerID),
  "project model provider is explicitly enabled",
)

const agentFiles = (await readdir(resolve(REPO_ROOT, ".opencode/agents")))
  .filter((name) => name.endsWith(".md"))
for (const agentFile of agentFiles) {
  const text = await readFile(resolve(REPO_ROOT, `.opencode/agents/${agentFile}`), "utf8")
  assert(text.includes(`model: ${projectModel.full}`), `${agentFile} model matches project model`)
  assert(!text.includes("# First Formalization Unit"), `${agentFile} obsolete first-unit block removed`)
  assert(!text.includes("Do not formalize another PTX instruction."), `${agentFile} no stale unit lock`)
  assert(!text.includes("Do not prove properties for another PTX instruction."), `${agentFile} no stale proof lock`)
}

const candidateTool = await readFile(
  resolve(REPO_ROOT, ".opencode/tools/candidate.ts"),
  "utf8",
)
assert(
  candidateTool.includes("JSON.parse(args.content)") &&
    candidateTool.includes("invalid JSON; artifact was not written"),
  "candidate_write validates JSON before the atomic write",
)

const runnerSource = await readFile(
  resolve(REPO_ROOT, "engine/orchestrator/src/runner.ts"),
  "utf8",
)
assert(
  runnerSource.includes("run.activeExecution.model === runtime.model.full") &&
    runnerSource.match(/model: runtime\.model\.full/g)?.length === 2,
  "active-session recovery is pinned to explicit model provenance",
)

const leanVerifierSmoke = await verifyLeanFile("lean/Spec2Lean/PTX/MovB32.lean")
assert(
  leanVerifierSmoke.success,
  `Lean verifier prepares project imports: ${leanVerifierSmoke.output}`,
)

const dottedNamespaceCandidate = [
  "import Spec2Lean.Basic",
  "namespace Spec2Lean.PTX.OrB32",
  "def marker := true",
  "end Spec2Lean.PTX.OrB32",
  "",
].join("\n")
const dottedPackage = packageTransform(dottedNamespaceCandidate, "OrB32")
assert(
  dottedPackage.text === dottedNamespaceCandidate &&
    dottedPackage.isolatedNamespace === false,
  "Lean packaging accepts an already-isolated dotted unit namespace",
)

const nestedBaseCandidate = [
  "import Spec2Lean.Basic",
  "namespace Spec2Lean",
  "namespace PTX",
  "def marker := true",
  "end PTX",
  "end Spec2Lean",
  "",
].join("\n")
const nestedPackage = packageTransform(nestedBaseCandidate, "TestUnit")
assert(
  nestedPackage.text.includes("namespace TestUnit") &&
    nestedPackage.text.includes("end TestUnit") &&
    nestedPackage.isolatedNamespace === true,
  "Lean packaging still isolates legacy nested PTX candidates",
)

console.log(JSON.stringify({ ok: true, test: "orchestrator-self-test" }, null, 2))
