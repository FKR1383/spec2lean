import { tool } from "@opencode-ai/plugin"
import { createHash } from "node:crypto"
import { readFile, realpath, stat } from "node:fs/promises"
import { dirname, isAbsolute, relative, resolve, sep } from "node:path"

import {
  resolvePtxInstructionSection,
  type PtxIndexedSection,
} from "../../engine/orchestrator/src/ptx-section-resolver.ts"

const TOOL_VERSION = 1
const PROFILE_PATH =
  "language_packs/ptx/9.3/retrieval-profile.json"

type RetrievalProfile = {
  schemaVersion: number
  language: string
  specificationVersion: string
  sourceManifest: string
  index: {
    schemaVersion: number
    cachePath: string
  }
  context: {
    targetMaxLines: number
    sharedMaxLines: number
    architectureTargetMaxLines: number
    architectureSharedMaxLines: number
    sharedSections: Array<{
      anchor: string
      purpose: string
    }>
  }
  policy: {
    interpretationPerformed: boolean
    humanApprovalImplied: boolean
    description: string
  }
}

type SourceManifest = {
  specification_version?: string
  artifacts?: Array<{
    kind?: string
    local_path?: string
    sha256?: string
  }>
}

type Section = PtxIndexedSection

type Index = {
  schemaVersion: number
  specificationVersion: string
  source: {
    relativePath: string
    sha256: string
    totalLines: number
  }
  sections: Section[]
}

type Loaded = {
  profile: RetrievalProfile
  index: Index
  lines: string[]
}

let loadedPromise: Promise<Loaded> | undefined

function jsonResult(value: unknown): string {
  return JSON.stringify(value, null, 2)
}

function sha256(data: Buffer): string {
  return createHash("sha256").update(data).digest("hex")
}

function stripHtml(value: string): string {
  return value
    .replace(/<script\b[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[\s\S]*?<\/style>/gi, " ")
    .replace(/<[^>]+>/g, " ")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", "\"")
    .replaceAll("&#39;", "'")
    .replaceAll("&amp;", "&")
    .replaceAll("&nbsp;", " ")
    .replace(/\s+/g, " ")
    .trim()
}

function ensureInside(root: string, candidate: string): void {
  const relation = relative(root, candidate)

  if (
    relation === ".." ||
    relation.startsWith(`..${sep}`) ||
    isAbsolute(relation)
  ) {
    throw new Error("path escapes project root")
  }
}

