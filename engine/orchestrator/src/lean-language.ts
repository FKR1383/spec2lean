import type { RunState } from "./workflow.js"

const KNOWN_LANGUAGE_NAMES: Record<string, string> = {
  ecmascript: "ECMAScript",
  javascript: "JavaScript",
  ptx: "PTX",
  spirv: "SPIRV",
}

export function makeLeanLanguageName(language: string): string {
  const normalized = language.trim().toLowerCase()
  const known = KNOWN_LANGUAGE_NAMES[normalized]
  if (known !== undefined) return known
  const parts = language.trim().split(/[^A-Za-z0-9]+/).filter(Boolean)
  if (parts.length === 0) throw new Error(`Cannot derive Lean language namespace from: ${language}`)
  return parts.map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join("")
}

export function leanLanguageName(run: RunState): string {
  return makeLeanLanguageName(run.language)
}

export function leanDeclarationNamespace(run: RunState): string {
  return `Spec2Lean.${leanLanguageName(run)}.${run.leanModuleName}`
}

export function leanModuleImport(run: RunState, proofs = false): string {
  return `${leanDeclarationNamespace(run)}${proofs ? "Proofs" : ""}`
}

export function leanPackagePath(run: RunState, proofs = false): string {
  return `lean/${leanModuleImport(run, proofs).replaceAll(".", "/")}.lean`
}
