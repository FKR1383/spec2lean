import { tool } from "@opencode-ai/plugin"
import path from "path"

const unitKinds = [
  "ARCHITECTURE", "STATE_MODEL", "TYPE_SYSTEM", "EXECUTION_MODEL", "OPERAND_MODEL",
  "MEMORY_MODEL", "ABI", "INSTRUCTION_FAMILY", "INSTRUCTION", "DIRECTIVE",
  "SPECIAL_REGISTER", "OTHER",
] as const

const dependencyTypes = [
  "USES_STATE_MODEL", "USES_TYPE_SYSTEM", "USES_EXECUTION_MODEL", "USES_OPERAND_MODEL",
  "USES_MEMORY_MODEL", "USES_INSTRUCTION", "REQUIRES",
] as const

export default tool({
  description: "Validate and submit a complete Phase-2 candidate; invalid results return concise diagnostics for correction in this same session. INSTRUCTION units require non-empty instructionNames.",
  args: {
    units: tool.schema.array(tool.schema.object({
      unitId: tool.schema.string(),
      name: tool.schema.string(),
      kind: tool.schema.enum(unitKinds),
      sourceNodeIds: tool.schema.array(tool.schema.string()),
      instructionNames: tool.schema.array(tool.schema.string()).optional(),
    })),
    dependencies: tool.schema.array(tool.schema.object({
      fromUnitId: tool.schema.string(),
      toUnitId: tool.schema.string(),
      type: tool.schema.enum(dependencyTypes),
      reason: tool.schema.string(),
      sourceNodeIds: tool.schema.array(tool.schema.string()),
      origin: tool.schema.enum(["EXPLICIT", "INFERRED"]),
    })),
  },
  async execute(args, context) {
    const database = process.env.SPEC2LEAN_PLANNER_DATABASE
    const state = process.env.SPEC2LEAN_PLANNER_SESSION_STATE
    const target = process.env.SPEC2LEAN_PLANNER_SUBMISSION
    const language = process.env.SPEC2LEAN_PLANNER_LANGUAGE
    const version = process.env.SPEC2LEAN_PLANNER_VERSION
    const digest = process.env.SPEC2LEAN_PLANNER_INDEX_DIGEST
    if (!database || !state || !target || !language || !version || !digest) {
      throw new Error("planner submission environment is incomplete")
    }
    const executable = path.join(context.worktree, "spec2lean")
    const processResult = Bun.spawn([
      executable, "planner-tool", "submit", "--database", database,
      "--session-state", state, "--submission-output", target,
      "--language", language, "--specification-version", version,
      "--index-digest", digest, "--request", JSON.stringify(args),
    ], { cwd: context.worktree, stdout: "pipe", stderr: "pipe" })
    const stdout = await new Response(processResult.stdout).text()
    const stderr = await new Response(processResult.stderr).text()
    const exitCode = await processResult.exited
    if (exitCode !== 0) throw new Error(stderr.trim() || stdout.trim())
    return stdout.trim()
  },
})