async function load(worktree: string): Promise<Loaded> {
  if (loadedPromise) return loadedPromise

  loadedPromise = (async () => {
    const root = await realpath(worktree)

    const profilePath = resolve(root, PROFILE_PATH)
    ensureInside(root, profilePath)
    const profile = JSON.parse(
      await readFile(profilePath, "utf8"),
    ) as RetrievalProfile

    if (
      profile.schemaVersion !== 1 ||
      profile.language !== "PTX" ||
      profile.specificationVersion !== "9.3" ||
      profile.index.schemaVersion !== 1 ||
      !Number.isInteger(profile.context.targetMaxLines) ||
      profile.context.targetMaxLines <= 0 ||
      profile.context.targetMaxLines > 200 ||
      !Number.isInteger(profile.context.sharedMaxLines) ||
      profile.context.sharedMaxLines <= 0 ||
      profile.context.sharedMaxLines > 80 ||
      !Number.isInteger(profile.context.architectureTargetMaxLines) ||
      profile.context.architectureTargetMaxLines <= 0 ||
      profile.context.architectureTargetMaxLines > profile.context.targetMaxLines ||
      !Number.isInteger(profile.context.architectureSharedMaxLines) ||
      profile.context.architectureSharedMaxLines <= 0 ||
      profile.context.architectureSharedMaxLines > profile.context.sharedMaxLines ||
      profile.context.sharedSections.length === 0 ||
      profile.context.sharedSections.some(
        (section) =>
          typeof section.anchor !== "string" ||
          !/^[A-Za-z0-9._:-]+$/.test(section.anchor) ||
          typeof section.purpose !== "string" ||
          section.purpose.length === 0,
      ) ||
      new Set(
        profile.context.sharedSections.map((section) => section.anchor),
      ).size !== profile.context.sharedSections.length ||
      profile.policy.interpretationPerformed !== false ||
      profile.policy.humanApprovalImplied !== false
    ) {
      throw new Error("invalid PTX retrieval profile")
    }

    const indexPath = resolve(root, profile.index.cachePath)
    ensureInside(root, indexPath)

    const index = JSON.parse(
      await readFile(indexPath, "utf8"),
    ) as Index

    const manifestPath = resolve(root, profile.sourceManifest)
    ensureInside(root, manifestPath)
    const manifest = JSON.parse(
      await readFile(manifestPath, "utf8"),
    ) as SourceManifest
    const htmlArtifact = manifest.artifacts?.find(
      (artifact) => artifact.kind === "html",
    )

    if (
      manifest.specification_version !== profile.specificationVersion ||
      !htmlArtifact?.local_path ||
      !htmlArtifact.sha256
    ) {
      throw new Error("PTX retrieval profile source manifest is invalid")
    }

    const expectedSourcePath =
      `${dirname(profile.sourceManifest)}/${htmlArtifact.local_path}`

    if (
      index.schemaVersion !== profile.index.schemaVersion ||
      index.specificationVersion !== profile.specificationVersion ||
      index.source.relativePath !== expectedSourcePath ||
      index.source.sha256 !== htmlArtifact.sha256
    ) {
      throw new Error("cached PTX index does not match the retrieval profile and manifest")
    }

    const missingSharedAnchors = profile.context.sharedSections
      .map((section) => section.anchor)
      .filter((anchor) =>
        !index.sections.some((section) => section.anchor === anchor)
      )
    if (missingSharedAnchors.length > 0) {
      throw new Error(
        `cached PTX index lacks shared anchors: ${missingSharedAnchors.join(", ")}`,
      )
    }

    const sourcePath = resolve(root, index.source.relativePath)
    ensureInside(root, sourcePath)

    const metadata = await stat(sourcePath)

    if (!metadata.isFile()) {
      throw new Error("indexed PTX source is not a regular file")
    }

    const sourceData = await readFile(sourcePath)
    const actualSha256 = sha256(sourceData)

    if (actualSha256 !== index.source.sha256) {
      throw new Error(
        "PTX source changed after indexing; rebuild the source index",
      )
    }

    return {
      profile,
      index,
      lines: sourceData.toString("utf8").split(/\r?\n/),
    }
  })()

  return loadedPromise
}

function boundedContext(
  lines: string[],
  section: Section,
  maxLines: number,
) {
  const actualEnd =
    Math.min(section.endLine, section.startLine + maxLines - 1)

  const selected =
    lines.slice(section.startLine - 1, actualEnd)

  return {
    anchor: section.anchor,
    heading: section.heading,
    startLine: section.startLine,
    endLine: actualEnd,
    sectionEndLine: section.endLine,
    truncated: actualEnd < section.endLine,
    rawLineNumberedHtml: selected
      .map((line, index) => `${section.startLine + index}: ${line}`)
      .join("\n"),
    renderedText: stripHtml(selected.join("\n")),
  }
}

function compactArchitectureContext(
  lines: string[],
  section: Section,
  maxLines: number,
) {
  const actualEnd = Math.min(section.endLine, section.startLine + maxLines - 1)
  const selected = lines.slice(section.startLine - 1, actualEnd)
  const renderedLines = selected
    .map((line, index) => ({
      line: section.startLine + index,
      text: stripHtml(line),
    }))
    .filter((item) => item.text.length > 0)

  return {
    anchor: section.anchor,
    heading: section.heading,
    startLine: section.startLine,
    endLine: actualEnd,
    sectionEndLine: section.endLine,
    truncated: actualEnd < section.endLine,
    lineNumberedRenderedText: renderedLines
      .map((item) => `${item.line}: ${item.text}`)
      .join("\n"),
  }
}

