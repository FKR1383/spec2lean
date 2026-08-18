type UnknownRecord = Record<string, unknown>

export type TheoremDeclaration = {
  name: string
  declaration: string
  canonicalStatement: string
}

export type TheoremContract = {
  declarations: TheoremDeclaration[]
  issues: string[]
}

const LEAN_SURFACE_OPERATOR_ALIASES: ReadonlyArray<readonly [string, string]> = [
  ["<->", "↔"],
  ["->", "→"],
  ["\\/", "∨"],
  ["/\\", "∧"],
]

function escapeRegex(source: string): string {
  return source.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
}

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function stripLeanComments(source: string): string {
  let output = ""
  let index = 0
  let blockDepth = 0
  let inString = false
  let escaped = false

  while (index < source.length) {
    const current = source[index]
    const next = source[index + 1]

    if (blockDepth > 0) {
      if (current === "/" && next === "-") {
        blockDepth += 1
        index += 2
        continue
      }
      if (current === "-" && next === "/") {
        blockDepth -= 1
        index += 2
        continue
      }
      if (current === "\n") output += "\n"
      index += 1
      continue
    }

    if (inString) {
      output += current
      if (escaped) escaped = false
      else if (current === "\\") escaped = true
      else if (current === '"') inString = false
      index += 1
      continue
    }

    if (current === "/" && next === "-") {
      blockDepth = 1
      index += 2
      continue
    }
    if (current === "-" && next === "-") {
      while (index < source.length && source[index] !== "\n") index += 1
      continue
    }
    if (current === '"') inString = true
    output += current
    index += 1
  }

  return output
}

function proofAssignmentOffset(source: string): number | undefined {
  let blockDepth = 0
  let delimiterDepth = 0
  let inString = false
  let escaped = false
  for (let index = 0; index < source.length - 1; index += 1) {
    const current = source[index]
    const next = source[index + 1]
    if (blockDepth > 0) {
      if (current === "/" && next === "-") {
        blockDepth += 1
        index += 1
      } else if (current === "-" && next === "/") {
        blockDepth -= 1
        index += 1
      }
      continue
    }
    if (inString) {
      if (escaped) escaped = false
      else if (current === "\\") escaped = true
      else if (current === '"') inString = false
      continue
    }
    if (current === "/" && next === "-") {
      blockDepth = 1
      index += 1
      continue
    }
    if (current === "-" && next === "-") {
      while (index < source.length && source[index] !== "\n") index += 1
      continue
    }
    if (current === '"') {
      inString = true
      continue
    }
    if (current === "(" || current === "[" || current === "{") delimiterDepth += 1
    if (current === ")" || current === "]" || current === "}") delimiterDepth = Math.max(0, delimiterDepth - 1)
    if (delimiterDepth === 0 && current === ":" && next === "=") return index
  }
  return undefined
}

export function canonicalTheoremStatement(declaration: string): string {
  const withoutComments = stripLeanComments(declaration)
  const assignment = proofAssignmentOffset(withoutComments)
  const statement = assignment === undefined
    ? withoutComments
    : withoutComments.slice(0, assignment)
  return normalizeLeanStatementSurfaceSyntax(statement).replace(/\s+/g, " ").trim()
}

/**
 * Normalize only parser-equivalent Lean surface spellings. This deliberately
 * does not reorder binders, add/remove hypotheses, unfold definitions, or use
 * theorem proving. It prevents JSON escaping and ASCII/Unicode notation from
 * turning an unchanged theorem proposition into a false contract mismatch.
 */
export function normalizeLeanStatementSurfaceSyntax(source: string): string {
  let output = ""
  let index = 0
  let inString = false
  let escaped = false

  while (index < source.length) {
    const current = source[index]!
    if (inString) {
      output += current
      if (escaped) escaped = false
      else if (current === "\\") escaped = true
      else if (current === '"') inString = false
      index += 1
      continue
    }
    if (current === '"') {
      inString = true
      output += current
      index += 1
      continue
    }

    const unicodeEscape = source.slice(index).match(/^\\u([0-9a-fA-F]{4})/)
    if (unicodeEscape?.[1] !== undefined) {
      output += String.fromCharCode(Number.parseInt(unicodeEscape[1], 16))
      index += unicodeEscape[0].length
      continue
    }

    const alias = LEAN_SURFACE_OPERATOR_ALIASES.find(([spelling]) =>
      source.startsWith(spelling, index)
    )
    if (alias !== undefined) {
      output += alias[1]
      index += alias[0].length
      continue
    }

    output += current
    index += 1
  }
  return output
}

export function theoremContractEncodingIssues(input: unknown): string[] {
  const issues: string[] = []
  for (const [index, obligation] of obligationRecords(input).entries()) {
    const sketch = obligation.lean_statement_sketch
    if (typeof sketch === "string" && /\\u[0-9a-fA-F]{4}/.test(sketch)) {
      const id = typeof obligation.obligation_id === "string"
        ? obligation.obligation_id
        : `index ${index}`
      issues.push(
        `${id} contains a literal \\uXXXX escape; write valid Lean source notation ` +
        "(for example ∨ or \\/) rather than double-escaped Unicode",
      )
    }
  }
  return issues
}

