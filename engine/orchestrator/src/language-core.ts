import { createHash } from "node:crypto"
import { readFile } from "node:fs/promises"
import { isAbsolute, relative, resolve, sep } from "node:path"

import { REPO_ROOT } from "./repo.js"
import { validateSharedSemanticEnvironment } from "./semantic-ir/validate.js"

type UnknownRecord = Record<string, unknown>

export type LanguageCore = {
  schemaVersion: 1
  coreId: string
  language: string
  specificationVersion: string
  scope: {
    statement: string
    eligibilityRequirements: string[]
    outsideScopeAction: "BOOTSTRAP_OR_DEEP_REVIEW"
  }
  semanticEnvironment: { path: string; sha256: string }
  leanModule: { path: string; sha256: string; importName: string }
  modelRoles: Record<string, { leanDeclaration: string; semanticIds: string[] }>
  reviewBinding: {
    status: "BOUND_TO_HUMAN_APPROVED_SEMANTICS" | "HUMAN_APPROVED"
    records: Array<{ path: string; sha256: string }>
  }
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function safe(path: string): string {
  if (!path || path.includes("\0") || path.includes("\\") || isAbsolute(path)) {
    throw new Error(`unsafe language-core path: ${path}`)
  }
  const absolute = resolve(REPO_ROOT, path)
  const relation = relative(REPO_ROOT, absolute)
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error(`language-core path escapes repository: ${path}`)
  }
  return absolute
}

function hash(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

function fingerprint(value: unknown, label: string): asserts value is { path: string; sha256: string } {
  if (!isRecord(value) || typeof value.path !== "string" ||
    typeof value.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(value.sha256)) {
    throw new Error(`invalid language-core ${label} fingerprint`)
  }
}

export async function loadLanguageCore(path: string): Promise<LanguageCore> {
  const input = JSON.parse(await readFile(safe(path), "utf8")) as unknown
  if (!isRecord(input) || input.schemaVersion !== 1 ||
    typeof input.coreId !== "string" || typeof input.language !== "string" ||
    typeof input.specificationVersion !== "string" || !isRecord(input.scope) ||
    !isRecord(input.modelRoles) || !isRecord(input.reviewBinding)) {
    throw new Error(`invalid language-core manifest: ${path}`)
  }
  fingerprint(input.semanticEnvironment, "semanticEnvironment")
  const leanModule = input.leanModule
  fingerprint(leanModule, "leanModule")
  if (typeof (leanModule as UnknownRecord).importName !== "string") {
    throw new Error("language-core Lean module lacks importName")
  }
  if (!Array.isArray(input.scope.eligibilityRequirements) ||
    input.scope.eligibilityRequirements.length === 0 ||
    typeof input.scope.statement !== "string" || input.scope.statement.trim().length === 0 ||
    input.scope.outsideScopeAction !== "BOOTSTRAP_OR_DEEP_REVIEW") {
    throw new Error("language-core scope is incomplete")
  }
  if (!["BOUND_TO_HUMAN_APPROVED_SEMANTICS", "HUMAN_APPROVED"].includes(String(input.reviewBinding.status)) ||
    !Array.isArray(input.reviewBinding.records) || input.reviewBinding.records.length === 0) {
    throw new Error("language-core review binding is incomplete")
  }
  for (const [role, value] of Object.entries(input.modelRoles)) {
    if (!isRecord(value) || typeof value.leanDeclaration !== "string" ||
      !Array.isArray(value.semanticIds) || value.semanticIds.length === 0 ||
      value.semanticIds.some((item) => typeof item !== "string")) {
      throw new Error(`invalid language-core model role: ${role}`)
    }
  }
  for (const [label, value] of [
    ["semanticEnvironment", input.semanticEnvironment],
    ["leanModule", input.leanModule],
    ...input.reviewBinding.records.map((record, index) => [`reviewBinding.records[${index}]`, record] as const),
  ] as const) {
    fingerprint(value, label)
    const actual = hash(await readFile(safe(value.path)))
    if (actual !== value.sha256) throw new Error(`language-core ${label} hash mismatch: ${value.path}`)
  }
  const environmentInput = JSON.parse(
    await readFile(safe(input.semanticEnvironment.path), "utf8"),
  ) as unknown
  const environment = validateSharedSemanticEnvironment(environmentInput)
  if (!environment.ok || environment.value === undefined ||
    environment.value.review.status !== "HUMAN_APPROVED" ||
    environment.value.language.toLowerCase() !== input.language.toLowerCase() ||
    environment.value.specificationVersion !== input.specificationVersion) {
    throw new Error("language-core is not bound to a matching HUMAN_APPROVED semantic environment")
  }
  return input as unknown as LanguageCore
}
