import { mkdir, readFile, unlink, writeFile } from "node:fs/promises"
import { createHash } from "node:crypto"
import { resolve } from "node:path"

import { buildLeanPackage } from "./lean-local.js"
import {
  leanDeclarationNamespace,
  leanLanguageName,
  leanModuleImport,
  leanPackagePath,
} from "./lean-language.js"
import { proofArtifactPath } from "./proof-plan.js"
import { REPO_ROOT } from "./repo.js"
import { withRepositoryLock } from "./repository-lock.js"
import type { RunState } from "./workflow.js"
import { authoritativeArtifact } from "./artifact-authority.js"

function sha256(text: string): string {
  return createHash("sha256").update(text).digest("hex")
}

export function packageTransform(source: string, moduleName: string, languageName = "PTX"): {
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

  const unitHeader = `namespace Spec2Lean\nnamespace ${languageName}\nnamespace ${moduleName}\n`
  const dottedUnitHeader = `namespace Spec2Lean.${languageName}.${moduleName}\n`
  const baseHeader = `namespace Spec2Lean\nnamespace ${languageName}\n`

  if (!text.includes(unitHeader) && !text.includes(dottedUnitHeader)) {
    if (!text.includes(baseHeader)) {
      throw new Error(`Lean mapping does not contain the expected Spec2Lean.${languageName} namespace header`)
    }
    text = text.replace(baseHeader, unitHeader)

    const footer = `end ${languageName}\nend Spec2Lean`
    const footerIndex = text.lastIndexOf(footer)
    if (footerIndex < 0) {
      throw new Error("Lean mapping does not contain the expected namespace footer")
    }
    text =
      text.slice(0, footerIndex) +
      `end ${moduleName}\nend ${languageName}\nend Spec2Lean` +
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
  const sourcePath = (await authoritativeArtifact(run, "LEAN_MAPPING")).path
  const source = await readFile(resolve(REPO_ROOT, sourcePath), "utf8")
  const languageName = leanLanguageName(run)
  const transformed = packageTransform(source, run.leanModuleName, languageName)

  return await withRepositoryLock("lean-package", async () => {

    const packagePath = leanPackagePath(run)
    const packageAbsolute = resolve(REPO_ROOT, packagePath)
    await mkdir(resolve(REPO_ROOT, `lean/Spec2Lean/${languageName}`), { recursive: true })
    await writeFile(packageAbsolute, transformed.text, "utf8")

    const rootPath = resolve(REPO_ROOT, "lean/Spec2Lean.lean")
    let root = await readFile(rootPath, "utf8")
    const importLine = `import ${leanModuleImport(run)}`
    if (!root.split(/\r?\n/).includes(importLine)) {
      if (!root.endsWith("\n")) root += "\n"
      root += `${importLine}\n`
      await writeFile(rootPath, root, "utf8")
    }

    const build = await buildLeanPackage(leanModuleImport(run))
    if (!build.success) {
      throw new Error(
        `Packaged Lean semantics failed to build:\n${build.output.slice(-8000)}`,
      )
    }

    const info: LeanPackageInfo = {
      sourcePath,
      packagePath,
      moduleImport: leanModuleImport(run),
      declarationNamespace: leanDeclarationNamespace(run),
      sourceSha256: sha256(source),
      packageSha256: sha256(transformed.text),
      isolatedNamespace: transformed.isolatedNamespace,
      importAdjusted: transformed.importAdjusted,
    }

    const recordPath = resolve(REPO_ROOT, `runs/${run.runId}/lean-package.json`)
    await writeFile(recordPath, `${JSON.stringify(info, null, 2)}\n`, "utf8")
    return info
  })
}

export async function installProofPackage(run: RunState): Promise<{
  sourcePath: string
  packagePath: string
  sha256: string
}> {
  return await withRepositoryLock("lean-package", async () => {
    const actualSourcePath = proofArtifactPath(run)
    const source = await readFile(resolve(REPO_ROOT, actualSourcePath), "utf8")
    const packagePath = leanPackagePath(run, true)
    const packageAbsolute = resolve(REPO_ROOT, packagePath)
    await mkdir(resolve(REPO_ROOT, `lean/Spec2Lean/${leanLanguageName(run)}`), { recursive: true })
    const previousPackage = await readFile(packageAbsolute, "utf8").catch(() => undefined)
    await writeFile(packageAbsolute, source, "utf8")

    const rootPath = resolve(REPO_ROOT, "lean/Spec2Lean.lean")
    let root = await readFile(rootPath, "utf8")
    const previousRoot = root
    const importLine = `import ${leanModuleImport(run, true)}`
    if (!root.split(/\r?\n/).includes(importLine)) {
      if (!root.endsWith("\n")) root += "\n"
      root += `${importLine}\n`
      await writeFile(rootPath, root, "utf8")
    }

    const build = await buildLeanPackage(leanModuleImport(run, true))
    if (!build.success) {
      if (previousPackage === undefined) await unlink(packageAbsolute).catch(() => {})
      else await writeFile(packageAbsolute, previousPackage, "utf8")
      await writeFile(rootPath, previousRoot, "utf8")
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
  })
}
