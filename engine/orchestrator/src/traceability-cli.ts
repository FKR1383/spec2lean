import { createHash } from "node:crypto"
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises"
import { dirname, isAbsolute, relative, resolve, sep } from "node:path"

import { REPO_ROOT } from "./repo.js"
import {
  buildTraceabilityManifest,
  traceabilityManifestPath,
  verifyTraceabilityManifest,
  writeTraceabilityManifest,
  type TraceabilityManifest,
} from "./traceability.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function argumentsFor(name: string): string[] {
  const values: string[] = []
  for (let index = 0; index < process.argv.length; index += 1) {
    if (process.argv[index] === name && process.argv[index + 1] !== undefined) {
      values.push(process.argv[index + 1]!)
    }
  }
  return values
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

function repositoryPath(path: string): string {
  if (path.length === 0 || path.includes("\0") || path.includes("\\") || isAbsolute(path)) {
    throw new Error(`Unsafe repository-relative path: ${path}`)
  }
  const absolute = resolve(REPO_ROOT, path)
  const relation = relative(REPO_ROOT, absolute)
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error(`Path escapes repository: ${path}`)
  }
  return absolute
}

async function loadManifest(path: string): Promise<TraceabilityManifest> {
  return JSON.parse(await readFile(repositoryPath(path), "utf8")) as TraceabilityManifest
}

async function build(): Promise<void> {
  const runId = required("--run")
  const requestedDocument = argument("--document") ?? "semantics"
  if (requestedDocument !== "semantics" && requestedDocument !== "proofs") {
    throw new Error("--document must be semantics or proofs")
  }
  const sourceBundlePaths = argumentsFor("--source-bundle")
  const manifest = await buildTraceabilityManifest({
    runId,
    documentRole: requestedDocument === "proofs" ? "PROOFS" : "SEMANTICS",
    leanPath: argument("--lean"),
    semanticPath: argument("--semantics"),
    sourceBundlePaths: sourceBundlePaths.length === 0 ? undefined : sourceBundlePaths,
    theoremPath: argument("--theorems"),
    includePdfRenditions: process.argv.includes("--pdf-boxes"),
  })
  const outputPath = argument("--output") ?? traceabilityManifestPath(manifest)
  await writeTraceabilityManifest(manifest, outputPath)
  const issues = await verifyTraceabilityManifest(manifest)
  console.log(JSON.stringify({
    ok: issues.length === 0,
    outputPath,
    entries: manifest.entries.length,
    evidenceLinks: manifest.entries.reduce((sum, entry) => sum + entry.evidence.length, 0),
    diagnostics: manifest.diagnostics,
    issues,
  }, null, 2))
  if (issues.length > 0) process.exitCode = 1
}

async function validate(): Promise<void> {
  const path = required("--manifest")
  const manifest = await loadManifest(path)
  const issues = await verifyTraceabilityManifest(manifest)
  console.log(JSON.stringify({ ok: issues.length === 0, path, issues }, null, 2))
  if (issues.length > 0) process.exitCode = 1
}

async function audit(): Promise<void> {
  const runEntries = await readdir(resolve(REPO_ROOT, "runs"), { withFileTypes: true })
  const rows: Array<{
    runId: string
    semantics: number
    proofs: number
    entries: number
    linkedEntries: number
    invalidManifests: number
    missing: string[]
  }> = []
  for (const runEntry of runEntries.filter((entry) => entry.isDirectory())) {
    const runId = runEntry.name
    try {
      await readFile(resolve(REPO_ROOT, "runs", runId, "run.json"))
    } catch {
      continue
    }
    let names: string[] = []
    try {
      names = (await readdir(resolve(REPO_ROOT, "runs", runId, "traceability")))
        .filter((name) => /^evidence-[a-f0-9]{64}\.json$/.test(name))
    } catch {
      // A run without a traceability directory is reported as missing both roles.
    }
    let semantics = 0
    let proofs = 0
    let entries = 0
    let linkedEntries = 0
    let invalidManifests = 0
    for (const name of names) {
      const manifest = await loadManifest(`runs/${runId}/traceability/${name}`)
      const issues = await verifyTraceabilityManifest(manifest)
      if (issues.length > 0) {
        invalidManifests += 1
        continue
      }
      const role = manifest.documentRole ?? "SEMANTICS"
      if (role === "PROOFS") proofs += 1
      else semantics += 1
      entries += manifest.entries.length
      linkedEntries += manifest.entries.filter((entry) =>
        entry.semanticIds.length > 0 || entry.evidence.length > 0,
      ).length
    }
    const missing = [
      ...(semantics === 0 ? ["SEMANTICS"] : []),
      ...(proofs === 0 ? ["PROOFS"] : []),
    ]
    rows.push({ runId, semantics, proofs, entries, linkedEntries, invalidManifests, missing })
  }
  rows.sort((left, right) => left.runId.localeCompare(right.runId))
  const ok = rows.length > 0 && rows.every((row) => row.missing.length === 0 && row.invalidManifests === 0)
  console.log(JSON.stringify({ ok, runs: rows.length, coverage: rows }, null, 2))
  if (!ok) process.exitCode = 1
}