export default tool({
  description:
    "Return a deterministic, hash-verified PTX 9.3 evidence context for one " +
    "instruction unit using the prebuilt local source index. This is the " +
    "preferred first retrieval tool for PTX source curation and critique.",

  args: {
    unit: tool.schema
      .string()
      .min(1)
      .max(120)
      .describe("PTX formalization unit, for example not.b32 or xor.b32"),
    purpose: tool.schema
      .enum(["evidence", "architecture"])
      .optional()
      .describe(
        "Use architecture for the compact architecture-stage view; " +
        "evidence is the default full citation view for curation and critique.",
      ),
  },

  async execute(args, context) {
    try {
      const loaded = await load(context.worktree)
      const purpose = args.purpose ?? "evidence"

      const mnemonic =
        args.unit.trim().toLowerCase().split(".")[0]

      if (!mnemonic || !/^[a-z][a-z0-9_]*$/.test(mnemonic)) {
        throw new Error(`cannot derive PTX mnemonic from unit: ${args.unit}`)
      }

      const resolution = resolvePtxInstructionSection(loaded.index.sections, args.unit)

      if (resolution.status === "NOT_FOUND") {
        return jsonResult({
          ok: false,
          tool: "spec_fast_context",
          version: TOOL_VERSION,
          error: {
            code: "INSTRUCTION_SECTION_NOT_FOUND",
            message:
              `No indexed PTX section ending in -${mnemonic} was found`,
          },
        })
      }

      if (resolution.status === "AMBIGUOUS") {
        return jsonResult({
          ok: false,
          tool: "spec_fast_context",
          version: TOOL_VERSION,
          error: {
            code: "AMBIGUOUS_INSTRUCTION_SECTION",
            candidates: resolution.candidates.slice(0, 8).map(({ section, score }) => ({
              anchor: section.anchor,
              startLine: section.startLine,
              endLine: section.endLine,
              heading: section.heading,
              score,
            })),
          },
        })
      }

      const shared = loaded.profile.context.sharedSections.flatMap((sharedSection) => {
        const section =
          loaded.index.sections.find(
            (item) => item.anchor === sharedSection.anchor,
          )

        return section
          ? [{
              ...(purpose === "architecture"
                ? compactArchitectureContext(
                    loaded.lines,
                    section,
                    loaded.profile.context.architectureSharedMaxLines,
                  )
                : boundedContext(
                    loaded.lines,
                    section,
                    loaded.profile.context.sharedMaxLines,
                  )),
              purpose: sharedSection.purpose,
            }]
          : []
      })

      return jsonResult({
        ok: true,
        tool: "spec_fast_context",
        version: TOOL_VERSION,
        languagePack: {
          retrievalProfile: PROFILE_PATH,
          schemaVersion: loaded.profile.schemaVersion,
          specificationVersion: loaded.profile.specificationVersion,
        },
        source: loaded.index.source,
        unit: args.unit,
        mnemonic,
        purpose,
        target: purpose === "architecture"
          ? compactArchitectureContext(
              loaded.lines,
              resolution.section,
              loaded.profile.context.architectureTargetMaxLines,
            )
          : boundedContext(
              loaded.lines,
              resolution.section,
              loaded.profile.context.targetMaxLines,
            ),
        shared,
        policy: {
          interpretationPerformed: false,
          humanApprovalImplied: false,
          sourceModified: false,
          sourceHashVerified: true,
        },
      })
    } catch (error) {
      return jsonResult({
        ok: false,
        tool: "spec_fast_context",
        version: TOOL_VERSION,
        error: {
          code: "FAST_CONTEXT_FAILED",
          message:
            error instanceof Error ? error.message : String(error),
        },
      })
    }
  },
})
