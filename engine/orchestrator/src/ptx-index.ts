import { createHash } from "node:crypto"
import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
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

type Manifest = {
  artifacts?: Array<{
    kind?: string
    local_path?: string
    sha256?: string
  }>
}

type RetrievalProfile = {
  schemaVersion: number
  language: string
  specificationVersion: string
  sourceManifest: string
  index: {
    schemaVersion: number
    cachePath: string
  }
}

type OpenSection = {
  anchor?: string
  startLine: number
}

const version = required("--version")

const profileRelative =
  `language_packs/ptx/${version}/retrieval-profile.json`

const profile = JSON.parse(
  await readFile(resolve(REPO_ROOT, profileRelative), "utf8"),
) as RetrievalProfile

if (
  profile.schemaVersion !== 1 ||
  profile.language !== "PTX" ||
  profile.specificationVersion !== version ||
  profile.index.schemaVersion !== 1
) {
  throw new Error(`Invalid PTX retrieval profile: ${profileRelative}`)
}

const manifestRelative = profile.sourceManifest

const manifest = JSON.parse(
  await readFile(resolve(REPO_ROOT, manifestRelative), "utf8"),
) as Manifest

const htmlArtifact = manifest.artifacts?.find(
  (artifact) => artifact.kind === "html",
)

if (!htmlArtifact?.local_path || !htmlArtifact.sha256) {
  throw new Error("PTX manifest does not contain a hashed HTML artifact")
}

const sourceRelative =
  `documents/sources/nvidia/ptx/${version}/${htmlArtifact.local_path}`

const data = await readFile(resolve(REPO_ROOT, sourceRelative))
const actualSha256 = sha256(data)

if (actualSha256 !== htmlArtifact.sha256) {
  throw new Error(
    `PTX HTML hash mismatch: manifest=${htmlArtifact.sha256} actual=${actualSha256}`,
  )
}

const text = data.toString("utf8")
const lines = text.split(/\r?\n/)

const stack: OpenSection[] = []
const sections: Array<{
  anchor: string
  startLine: number
  endLine: number
  heading: string
}> = []

for (let lineIndex = 0; lineIndex < lines.length; lineIndex += 1) {
  const line = lines[lineIndex]!
  const lineNumber = lineIndex + 1

  const tokens = [...line.matchAll(/<\/?section\b[^>]*>/gi)]

  for (const match of tokens) {
    const token = match[0]!

    if (/^<\/section/i.test(token)) {
      const opened = stack.pop()

      if (opened?.anchor) {
        const preview = lines
          .slice(opened.startLine - 1, Math.min(lineNumber, opened.startLine + 12))
          .join("\n")

        sections.push({
          anchor: opened.anchor,
          startLine: opened.startLine,
          endLine: lineNumber,
          heading: stripHtml(preview).slice(0, 500),
        })
      }

      continue
    }

    const id =
      token.match(/\bid\s*=\s*"([^"]+)"/i)?.[1] ??
      token.match(/\bid\s*=\s*'([^']+)'/i)?.[1]

    stack.push({
      anchor: id,
      startLine: lineNumber,
    })
  }
}

sections.sort((a, b) => a.startLine - b.startLine)

const outputRelative = profile.index.cachePath

const outputPath = resolve(REPO_ROOT, outputRelative)

await mkdir(dirname(outputPath), { recursive: true })

await writeFile(
  outputPath,
  JSON.stringify({
    schemaVersion: profile.index.schemaVersion,
    language: "PTX",
    specificationVersion: version,
    languagePackProfile: profileRelative,
    source: {
      relativePath: sourceRelative,
      sha256: actualSha256,
      totalLines: lines.length,
    },
    sections,
  }, null, 2) + "\n",
)

console.log(JSON.stringify({
  ok: true,
  version,
  sourceSha256: actualSha256,
  sections: sections.length,
  outputPath: outputRelative,
}, null, 2))
