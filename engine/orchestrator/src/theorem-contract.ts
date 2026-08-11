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
  return statement.replace(/\s+/g, " ").trim()
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
