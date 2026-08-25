import { tool } from "@opencode-ai/plugin"
import path from "path"

async function invoke(name: string, args: unknown, context: { worktree: string }) {
  const database = process.env.SPEC2LEAN_PLANNER_DATABASE
  const state = process.env.SPEC2LEAN_PLANNER_SESSION_STATE
  if (!database || !state) throw new Error("Planner database/session environment is not set")
  const executable = path.join(context.worktree, "spec2lean")
  const processResult = Bun.spawn(
    [
      executable, "planner-tool", name, "--database", database,
      "--session-state", state, "--request", JSON.stringify(args),
    ],
    { cwd: context.worktree, stdout: "pipe", stderr: "pipe" },
  )
  const stdout = await new Response(processResult.stdout).text()
  const stderr = await new Response(processResult.stderr).text()
  const exitCode = await processResult.exited
  if (exitCode !== 0) throw new Error(stderr.trim() || stdout.trim())
  return stdout.trim()
}

const paging = {
  offset: tool.schema.number().optional().describe("Zero-based result offset"),
  limit: tool.schema.number().optional().describe("Bounded page size"),
}

export const tree = tool({
  description: "List a bounded hierarchical slice of Phase-1 nodes; defaults to the HTML heading tree",
  args: {
    rootNodeId: tool.schema.string().optional(),
    sourceType: tool.schema.enum(["html", "pdf"]).optional(),
    maxDepth: tool.schema.number().optional(),
    headingsOnly: tool.schema.boolean().optional(),
    ...paging,
  },
  async execute(args, context) { return invoke("tree", args, context) },
})

export const search = tool({
  description: "Full-text search a bounded page of Phase-1 nodes",
  args: {
    query: tool.schema.string(),
    sourceType: tool.schema.enum(["html", "pdf"]).optional(),
    nodeType: tool.schema.string().optional(),
    ...paging,
  },
  async execute(args, context) { return invoke("search", args, context) },
})

export const show = tool({
  description: "Show one Phase-1 node with bounded exact text, definitions, metadata, and outgoing cross-references",
  args: { nodeId: tool.schema.string(), textChars: tool.schema.number().optional() },
  async execute(args, context) { return invoke("show", args, context) },
})

export const children = tool({
  description: "List a bounded page of direct children of one Phase-1 node",
  args: { nodeId: tool.schema.string(), headingsOnly: tool.schema.boolean().optional(), ...paging },
  async execute(args, context) { return invoke("children", args, context) },
})

export const ancestors = tool({
  description: "List a Phase-1 node's ancestry from document root through the node",
  args: { nodeId: tool.schema.string() },
  async execute(args, context) { return invoke("ancestors", args, context) },
})

export const subtree = tool({
  description: "List a bounded hierarchical subtree rooted at one Phase-1 node",
  args: {
    nodeId: tool.schema.string(),
    maxDepth: tool.schema.number().optional(),
    headingsOnly: tool.schema.boolean().optional(),
    ...paging,
  },
  async execute(args, context) { return invoke("subtree", args, context) },
})

export const definitions = tool({
  description: "List structurally indexed Phase-1 definitions",
  args: {
    query: tool.schema.string().optional(),
    sourceType: tool.schema.enum(["html", "pdf"]).optional(),
    ...paging,
  },
  async execute(args, context) { return invoke("definitions", args, context) },
})

export const xrefs = tool({
  description: "Inspect bounded indexed cross-references, optionally connected to a node",
  args: {
    nodeId: tool.schema.string().optional(),
    status: tool.schema.enum(["RESOLVED", "AMBIGUOUS", "UNRESOLVED"]).optional(),
    direction: tool.schema.enum(["source", "target", "either"]).optional(),
    ...paging,
  },
  async execute(args, context) { return invoke("xrefs", args, context) },
})
