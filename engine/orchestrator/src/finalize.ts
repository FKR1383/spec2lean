import { copyFile, mkdir, readFile, readdir, writeFile } from "node:fs/promises"
import { createHash } from "node:crypto"
import { spawn } from "node:child_process"
import { basename, dirname, resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"
import { loadRun } from "./run-store.js"
import { verifyTraceabilityManifest, type TraceabilityManifest } from "./traceability.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

function sha256(buffer: Uint8Array): string {
  return createHash("sha256").update(buffer).digest("hex")
}

type ApprovalRecord = {
  decision?: string
  submittedAtUtc?: string
  artifacts?: Array<{ relativePath?: string; sha256?: string; sizeBytes?: number }>
  provenance?: { runId?: string }
}

async function approvalRecord(
  runId: string,
  unitReviewRoot: string,
  directory: string,
): Promise<{ path: string; record: ApprovalRecord }> {
  const root = `${unitReviewRoot}/${directory}`
  const files = await readdir(resolve(REPO_ROOT, root))
  const candidates: Array<{ path: string; record: ApprovalRecord }> = []
  for (const name of files.filter((item) => /approval-v\d+\.json$/.test(item))) {
    const path = `${root}/${name}`
    const record = JSON.parse(await readFile(resolve(REPO_ROOT, path), "utf8")) as ApprovalRecord
    if (record.decision === "approved" && record.provenance?.runId === runId) {
      candidates.push({ path, record })
    }
  }
  candidates.sort((left, right) => String(right.record.submittedAtUtc).localeCompare(String(left.record.submittedAtUtc)))
  if (candidates[0] === undefined) throw new Error(`No human approval record for ${runId} in ${root}`)
  return candidates[0]
}

async function verifyApprovedArtifacts(record: ApprovalRecord): Promise<string[]> {
  if (!Array.isArray(record.artifacts) || record.artifacts.length === 0) {
    throw new Error("Human approval record has no artifact fingerprints")
  }
  const paths: string[] = []
  for (const artifact of record.artifacts) {
    if (artifact.relativePath === undefined || artifact.sha256 === undefined) {
      throw new Error("Human approval record has an incomplete artifact fingerprint")
    }
    const data = await readFile(resolve(REPO_ROOT, artifact.relativePath))
    if (sha256(data) !== artifact.sha256 || (artifact.sizeBytes !== undefined && data.length !== artifact.sizeBytes)) {
      throw new Error(`Human-approved artifact changed: ${artifact.relativePath}`)
    }
    paths.push(artifact.relativePath)
  }
  return paths
}

function referencedSourceBundles(value: unknown, artifactRoot: string, output = new Set<string>()): Set<string> {
  if (typeof value === "string") {
    if (value.startsWith(`${artifactRoot}/source-bundles/`) && /source-bundle-v\d+\.json$/.test(value)) output.add(value)
  } else if (Array.isArray(value)) {
    for (const item of value) referencedSourceBundles(item, artifactRoot, output)
  } else if (typeof value === "object" && value !== null) {
    for (const item of Object.values(value as Record<string, unknown>)) referencedSourceBundles(item, artifactRoot, output)
  }
  return output
}

async function git(args: string[]): Promise<{ code: number; output: string }> {
  return await new Promise((resolvePromise, reject) => {
    const child = spawn("git", args, { cwd: REPO_ROOT, shell: false, stdio: ["ignore", "pipe", "pipe"] })
    let output = ""
    child.stdout.on("data", (x: unknown) => { output += String(x) })
    child.stderr.on("data", (x: unknown) => { output += String(x) })
    child.once("error", reject)
    child.once("exit", (code: number | null) => resolvePromise({ code: code ?? 1, output }))
  })
}

const runId = required("--run")
const push = process.argv.includes("--push")
const run = await loadRun(runId)

if (run.benchmark?.autoApprove === true) {
  throw new Error(
    "Benchmark auto-approve runs are not human-approved and cannot be finalized or promoted",
  )
}

if (run.stage !== "ACCEPTED" || run.gates.FINAL !== "approved") {
  throw new Error(`Run must be at ACCEPTED with FINAL approved; current stage=${run.stage}`)
}

const unitReviewRoot = `reviews/${run.language}-${run.unitSlug}`
const approvals = await Promise.all([
  approvalRecord(run.runId, unitReviewRoot, "gate-a"),
  approvalRecord(run.runId, unitReviewRoot, "gate-b"),
  approvalRecord(run.runId, unitReviewRoot, "gate-c"),
  approvalRecord(run.runId, unitReviewRoot, "theorem-strength"),
  approvalRecord(run.runId, unitReviewRoot, "gate-final"),
])
const approvedArtifacts = (await Promise.all(
  approvals.map(({ record }) => verifyApprovedArtifacts(record)),
)).flat()
const semanticPaths = approvedArtifacts.filter((path) => path.includes("/semantics/") && path.endsWith(".json"))
if (semanticPaths.length !== 1) throw new Error("Gate B must pin exactly one semantic artifact")
const semanticDocument = JSON.parse(await readFile(resolve(REPO_ROOT, semanticPaths[0]!), "utf8")) as unknown
const sourceBundles = [...referencedSourceBundles(semanticDocument, run.artifactRoot)]
if (sourceBundles.length === 0) {
  throw new Error("The human-approved semantic artifact does not pin a source bundle")
}

const approvedLean = new Map<string, string>()
for (const path of approvedArtifacts.filter((item) => item.endsWith(".lean"))) {
  approvedLean.set(path, sha256(await readFile(resolve(REPO_ROOT, path))))
}
const traceabilityDirectory = `runs/${run.runId}/traceability`
const traceabilityPaths: string[] = []
const tracedLean = new Set<string>()
const tracedSourceBundles = new Set<string>()
for (const name of await readdir(resolve(REPO_ROOT, traceabilityDirectory))) {
  if (!/^evidence-[a-f0-9]{64}\.json$/.test(name)) continue
  const path = `${traceabilityDirectory}/${name}`
  const manifest = JSON.parse(await readFile(resolve(REPO_ROOT, path), "utf8")) as TraceabilityManifest
  if (approvedLean.get(manifest.leanDocument.path) !== manifest.leanDocument.sha256) continue
  const issues = await verifyTraceabilityManifest(manifest)
  if (issues.length > 0) continue
  traceabilityPaths.push(path)
  tracedLean.add(manifest.leanDocument.path)
  for (const bundle of manifest.sourceBundles) tracedSourceBundles.add(bundle.path)
}
for (const sourceBundle of sourceBundles) {
  if (!tracedSourceBundles.has(sourceBundle)) {
    throw new Error(`Approved semantics references a source bundle not pinned by complete traceability: ${sourceBundle}`)
  }
}
for (const leanPath of approvedLean.keys()) {
  if (!tracedLean.has(leanPath)) {
    throw new Error(`Human-approved Lean artifact has no complete traceability manifest: ${leanPath}`)
  }
}

const selected = [...new Set([
  ...approvedArtifacts,
  ...sourceBundles,
  ...approvals.map(({ path }) => path),
  ...traceabilityPaths,
])]
const acceptedRoot = `accepted/${run.language}/${run.specVersion}/${run.unitSlug}`
const copied: Array<{ source: string; path: string; sha256: string; sizeBytes: number }> = []

for (const source of selected) {
  const category = source.includes("/architecture/") ? "architecture"
    : source.includes("/source-bundles/") ? "source-bundles"
    : source.includes("/semantics/") ? "semantics"
    : source.includes("/theorems/") ? "theorems"
    : source.includes("/lean/") ? "lean"
    : source.includes("/traceability/") ? "traceability"
    : source.includes("/gate-") || source.includes("/theorem-strength/") ? "human-reviews"
    : "reviews"
  const destination = `${acceptedRoot}/${category}/${basename(source)}`
  await mkdir(resolve(REPO_ROOT, dirname(destination)), { recursive: true })
  await copyFile(resolve(REPO_ROOT, source), resolve(REPO_ROOT, destination))
  const bytes = await readFile(resolve(REPO_ROOT, destination))
  copied.push({ source, path: destination, sha256: sha256(bytes), sizeBytes: bytes.length })
}

const manifestPath = `${acceptedRoot}/accepted-manifest.json`
await writeFile(resolve(REPO_ROOT, manifestPath), `${JSON.stringify({
  schema_version: 1,
  acceptance_id: `${run.language}-${run.specVersion}-${run.unitSlug}-accepted`,
  status: "HUMAN_ACCEPTED",
  run_id: run.runId,
  language: run.language,
  specification_version: run.specVersion,
  unit: run.unit,
  accepted_at_utc: new Date().toISOString(),
  artifacts: copied,
}, null, 2)}\n`, "utf8")

console.log(JSON.stringify({ ok: true, acceptedRoot, manifestPath, artifactCount: copied.length }, null, 2))

if (push) {
  const staged = await git(["diff", "--cached", "--name-only"])
  if (staged.code !== 0) throw new Error(staged.output)
  if (staged.output.trim().length > 0) {
    throw new Error("Git index already contains staged changes; refusing automated milestone commit")
  }

  const paths = [
    acceptedRoot,
    run.artifactRoot,
    `runs/${run.runId}`,
    `reviews/${run.language}-${run.unitSlug}`,
    `lean/Spec2Lean/PTX/${run.leanModuleName}.lean`,
    `lean/Spec2Lean.lean`,
  ]
  const proofPackage = `lean/Spec2Lean/PTX/${run.leanModuleName}Proofs.lean`
  try { await readFile(resolve(REPO_ROOT, proofPackage)); paths.push(proofPackage) } catch {}

  const add = await git(["add", "--", ...paths])
  if (add.code !== 0) throw new Error(add.output)
  const commit = await git(["commit", "-m", `feat: accept Spec2Lean ${run.language} ${run.unit} formalization`])
  if (commit.code !== 0) throw new Error(commit.output)
  const branchResult = await git(["branch", "--show-current"])
  const branch = branchResult.output.trim()
  if (branchResult.code !== 0 || branch.length === 0) {
    throw new Error("Cannot push a finalized run from a detached or unknown Git branch")
  }
  const pushResult = await git(["push", "origin", branch])
  if (pushResult.code !== 0) throw new Error(pushResult.output)
  console.log(JSON.stringify({ committed: true, pushed: true }, null, 2))
}