export function theoremDeclarations(source: string): TheoremDeclaration[] {
  const matches = [...source.matchAll(/^[ \t]*theorem\s+([A-Za-z_][A-Za-z0-9_'.]*)\b/gm)]
  return matches.map((match, index) => {
    const start = match.index ?? 0
    const end = matches[index + 1]?.index ?? source.length
    const declaration = source.slice(start, end).trim()
    return {
      name: match[1]!,
      declaration,
      canonicalStatement: canonicalTheoremStatement(declaration),
    }
  })
}

function hasExplicitResultType(statement: string): boolean {
  let depth = 0
  let inString = false
  let escaped = false
  for (const character of statement) {
    if (inString) {
      if (escaped) escaped = false
      else if (character === "\\") escaped = true
      else if (character === '"') inString = false
      continue
    }
    if (character === '"') {
      inString = true
      continue
    }
    if (character === "(" || character === "[" || character === "{") depth += 1
    else if (character === ")" || character === "]" || character === "}") depth = Math.max(0, depth - 1)
    else if (character === ":" && depth === 0) return true
  }
  return false
}

function obligationRecords(input: unknown): UnknownRecord[] {
  if (!isRecord(input) || !Array.isArray(input.theorem_obligations)) return []
  return input.theorem_obligations.filter(isRecord)
}

export function validateTheoremObligationDocument(input: unknown): TheoremContract {
  const issues: string[] = []
  if (!isRecord(input)) return { declarations: [], issues: ["obligation artifact must be a JSON object"] }
  if (input.schema_version !== 1) issues.push("schema_version must be 1")
  if (!Array.isArray(input.theorem_obligations) || input.theorem_obligations.length === 0) {
    issues.push("theorem_obligations must be a non-empty array")
  }

  const declarations: TheoremDeclaration[] = []
  for (const [index, obligation] of obligationRecords(input).entries()) {
    const obligationId = typeof obligation.obligation_id === "string"
      ? obligation.obligation_id
      : `index ${index}`
    if (typeof obligation.obligation_id !== "string" || obligation.obligation_id.trim().length === 0) {
      issues.push(`theorem obligation ${index} has no obligation_id`)
    }
    const sketch = obligation.lean_statement_sketch
    if (typeof sketch !== "string" || sketch.trim().length === 0) {
      issues.push(`${obligationId} has no lean_statement_sketch`)
      continue
    }
    if (/\.\.\.|\?_\b|\bby\?\b|\b(?:sorry|admit|axiom|unsafe)\b/.test(stripLeanComments(sketch))) {
      issues.push(`${obligationId} contains placeholders or prohibited Lean tokens`)
    }
    const extracted = theoremDeclarations(sketch)
    if (extracted.length === 0) {
      issues.push(`${obligationId} contains no complete theorem declaration`)
      continue
    }
    declarations.push(...extracted)
  }

  const seen = new Set<string>()
  for (const declaration of declarations) {
    if (seen.has(declaration.name)) issues.push(`duplicate theorem declaration: ${declaration.name}`)
    seen.add(declaration.name)
    if (!hasExplicitResultType(declaration.canonicalStatement)) {
      issues.push(`theorem declaration has no explicit result type: ${declaration.name}`)
    }
  }
  return { declarations, issues: [...new Set(issues)] }
}

export function compareProofWithApprovedTheorems(
  approved: TheoremDeclaration[],
  proofSource: string,
): string[] {
  const actual = new Map(theoremDeclarations(proofSource).map((item) => [item.name, item]))
  const issues: string[] = []
  for (const expected of approved) {
    const declaration = actual.get(expected.name)
    if (declaration === undefined) {
      issues.push(`missing approved theorem declaration: ${expected.name}`)
    } else if (declaration.canonicalStatement !== expected.canonicalStatement) {
      issues.push(`approved theorem statement changed: ${expected.name}`)
    }
  }
  return issues
}

export function theoremStrengthReviewAuditIssues(
  review: string,
  obligationPath: string,
  declarations: Array<Pick<TheoremDeclaration, "name">>,
): string[] {
  const issues: string[] = []
  const pathPattern = new RegExp(
    `Validated obligation artifact:\\s*\u0060?${escapeRegex(obligationPath)}\u0060?`,
    "i",
  )
  if (!pathPattern.test(review)) {
    issues.push(`theorem-strength review must identify validated obligation artifact ${obligationPath}`)
  }

  const countMatch = review.match(
    /Complete declaration count reviewed:\s*\*{0,2}(\d+)\*{0,2}/i,
  )
  if (countMatch === null) {
    issues.push("theorem-strength review must state the complete declaration count reviewed")
  } else if (Number(countMatch[1]) !== declarations.length) {
    issues.push(
      `theorem-strength review counted ${countMatch[1]} declarations; ` +
      `the validated obligation contract contains ${declarations.length}`,
    )
  }

  for (const declaration of declarations) {
    const namePattern = new RegExp(`\\b${escapeRegex(declaration.name)}\\b`)
    if (!namePattern.test(review)) {
      issues.push(`theorem-strength review does not identify declaration ${declaration.name}`)
    }
  }
  return issues
}
