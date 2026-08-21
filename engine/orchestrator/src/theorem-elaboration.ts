import { randomUUID } from "node:crypto"
import { readFile, unlink, writeFile } from "node:fs/promises"
import { resolve } from "node:path"

import { verifyLeanFile } from "./lean-local.js"
import { leanDeclarationNamespace, leanLanguageName } from "./lean-language.js"
import { packageTransform } from "./lean-package.js"
import { REPO_ROOT } from "./repo.js"
import {
  validateTheoremObligationDocument,
  type TheoremDeclaration,
} from "./theorem-contract.js"
import type { RunState } from "./workflow.js"

function topLevelResultColon(source: string): number | undefined {
  let depth = 0
  let inString = false
  let escaped = false
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index]!
    if (inString) {
      if (escaped) escaped = false
      else if (character === "\\") escaped = true
      else if (character === '"') inString = false
      continue
    }
    if (character === '"') inString = true
    else if (character === "(" || character === "[" || character === "{") depth += 1
    else if (character === ")" || character === "]" || character === "}") depth = Math.max(0, depth - 1)
    else if (character === ":" && depth === 0) return index
  }
  return undefined
}

/** Convert a validated header into a proposition expression without adding a proof or axiom. */
export function theoremTypeExpression(declaration: TheoremDeclaration): string {
  const prefix = `theorem ${declaration.name}`
  if (!declaration.canonicalStatement.startsWith(prefix)) {
    throw new Error(`Malformed canonical theorem header: ${declaration.name}`)
  }
  const tail = declaration.canonicalStatement.slice(prefix.length).trim()
  const colon = topLevelResultColon(tail)
  if (colon === undefined) throw new Error(`Theorem has no top-level result type: ${declaration.name}`)
  const binders = tail.slice(0, colon).trim()
  const result = tail.slice(colon + 1).trim()
  if (result.length === 0) throw new Error(`Theorem has an empty result type: ${declaration.name}`)
  return binders.length === 0 ? `(${result})` : `(∀ ${binders}, ${result})`
}

export async function theoremElaborationIssues(
  run: RunState,
  obligationDocument: unknown,
  leanMappingPath: string,
): Promise<string[]> {
  const contract = validateTheoremObligationDocument(obligationDocument)
  if (contract.issues.length > 0) return contract.issues
  const source = await readFile(resolve(REPO_ROOT, leanMappingPath), "utf8")
  let mapping: string
  try {
    mapping = packageTransform(source, run.leanModuleName, leanLanguageName(run)).text
  } catch (error) {
    return [`could not prepare intended Lean module context: ${error instanceof Error ? error.message : String(error)}`]
  }
  let checks: string
  try {
    checks = contract.declarations.map((declaration) => [
      `-- deterministic theorem-contract elaboration: ${declaration.name}`,
      `#check ${theoremTypeExpression(declaration)}`,
    ].join("\n")).join("\n")
  } catch (error) {
    return [error instanceof Error ? error.message : String(error)]
  }
  const namespace = leanDeclarationNamespace(run)
  const temporaryName = `.spec2lean-theorem-contract-${randomUUID()}.lean`
  const relativePath = `lean/${temporaryName}`
  const absolutePath = resolve(REPO_ROOT, relativePath)
  await writeFile(absolutePath, [
    mapping,
    "",
    `namespace ${namespace}`,
    checks,
    `end ${namespace}`,
    "",
  ].join("\n"), { encoding: "utf8", flag: "wx" })
  try {
    const check = await verifyLeanFile(relativePath, 120_000)
    return check.success
      ? []
      : [`theorem declarations do not elaborate in ${namespace}: ${check.output.slice(-8_000)}`]
  } finally {
    await unlink(absolutePath).catch(() => undefined)
  }
}
