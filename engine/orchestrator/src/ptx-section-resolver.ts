export type PtxIndexedSection = {
  anchor: string
  startLine: number
  endLine: number
  heading: string
  searchText?: string
}

export type PtxSectionResolution =
  | { status: "FOUND"; section: PtxIndexedSection; score: number }
  | { status: "NOT_FOUND" }
  | { status: "AMBIGUOUS"; candidates: Array<{ section: PtxIndexedSection; score: number }> }

function mnemonicForUnit(unit: string): string | undefined {
  const mnemonic = unit.trim().toLowerCase().split(".")[0]
  return mnemonic !== undefined && /^[a-z][a-z0-9_]*$/.test(mnemonic)
    ? mnemonic
    : undefined
}

function unitQualifiers(unit: string): string[] {
  return unit.trim().toLowerCase().split(".").slice(1).filter(Boolean)
}

function baseScore(section: PtxIndexedSection, mnemonic: string): number {
  const anchor = section.anchor.toLowerCase()
  const heading = section.heading.toLowerCase()
  let score = 0
  if (anchor.endsWith(`-${mnemonic}`)) score += 100
  if (anchor.includes(`instructions-${mnemonic}`)) score += 50
  if (heading.includes(`instructions: ${mnemonic}`)) score += 40
  if (heading.includes(` ${mnemonic} `)) score += 10
  return score
}

function qualifierScore(section: PtxIndexedSection, qualifiers: readonly string[]): number {
  const haystack = `${section.anchor} ${section.heading} ${section.searchText ?? ""}`.toLowerCase()
  return qualifiers.reduce((score, qualifier) => {
    const escaped = qualifier.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    return score + (new RegExp(`(?:^|[^a-z0-9_])\\.${escaped}(?:[^a-z0-9_]|$)`).test(haystack) ? 12 : 0)
  }, 0)
}

function familyScore(section: PtxIndexedSection, qualifiers: readonly string[]): number {
  const anchor = section.anchor.toLowerCase()
  const typeQualifiers = qualifiers.filter((item) =>
    /^(?:(?:s|u|b|f|bf)\d+(?:x\d+)?)$/.test(item)
  )
  const primaryType = typeQualifiers[0]
  const integerTyped = primaryType !== undefined && /^(?:s|u|b)\d+(?:x\d+)?$/.test(primaryType)
  const floatTyped = primaryType !== undefined && /^(?:f|bf)\d+(?:x\d+)?$/.test(primaryType)
  const halfTyped = primaryType !== undefined && /^(?:f16|f16x2|bf16|bf16x2)$/.test(primaryType)
  const mixedTyped = primaryType === "f32" &&
    typeQualifiers.slice(1).some((item) => /^(?:f16|bf16)$/.test(item))

  if (anchor.includes("mixed-precision")) return mixedTyped ? 160 : -100

  if (halfTyped) {
    if (anchor.includes("half-precision")) return 120
    if (anchor.includes("floating-point")) return 40
    if (anchor.includes("integer-")) return -80
  }
  if (floatTyped) {
    if (anchor.includes("floating-point")) return 100
    if (anchor.includes("integer-")) return -80
  }
  if (integerTyped) {
    if (anchor.includes("integer-") || anchor.includes("logic-and-shift")) return 100
    if (anchor.includes("floating-point") || anchor.includes("half-precision")) return -80
  }
  return 0
}

export function resolvePtxInstructionSection(
  sections: readonly PtxIndexedSection[],
  unit: string,
): PtxSectionResolution {
  const mnemonic = mnemonicForUnit(unit)
  if (mnemonic === undefined) return { status: "NOT_FOUND" }
  const qualifiers = unitQualifiers(unit)
  const candidates = sections
    .filter((section) => section.anchor.toLowerCase().endsWith(`-${mnemonic}`))
    .map((section) => ({
      section,
      score:
        baseScore(section, mnemonic) +
        familyScore(section, qualifiers) +
        qualifierScore(section, qualifiers),
    }))
    .sort((left, right) =>
      right.score - left.score ||
      (left.section.endLine - left.section.startLine) -
        (right.section.endLine - right.section.startLine) ||
      left.section.anchor.localeCompare(right.section.anchor)
    )

  if (candidates.length === 0) return { status: "NOT_FOUND" }
  const bestScore = candidates[0]!.score
  const tied = candidates.filter((candidate) => candidate.score === bestScore)
  return tied.length === 1
    ? { status: "FOUND", section: tied[0]!.section, score: bestScore }
    : { status: "AMBIGUOUS", candidates: tied }
}