type FeedbackDecision = "CONFIRM_MAPPING" | "REQUEST_CHANGE" | "QUESTION"

async function feedback(): Promise<void> {
  const manifestPath = required("--manifest")
  const manifestData = await readFile(repositoryPath(manifestPath))
  const manifest = JSON.parse(manifestData.toString("utf8")) as TraceabilityManifest
  const manifestIssues = await verifyTraceabilityManifest(manifest)
  if (manifestIssues.length > 0) {
    throw new Error(`Traceability manifest verification failed: ${manifestIssues.join("; ")}`)
  }
  const entryId = required("--entry")
  const entry = manifest.entries.find((candidate) => candidate.entryId === entryId)
  if (entry === undefined) throw new Error(`Unknown traceability entry: ${entryId}`)
  const decision = required("--decision") as FeedbackDecision
  if (!(["CONFIRM_MAPPING", "REQUEST_CHANGE", "QUESTION"] as string[]).includes(decision)) {
    throw new Error(`Unsupported feedback decision: ${decision}`)
  }
  const submittedAtUtc = new Date().toISOString()
  const reviewer = required("--reviewer").trim()
  const comment = required("--comment").trim()
  if (reviewer.length === 0) throw new Error("Reviewer must not be empty")
  if (comment.length === 0) throw new Error("Feedback comment must not be empty")
  const record = {
    schemaVersion: 1,
    recordType: "human_traceability_feedback",
    feedbackId: `${manifest.runId}-${entry.declarationName}-${submittedAtUtc}`,
    runId: manifest.runId,
    unit: manifest.unit,
    reviewer,
    submittedAtUtc,
    decision,
    comment,
    target: {
      manifestPath,
      manifestSha256: createHash("sha256").update(manifestData).digest("hex"),
      leanPath: manifest.leanDocument.path,
      leanSha256: manifest.leanDocument.sha256,
      entryId,
      declarationName: entry.declarationName,
      semanticIds: entry.semanticIds,
      evidenceIds: entry.evidence.map((item) => item.evidenceId),
    },
    humanConfirmationRecorded: true,
    gateApprovalPerformed: false,
    promotionPerformed: false,
    provenance: {
      controller: "spec2lean-gui",
      command: "traceability feedback",
    },
  }
  const recordHash = createHash("sha256")
    .update(JSON.stringify(record))
    .digest("hex")
  const unitSlug = manifest.unit.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase()
  if (unitSlug.length === 0) throw new Error(`Cannot derive feedback path from unit: ${manifest.unit}`)
  const languageSlug = manifest.language.replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase()
  if (languageSlug.length === 0) throw new Error(`Cannot derive feedback path from language: ${manifest.language}`)
  const outputPath = `reviews/${languageSlug}-${unitSlug}/traceability-feedback/${recordHash}.json`
  const destination = repositoryPath(outputPath)
  await mkdir(dirname(destination), { recursive: true })
  await writeFile(destination, `${JSON.stringify(record, null, 2)}\n`, { encoding: "utf8", flag: "wx" })
  console.log(JSON.stringify({ ok: true, outputPath, gateApprovalPerformed: false }, null, 2))
}

switch (process.argv[2]) {
  case "build":
    await build()
    break
  case "validate":
    await validate()
    break
  case "audit":
    await audit()
    break
  case "feedback":
    await feedback()
    break
  default:
    throw new Error([
      "Usage:",
      "  traceability build --run <run-id> [--document semantics|proofs] [--pdf-boxes] [--lean <path>] [--semantics <path>] [--source-bundle <path>]... [--theorems <path>] [--output <path>]",
      "  traceability validate --manifest <path>",
      "  traceability audit",
      "  traceability feedback --manifest <path> --entry <entry-id> --decision CONFIRM_MAPPING|REQUEST_CHANGE|QUESTION --reviewer <name> --comment <text>",
    ].join("\n"))
}
