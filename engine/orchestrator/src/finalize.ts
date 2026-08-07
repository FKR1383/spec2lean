import { copyFile, mkdir, readFile, readdir, writeFile } from "node:fs/promises"
import { createHash } from "node:crypto"
import { spawn } from "node:child_process"
import { basename, dirname, resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"
import { loadRun } from "./run-store.js"

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

async function latestVersioned(dirRelative: string, regex: RegExp): Promise<string> {
  const files = (await readdir(resolve(REPO_ROOT, dirRelative))) as string[]
  const matches = files
    .map((name) => ({ name, m: name.match(regex) }))
    .filter((x): x is { name: string; m: RegExpMatchArray } => x.m !== null)
    .map((x) => ({ name: x.name, version: Number(x.m[1]!) }))
    .sort((a, b) => b.version - a.version)
  if (matches.length === 0) throw new Error(`No matching final artifact in ${dirRelative}`)
  return `${dirRelative}/${matches[0]!.name}`
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

if (run.stage !== "ACCEPTED" || run.gates.FINAL !== "approved") {
  throw new Error(`Run must be at ACCEPTED with FINAL approved; current stage=${run.stage}`)
}

const architecture = await latestVersioned(`${run.artifactRoot}/architecture`, /^foundation-v(\d+)\.md$/)
const sourceBundle = await latestVersioned(`${run.artifactRoot}/source-bundles`, /^source-bundle-v(\d+)\.json$/)
const semantics = await latestVersioned(`${run.artifactRoot}/semantics`, /^semantics-v(\d+)\.json$/)
const obligations = await latestVersioned(`${run.artifactRoot}/theorems`, /^obligations-v(\d+)\.json$/)
const mapping = await latestVersioned(`${run.artifactRoot}/lean`, new RegExp(`^${run.leanModuleName}-v(\\d+)\\.lean$`))
const proofs = await latestVersioned(`${run.artifactRoot}/lean`, new RegExp(`^${run.leanModuleName}Proofs-v(\\d+)\\.lean$`))
const finalCritic = await latestVersioned(`${run.artifactRoot}/reviews`, /^final-critic-v(\d+)\.md$/)

const selected = [architecture, sourceBundle, semantics, obligations, mapping, proofs, finalCritic]
const acceptedRoot = `accepted/${run.language}/${run.specVersion}/${run.unitSlug}`
const copied: Array<{ source: string; path: string; sha256: string; sizeBytes: number }> = []

for (const source of selected) {
  const category = source.includes("/architecture/") ? "architecture"
    : source.includes("/source-bundles/") ? "source-bundles"
    : source.includes("/semantics/") ? "semantics"
    : source.includes("/theorems/") ? "theorems"
    : source.includes("/lean/") ? "lean"
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
  const pushResult = await git(["push", "origin", "main"])
  if (pushResult.code !== 0) throw new Error(pushResult.output)
  console.log(JSON.stringify({ committed: true, pushed: true }, null, 2))
}
