import { readFile } from "node:fs/promises"
import { spawn } from "node:child_process"
import { relative, resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"

const LEAN_ROOT = resolve(REPO_ROOT, "lean")

export type LeanCheckResult = {
  success: boolean
  exitCode: number | null
  timedOut: boolean
  stdout: string
  stderr: string
  output: string
}

async function runProcess(
  command: string,
  args: string[],
  cwd: string,
  timeoutMs: number,
): Promise<LeanCheckResult> {
  return await new Promise((resolvePromise, reject) => {
    const child = spawn(command, args, {
      cwd,
      stdio: ["ignore", "pipe", "pipe"],
      shell: false,
    })

    let stdout = ""
    let stderr = ""
    let timedOut = false

    child.stdout.on("data", (chunk: unknown) => { stdout += String(chunk) })
    child.stderr.on("data", (chunk: unknown) => { stderr += String(chunk) })
    child.once("error", reject)

    const timer = setTimeout(() => {
      timedOut = true
      child.kill("SIGTERM")
    }, timeoutMs)

    child.once("exit", (code: number | null) => {
      clearTimeout(timer)
      resolvePromise({
        success: code === 0 && !timedOut,
        exitCode: code,
        timedOut,
        stdout,
        stderr,
        output: [stdout, stderr].filter(Boolean).join("\n").trim(),
      })
    })
  })
}

export async function verifyLeanFile(
  repoRelativePath: string,
  timeoutMs = 60_000,
): Promise<LeanCheckResult> {
  const absolute = resolve(REPO_ROOT, repoRelativePath)
  const leanRelative = relative(LEAN_ROOT, absolute)
  return await runProcess("lake", ["env", "lean", leanRelative], LEAN_ROOT, timeoutMs)
}

export async function buildLeanPackage(
  timeoutMs = 120_000,
): Promise<LeanCheckResult> {
  return await runProcess("lake", ["build"], LEAN_ROOT, timeoutMs)
}

function stripLeanCommentsAndStrings(source: string): string {
  let out = ""
  let i = 0
  let blockDepth = 0
  let inString = false
  let escaped = false

  while (i < source.length) {
    const a = source[i]
    const b = source[i + 1]

    if (blockDepth > 0) {
      if (a === "/" && b === "-") {
        blockDepth += 1
        i += 2
        continue
      }
      if (a === "-" && b === "/") {
        blockDepth -= 1
        i += 2
        continue
      }
      i += 1
      continue
    }

    if (inString) {
      if (escaped) {
        escaped = false
      } else if (a === "\\") {
        escaped = true
      } else if (a === '"') {
        inString = false
      }
      out += " "
      i += 1
      continue
    }

    if (a === "/" && b === "-") {
      blockDepth = 1
      i += 2
      continue
    }

    if (a === "-" && b === "-") {
      while (i < source.length && source[i] !== "\n") i += 1
      out += "\n"
      continue
    }

    if (a === '"') {
      inString = true
      out += " "
      i += 1
      continue
    }

    out += a
    i += 1
  }

  return out
}

export async function prohibitedLeanTokens(
  repoRelativePath: string,
): Promise<string[]> {
  const source = await readFile(resolve(REPO_ROOT, repoRelativePath), "utf8")
  const code = stripLeanCommentsAndStrings(source)
  const matches = code.match(/\b(?:sorry|admit|axiom|unsafe)\b/g) ?? []
  return [...new Set(matches)]
}
