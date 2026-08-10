import { mkdir, readFile, readdir, writeFile } from "node:fs/promises"
import { createHash } from "node:crypto"
import { resolve } from "node:path"

import { buildLeanPackage } from "./lean-local.js"
import { REPO_ROOT } from "./repo.js"
import type { RunState } from "./workflow.js"

function sha256(text: string): string {
  return createHash("sha256").update(text).digest("hex")
}

async function latestMappingPath(run: RunState): Promise<string> {
  const dirRelative = `${run.artifactRoot}/lean`
  const dir = resolve(REPO_ROOT, dirRelative)
  const files = (await readdir(dir)) as string[]
  const pattern = new RegExp(`^${run.leanModuleName}-v(\\d+)\\.lean$`)
  const matches = files
    .map((name) => ({ name, match: name.match(pattern) }))
    .filter((x): x is { name: string; match: RegExpMatchArray } => x.match !== null)
    .map((x) => ({ name: x.name, version: Number(x.match[1]!) }))
    .sort((a, b) => b.version - a.version)

  if (matches.length === 0) {
    throw new Error(`No Lean mapping candidate found under ${dirRelative}`)
  }

  return `${dirRelative}/${matches[0]!.name}`
}

export function packageTransform(source: string, moduleName: string): {
  text: string
  isolatedNamespace: boolean
  importAdjusted: boolean
} {
  let text = source
  let importAdjusted = false
  let isolatedNamespace = false

  if (text.includes("import Spec2Lean\n")) {
    text = text.replace("import Spec2Lean\n", "import Spec2Lean.Basic\n")
    importAdjusted = true
  }

  const unitHeader = `namespace Spec2Lean\nnamespace PTX\nnamespace ${moduleName}\n`
  const dottedUnitHeader = `namespace Spec2Lean.PTX.${moduleName}\n`
  const baseHeader = "namespace Spec2Lean\nnamespace PTX\n"

  if (!text.includes(unitHeader) && !text.includes(dottedUnitHeader)) {
    if (!text.includes(baseHeader)) {
      throw new Error("Lean mapping does not contain the expected Spec2Lean.PTX namespace header")
    }
    text = text.replace(baseHeader, unitHeader)

    const footer = "end PTX\nend Spec2Lean"
    const footerIndex = text.lastIndexOf(footer)
    if (footerIndex < 0) {
      throw new Error("Lean mapping does not contain the expected namespace footer")
    }
    text =
      text.slice(0, footerIndex) +
      `end ${moduleName}\nend PTX\nend Spec2Lean` +
      text.slice(footerIndex + footer.length)

    isolatedNamespace = true
  }

  return { text, isolatedNamespace, importAdjusted }
}

export type LeanPackageInfo = {
  sourcePath: string
  packagePath: string
  moduleImport: string
  declarationNamespace: string
  sourceSha256: string
  packageSha256: string
  isolatedNamespace: boolean
  importAdjusted: boolean
}

export async function prepareLeanPackage(run: RunState): Promise<LeanPackageInfo> {
  const sourcePath = await latestMappingPath(run)
  const source = await readFile(resolve(REPO_ROOT, sourcePath), "utf8")
  const transformed = packageTransform(source, run.leanModuleName)

  const packagePath = `lean/Spec2Lean/PTX/${run.leanModuleName}.lean`
  const packageAbsolute = resolve(REPO_ROOT, packagePath)
  await mkdir(resolve(REPO_ROOT, "lean/Spec2Lean/PTX"), { recursive: true })
  await writeFile(packageAbsolute, transformed.text, "utf8")

  const rootPath = resolve(REPO_ROOT, "lean/Spec2Lean.lean")
  let root = await readFile(rootPath, "utf8")
  const importLine = `import Spec2Lean.PTX.${run.leanModuleName}`
  if (!root.split(/\r?\n/).includes(importLine)) {
    if (!root.endsWith("\n")) root += "\n"
    root += `${importLine}\n`
    await writeFile(rootPath, root, "utf8")
  }

  const build = await buildLeanPackage()
  if (!build.success) {
    throw new Error(
      `Packaged Lean semantics failed to build:\n${build.output.slice(-8000)}`,
    )
  }

  const info: LeanPackageInfo = {
    sourcePath,
    packagePath,
    moduleImport: `Spec2Lean.PTX.${run.leanModuleName}`,
    declarationNamespace: `Spec2Lean.PTX.${run.leanModuleName}`,
    sourceSha256: sha256(source),
    packageSha256: sha256(transformed.text),
    isolatedNamespace: transformed.isolatedNamespace,
    importAdjusted: transformed.importAdjusted,
  }

  const recordPath = resolve(REPO_ROOT, `runs/${run.runId}/lean-package.json`)
  await writeFile(recordPath, `${JSON.stringify(info, null, 2)}\n`, "utf8")
  return info
}

export async function installProofPackage(run: RunState): Promise<{
  sourcePath: string
  packagePath: string
  sha256: string
}> {
  const dirRelative = `${run.artifactRoot}/lean`
  const files = (await readdir(resolve(REPO_ROOT, dirRelative))) as string[]
  const pattern = new RegExp(`^${run.leanModuleName}Proofs-v(\\d+)\\.lean$`)
  const matches = files
    .map((name) => ({ name, m: name.match(pattern) }))
    .filter((x): x is { name: string; m: RegExpMatchArray } => x.m !== null)
    .map((x) => ({ name: x.name, version: Number(x.m[1]!) }))
    .sort((a, b) => b.version - a.version)

  if (matches.length === 0) {
    throw new Error(`No proof candidate found under ${dirRelative}`)
  }

  const actualSourcePath = `${dirRelative}/${matches[0]!.name}`
  const source = await readFile(resolve(REPO_ROOT, actualSourcePath), "utf8")
  const packagePath = `lean/Spec2Lean/PTX/${run.leanModuleName}Proofs.lean`
  await writeFile(resolve(REPO_ROOT, packagePath), source, "utf8")

  const rootPath = resolve(REPO_ROOT, "lean/Spec2Lean.lean")
  let root = await readFile(rootPath, "utf8")
  const importLine = `import Spec2Lean.PTX.${run.leanModuleName}Proofs`
  if (!root.split(/\r?\n/).includes(importLine)) {
    if (!root.endsWith("\n")) root += "\n"
    root += `${importLine}\n`
    await writeFile(rootPath, root, "utf8")
  }

  const build = await buildLeanPackage()
  if (!build.success) {
    throw new Error(`Packaged proof module failed to build:\n${build.output.slice(-8000)}`)
  }

  const record = {
    sourcePath: actualSourcePath,
    packagePath,
    sha256: sha256(source),
  }
  await writeFile(
    resolve(REPO_ROOT, `runs/${run.runId}/lean-proof-package.json`),
    `${JSON.stringify(record, null, 2)}\n`,
    "utf8",
  )
  return record
}
