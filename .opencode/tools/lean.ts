import { tool } from "@opencode-ai/plugin"
import { createHash } from "node:crypto"
import { spawn } from "node:child_process"
import { lstat, readFile, realpath } from "node:fs/promises"
import {
  extname,
  isAbsolute,
  normalize,
  relative,
  resolve,
  sep,
} from "node:path"

const TOOL_VERSION = 2
const MAX_FILE_BYTES = 2 * 1024 * 1024
const MAX_PROCESS_OUTPUT_BYTES = 256 * 1024
const LEAN_CANDIDATE_BASE_TARGET = "Spec2Lean.Basic"

const ALLOWED_ROOTS = [
  "lean",
  "candidates",
  "accepted",
] as const

type ProcessResult = {
  exitCode: number | null
  signal: NodeJS.Signals | null
  timedOut: boolean
  outputLimitExceeded: boolean
  stdout: string
  stderr: string
  durationMs: number
}

type Diagnostic = {
  severity: "error" | "warning" | "information"
  file: string
  line: number
  column: number
  message: string
}

function jsonResult(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

function normalizeLeanPath(path: string): string {
  if (
    path.length === 0 ||
    path.includes("\0") ||
    path.includes("\\") ||
    isAbsolute(path)
  ) {
    throw new Error("path must be a relative POSIX path")
  }

  const normalized = normalize(path)

  if (
    normalized === "." ||
    normalized === ".." ||
    normalized.startsWith(`..${sep}`)
  ) {
    throw new Error("path escapes the project worktree")
  }

  if (extname(normalized).toLowerCase() !== ".lean") {
    throw new Error("only .lean files are supported")
  }

  return normalized
}

function ensureInsideRoot(root: string, candidate: string): void {
  const relation = relative(root, candidate)

  if (
    relation === ".." ||
    relation.startsWith(`..${sep}`) ||
    isAbsolute(relation)
  ) {
    throw new Error("Lean file escapes its allowed root")
  }
}

async function resolveLeanFile(
  worktree: string,
  requestedPath: string,
): Promise<{
  absolutePath: string
  relativePath: string
  data: Buffer
}> {
  const relativePath = normalizeLeanPath(requestedPath)
  const firstComponent = relativePath.split(sep)[0]

  if (!ALLOWED_ROOTS.includes(
    firstComponent as (typeof ALLOWED_ROOTS)[number],
  )) {
    throw new Error(
      `Lean file must be under one of: ${ALLOWED_ROOTS.join(", ")}`,
    )
  }

  const projectRoot = await realpath(worktree)
  const allowedRoot = await realpath(
    resolve(projectRoot, firstComponent),
  )

  const lexicalPath = resolve(projectRoot, relativePath)
  ensureInsideRoot(allowedRoot, lexicalPath)

  const metadata = await lstat(lexicalPath)

  if (metadata.isSymbolicLink()) {
    throw new Error("symbolic-link Lean files are not allowed")
  }

  if (!metadata.isFile()) {
    throw new Error("requested Lean path is not a regular file")
  }

  if (metadata.size > MAX_FILE_BYTES) {
    throw new Error(
      `Lean file exceeds the ${MAX_FILE_BYTES}-byte limit`,
    )
  }

  const canonicalPath = await realpath(lexicalPath)
  ensureInsideRoot(allowedRoot, canonicalPath)

  const data = await readFile(canonicalPath)

  return {
    absolutePath: canonicalPath,
    relativePath,
    data,
  }
}

function safeChildEnvironment(): Record<string, string> {
  const environment: Record<string, string> = {}

  for (const key of [
    "PATH",
    "HOME",
    "ELAN_HOME",
    "XDG_CACHE_HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
  ]) {
    const value = process.env[key]

    if (value !== undefined) {
      environment[key] = value
    }
  }

  return environment
}

async function runLake(
  worktree: string,
  args: string[],
  timeoutSeconds: number,
): Promise<ProcessResult> {
  const projectRoot = await realpath(worktree)
  const leanRoot = await realpath(resolve(projectRoot, "lean"))
  const startedAt = Date.now()

  return await new Promise<ProcessResult>((resolveResult, reject) => {
    const child = spawn(
      "lake",
      args,
      {
        cwd: leanRoot,
        env: safeChildEnvironment(),
        shell: false,
        stdio: ["ignore", "pipe", "pipe"],
      },
    )

    const stdoutChunks: Buffer[] = []
    const stderrChunks: Buffer[] = []

    let stdoutBytes = 0
    let stderrBytes = 0
    let timedOut = false
    let outputLimitExceeded = false
    let finished = false

    const finish = (
      exitCode: number | null,
      signal: NodeJS.Signals | null,
    ) => {
      if (finished) {
        return
      }

      finished = true
      clearTimeout(timer)

      resolveResult({
        exitCode,
        signal,
        timedOut,
        outputLimitExceeded,
        stdout: Buffer.concat(stdoutChunks).toString("utf8"),
        stderr: Buffer.concat(stderrChunks).toString("utf8"),
        durationMs: Date.now() - startedAt,
      })
    }

    const collect = (
      chunk: Buffer,
      destination: Buffer[],
      currentBytes: number,
    ): number => {
      const remaining =
        MAX_PROCESS_OUTPUT_BYTES - currentBytes

      if (remaining <= 0) {
        outputLimitExceeded = true
        child.kill("SIGKILL")
        return currentBytes
      }

      if (chunk.length <= remaining) {
        destination.push(chunk)
        return currentBytes + chunk.length
      }

      destination.push(chunk.subarray(0, remaining))
      outputLimitExceeded = true
      child.kill("SIGKILL")
      return MAX_PROCESS_OUTPUT_BYTES
    }

    child.stdout.on("data", (chunk: Buffer) => {
      stdoutBytes = collect(
        chunk,
        stdoutChunks,
        stdoutBytes,
      )
    })

    child.stderr.on("data", (chunk: Buffer) => {
      stderrBytes = collect(
        chunk,
        stderrChunks,
        stderrBytes,
      )
    })

    child.on("error", error => {
      clearTimeout(timer)
      reject(error)
    })

    child.on("close", (exitCode, signal) => {
      finish(exitCode, signal)
    })

    const timer = setTimeout(() => {
      timedOut = true
      child.kill("SIGKILL")
    }, timeoutSeconds * 1000)
  })
}

async function runLean(
  worktree: string,
  absolutePath: string,
  timeoutSeconds: number,
): Promise<ProcessResult> {
  // `lake env lean` configures the module search path but does not compile
  // project imports in a fresh worktree. Prepare the shared candidate import
  // first so agents receive diagnostics for their file, not a missing .olean.
  const baseBuild = await runLake(
    worktree,
    ["build", LEAN_CANDIDATE_BASE_TARGET],
    timeoutSeconds,
  )
  if (
    baseBuild.exitCode !== 0 ||
    baseBuild.timedOut ||
    baseBuild.outputLimitExceeded
  ) {
    return baseBuild
  }

  return await runLake(
    worktree,
    ["env", "lean", absolutePath],
    timeoutSeconds,
  )
}

function parseDiagnostics(
  stdout: string,
  stderr: string,
): Diagnostic[] {
  const diagnostics: Diagnostic[] = []
  const lines = `${stdout}\n${stderr}`.split(/\r?\n/)

  let current: Diagnostic | null = null

  const pattern =
    /^(.*?):(\d+):(\d+):\s+(error|warning|information):\s*(.*)$/

  for (const line of lines) {
    const match = line.match(pattern)

    if (match !== null) {
      current = {
        file: match[1],
        line: Number(match[2]),
        column: Number(match[3]),
        severity: match[4] as Diagnostic["severity"],
        message: match[5],
      }

      diagnostics.push(current)
      continue
    }

    if (current !== null && line.trim().length > 0) {
      current.message += `\n${line}`
    }
  }

  return diagnostics
}

function extractGoals(
  diagnostics: Diagnostic[],
  stdout: string,
  stderr: string,
): Array<{
  file: string | null
  line: number | null
  column: number | null
  text: string
}> {
  const goals = diagnostics
    .filter(diagnostic =>
      /unsolved goals|⊢|declaration has metavariables/i.test(
        diagnostic.message,
      ),
    )
    .map(diagnostic => ({
      file: diagnostic.file,
      line: diagnostic.line,
      column: diagnostic.column,
      text: diagnostic.message,
    }))

  if (goals.length > 0) {
    return goals
  }

  const combined = `${stdout}\n${stderr}`

  if (/unsolved goals|⊢/i.test(combined)) {
    return [{
      file: null,
      line: null,
      column: null,
      text: combined.trim(),
    }]
  }

  return []
}

async function executeLeanTool(
  worktree: string,
  path: string,
  timeoutSeconds: number,
) {
  const file = await resolveLeanFile(worktree, path)

  const processResult = await runLean(
    worktree,
    file.absolutePath,
    timeoutSeconds,
  )

  const diagnostics = parseDiagnostics(
    processResult.stdout,
    processResult.stderr,
  )

  return {
    file,
    processResult,
    diagnostics,
    goals: extractGoals(
      diagnostics,
      processResult.stdout,
      processResult.stderr,
    ),
  }
}

export const check_file = tool({
  description:
    "Check one whitelisted Lean file using `lake env lean`. " +
    "The command is executed without a shell and returns structured JSON.",

  args: {
    path: tool.schema
      .string()
      .min(1)
      .max(300)
      .describe(
        "Lean file under lean/, candidates/, or accepted/",
      ),

    timeoutSeconds: tool.schema
      .number()
      .int()
      .min(1)
      .max(30),
  },

  async execute(args, context) {
    try {
      const result = await executeLeanTool(
        context.worktree,
        args.path,
        args.timeoutSeconds,
      )

      const errorCount = result.diagnostics.filter(
        item => item.severity === "error",
      ).length

      const warningCount = result.diagnostics.filter(
        item => item.severity === "warning",
      ).length

      return jsonResult({
        ok: true,
        tool: "lean_check_file",
        version: TOOL_VERSION,
        file: {
          relativePath: result.file.relativePath,
          sha256: sha256(result.file.data),
          sizeBytes: result.file.data.length,
        },
        lean: {
          success:
            result.processResult.exitCode === 0 &&
            !result.processResult.timedOut &&
            !result.processResult.outputLimitExceeded,
          exitCode: result.processResult.exitCode,
          signal: result.processResult.signal,
          timedOut: result.processResult.timedOut,
          outputLimitExceeded:
            result.processResult.outputLimitExceeded,
          durationMs: result.processResult.durationMs,
          errorCount,
          warningCount,
        },
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "lean_check_file",
        version: TOOL_VERSION,
        error: {
          code: "LEAN_CHECK_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown Lean-check failure",
        },
      })
    }
  },
})

export const get_diagnostics = tool({
  description:
    "Run Lean on one whitelisted file and return parsed errors and warnings. " +
    "No shell is used.",

  args: {
    path: tool.schema.string().min(1).max(300),

    timeoutSeconds: tool.schema
      .number()
      .int()
      .min(1)
      .max(30),
  },

  async execute(args, context) {
    try {
      const result = await executeLeanTool(
        context.worktree,
        args.path,
        args.timeoutSeconds,
      )

      return jsonResult({
        ok: true,
        tool: "lean_get_diagnostics",
        version: TOOL_VERSION,
        file: {
          relativePath: result.file.relativePath,
          sha256: sha256(result.file.data),
        },
        lean: {
          success:
            result.processResult.exitCode === 0 &&
            !result.processResult.timedOut &&
            !result.processResult.outputLimitExceeded,
          exitCode: result.processResult.exitCode,
          timedOut: result.processResult.timedOut,
          durationMs: result.processResult.durationMs,
        },
        summary: {
          errors: result.diagnostics.filter(
            item => item.severity === "error",
          ).length,
          warnings: result.diagnostics.filter(
            item => item.severity === "warning",
          ).length,
          information: result.diagnostics.filter(
            item => item.severity === "information",
          ).length,
        },
        diagnostics: result.diagnostics,
        unparsedOutput:
          result.diagnostics.length === 0 &&
          result.processResult.exitCode !== 0
            ? {
                stdout: result.processResult.stdout,
                stderr: result.processResult.stderr,
              }
            : null,
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "lean_get_diagnostics",
        version: TOOL_VERSION,
        error: {
          code: "LEAN_DIAGNOSTICS_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown Lean-diagnostics failure",
        },
      })
    }
  },
})

export const get_goals = tool({
  description:
    "Run Lean on one whitelisted file and return unresolved proof-goal diagnostics. " +
    "No shell is used.",

  args: {
    path: tool.schema.string().min(1).max(300),

    timeoutSeconds: tool.schema
      .number()
      .int()
      .min(1)
      .max(30),
  },

  async execute(args, context) {
    try {
      const result = await executeLeanTool(
        context.worktree,
        args.path,
        args.timeoutSeconds,
      )

      return jsonResult({
        ok: true,
        tool: "lean_get_goals",
        version: TOOL_VERSION,
        file: {
          relativePath: result.file.relativePath,
          sha256: sha256(result.file.data),
        },
        lean: {
          exitCode: result.processResult.exitCode,
          timedOut: result.processResult.timedOut,
          durationMs: result.processResult.durationMs,
        },
        goalCount: result.goals.length,
        goals: result.goals,
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "lean_get_goals",
        version: TOOL_VERSION,
        error: {
          code: "LEAN_GOALS_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown Lean-goals failure",
        },
      })
    }
  },
})

export const run_eval = tool({
  description:
    "Run a whitelisted Lean file containing #eval or #reduce and return its bounded output. " +
    "No shell is used.",

  args: {
    path: tool.schema.string().min(1).max(300),

    timeoutSeconds: tool.schema
      .number()
      .int()
      .min(1)
      .max(30),
  },

  async execute(args, context) {
    try {
      const file = await resolveLeanFile(
        context.worktree,
        args.path,
      )

      const source = file.data.toString("utf8")

      if (!/#(?:eval|reduce)\b/.test(source)) {
        return jsonResult({
          ok: false,
          tool: "lean_run_eval",
          version: TOOL_VERSION,
          error: {
            code: "NO_EVAL_DIRECTIVE",
            message:
              "the Lean file must contain #eval or #reduce",
          },
        })
      }

      const result = await executeLeanTool(
        context.worktree,
        args.path,
        args.timeoutSeconds,
      )

      return jsonResult({
        ok: true,
        tool: "lean_run_eval",
        version: TOOL_VERSION,
        file: {
          relativePath: result.file.relativePath,
          sha256: sha256(result.file.data),
        },
        lean: {
          success:
            result.processResult.exitCode === 0 &&
            !result.processResult.timedOut &&
            !result.processResult.outputLimitExceeded,
          exitCode: result.processResult.exitCode,
          timedOut: result.processResult.timedOut,
          durationMs: result.processResult.durationMs,
        },
        evaluation: {
          stdout: result.processResult.stdout,
          stderr: result.processResult.stderr,
        },
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "lean_run_eval",
        version: TOOL_VERSION,
        error: {
          code: "LEAN_EVAL_FAILED",
          message:
            error instanceof Error
              ? error.message
              : "unknown Lean-evaluation failure",
        },
      })
    }
  },
})
