import { randomUUID } from "node:crypto"
import { spawn } from "node:child_process"
import { unlink, writeFile } from "node:fs/promises"
import { relative, resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"

const LEAN_ROOT = resolve(REPO_ROOT, "lean")
const MARKER = "SPEC2LEAN_DECLARATION_RANGE"

export type LeanDerivedDeclarationRange = {
  leanName: string
  startLine: number
  endLine: number
}

function probeSource(source: string): string {
  return [
    "import Lean.Elab.Command",
    source,
    "",
    "open Lean Elab",
    "run_cmd do",
    "  let env ← getEnv",
    "  for (name, _) in env.constants.toList do",
    "    if env.getModuleIdxFor? name |>.isNone then",
    "      if let some ranges ← findDeclarationRanges? name then",
    `        IO.println s!\"${MARKER}\\t{name}\\t{ranges.range.pos.line}\\t{ranges.range.endPos.line}\"`,
    "",
  ].join("\n")
}

async function runLean(path: string, timeoutMs: number): Promise<{ code: number | null; output: string }> {
  return await new Promise((resolvePromise, reject) => {
    const child = spawn("lake", ["env", "lean", relative(LEAN_ROOT, path)], {
      cwd: LEAN_ROOT,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    })
    let output = ""
    child.stdout.on("data", (chunk: unknown) => { output += String(chunk) })
    child.stderr.on("data", (chunk: unknown) => { output += String(chunk) })
    child.once("error", reject)
    const timer = setTimeout(() => child.kill("SIGTERM"), timeoutMs)
    child.once("exit", (code: number | null) => {
      clearTimeout(timer)
      resolvePromise({ code, output })
    })
  })
}

/** Elaborate the exact candidate and ask Lean for declaration source ranges. */
export async function leanDerivedDeclarationRanges(
  source: string,
  timeoutMs = 90_000,
): Promise<LeanDerivedDeclarationRange[]> {
  const path = resolve(LEAN_ROOT, `.spec2lean-declaration-index-${randomUUID()}.lean`)
  await writeFile(path, probeSource(source), { encoding: "utf8", flag: "wx" })
  try {
    const result = await runLean(path, timeoutMs)
    if (result.code !== 0) {
      throw new Error(`Lean declaration indexing failed:\n${result.output.slice(-8_000)}`)
    }
    const ranges = result.output.split(/\r?\n/).flatMap((line) => {
      const [marker, leanName, start, end] = line.split("\t")
      if (marker !== MARKER || leanName === undefined || start === undefined || end === undefined) return []
      // The probe prepends exactly one import line.
      const startLine = Number(start) - 1
      const endLine = Number(end) - 1
      return Number.isSafeInteger(startLine) && Number.isSafeInteger(endLine) && startLine > 0
        ? [{ leanName, startLine, endLine }]
        : []
    })
    if (ranges.length === 0) {
      throw new Error("Lean elaborated the file but returned no declaration ranges")
    }
    return ranges
  } finally {
    await unlink(path).catch(() => undefined)
  }
}
