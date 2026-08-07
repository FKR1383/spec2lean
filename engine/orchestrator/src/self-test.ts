import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import { parseAgentResult } from "./agent-result.js"
import { makeLeanModuleName, makeUnitSlug } from "./artifact-contract.js"
import { proofTargets } from "./proof-plan.js"
import { REPO_ROOT } from "./repo.js"
import { canTransition, type RunState } from "./workflow.js"

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`SELF_TEST_FAILED: ${message}`)
}

assert(makeUnitSlug("mov.b32") === "mov-b32", "unit slug")
assert(makeLeanModuleName("mov.b32") === "MovB32", "Lean module name")
assert(canTransition("ARCHITECTURE_CRITIQUE", "WAITING_GATE_A"), "Gate A transition")
assert(!canTransition("ARCHITECTURE", "LEAN_FORMALIZATION"), "illegal stage skip rejected")

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

console.log(JSON.stringify({ ok: true, test: "orchestrator-self-test" }, null, 2))
