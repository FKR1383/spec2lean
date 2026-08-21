export type MachineBlockStatus =
  | "ABSENT"
  | "MALFORMED_FRAMING"
  | "JSON_PARSE_ERROR"
  | "JSON_NOT_OBJECT"
  | "OK"

export type MachineBlockResult = {
  status: MachineBlockStatus
  value?: Record<string, unknown>
  issue?: string
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

/** Parse one JSON machine block while accepting harmless closing-delimiter layout. */
export function parseMachineJsonBlock(source: string, name: string): MachineBlockResult {
  const escaped = escapeRegExp(name)
  const htmlOpen = new RegExp(`<!--[ \\t]*${escaped}[ \\t]*\\r?\\n`, "gi")
  const leanOpen = new RegExp(`/\\-[ \\t]*${escaped}[ \\t]*\\r?\\n`, "gi")
  const htmlMatches = [...source.matchAll(htmlOpen)]
  const leanMatches = [...source.matchAll(leanOpen)]
  const matches = [
    ...htmlMatches.map((match) => ({ match, close: "-->" })),
    ...leanMatches.map((match) => ({ match, close: "-/" })),
  ].sort((left, right) => (left.match.index ?? 0) - (right.match.index ?? 0))

  if (matches.length === 0) {
    return source.includes(name)
      ? {
          status: "MALFORMED_FRAMING",
          issue: `${name} marker is present but malformed; expected '<!-- ${name}\\n<JSON>\\n-->'`,
        }
      : { status: "ABSENT", issue: `${name} marker/block is absent` }
  }
  if (matches.length !== 1) {
    return {
      status: "MALFORMED_FRAMING",
      issue: `${name} must occur in exactly one machine block; found ${matches.length}`,
    }
  }

  const selected = matches[0]!
  const start = (selected.match.index ?? 0) + selected.match[0].length
  const end = source.indexOf(selected.close, start)
  if (end < 0) {
    return {
      status: "MALFORMED_FRAMING",
      issue: `${name} opening marker has no closing ${selected.close} delimiter`,
    }
  }
  const body = source.slice(start, end).trim()
  if (body.length === 0) {
    return { status: "JSON_PARSE_ERROR", issue: `${name} JSON body is empty` }
  }
  try {
    const value = JSON.parse(body) as unknown
    return isRecord(value)
      ? { status: "OK", value }
      : { status: "JSON_NOT_OBJECT", issue: `${name} parsed JSON must be an object` }
  } catch (error) {
    return {
      status: "JSON_PARSE_ERROR",
      issue: `${name} JSON parse failed: ${error instanceof Error ? error.message : String(error)}`,
    }
  }
}

export function canonicalMachineJsonBlock(name: string, value: Record<string, unknown>): string {
  return `<!-- ${name}\n${JSON.stringify(value)}\n-->`
}

/** The architecture tool owns machine-block serialization; prose must not. */
export function architectureWithCanonicalMachineBlocks(
  markdown: string,
  architectureIndex: Record<string, unknown>,
  completenessContract: Record<string, unknown>,
): string {
  for (const marker of ["SPEC2LEAN_ARCHITECTURE_INDEX", "SPEC2LEAN_COMPLETENESS_CONTRACT"]) {
    if (markdown.includes(marker)) {
      throw new Error(`architecture prose must omit ${marker}; pass its structured value to candidate_architecture_write`)
    }
  }
  return [
    markdown.trimEnd(),
    "",
    canonicalMachineJsonBlock("SPEC2LEAN_ARCHITECTURE_INDEX", architectureIndex),
    canonicalMachineJsonBlock("SPEC2LEAN_COMPLETENESS_CONTRACT", completenessContract),
    "",
  ].join("\n")
}
