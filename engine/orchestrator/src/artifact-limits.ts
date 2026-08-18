import type { FormalizationStage } from "./workflow.js"

export const MAX_CANDIDATE_WRITE_BYTES = 128 * 1024
export const MAX_ARCHITECTURE_BYTES = 32 * 1024
export const MAX_ARCHITECTURE_LINES = 400

function lineCount(source: string): number {
  return source.length === 0 ? 0 : source.split(/\r?\n/).length
}

export function artifactBudgetIssues(
  stage: FormalizationStage,
  source: string,
): string[] {
  if (stage !== "ARCHITECTURE") return []

  const issues: string[] = []
  const bytes = Buffer.byteLength(source, "utf8")
  const lines = lineCount(source)

  if (bytes > MAX_ARCHITECTURE_BYTES) {
    issues.push(
      `architecture artifact exceeds the ${MAX_ARCHITECTURE_BYTES}-byte budget (${bytes} bytes)`,
    )
  }
  if (lines > MAX_ARCHITECTURE_LINES) {
    issues.push(
      `architecture artifact exceeds the ${MAX_ARCHITECTURE_LINES}-line budget (${lines} lines)`,
    )
  }

  return issues
}

export function candidatePathBudgetIssues(path: string, source: string): string[] {
  return /(^|\/)architecture\/foundation-v\d+\.md$/.test(path)
    ? artifactBudgetIssues("ARCHITECTURE", source)
    : []
}
