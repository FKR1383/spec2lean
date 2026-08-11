import { createHash } from "node:crypto"
import { access, mkdir, readFile, readdir, writeFile } from "node:fs/promises"
import { dirname, resolve } from "node:path"

import { parseAgentResult } from "./agent-result.js"
import { sendPromptAsync, waitForAgentResult } from "./async-session.js"
import { startOpenCode, unwrap } from "./opencode.js"
import { loadAgentModel, REPO_ROOT } from "./repo.js"
import { verifySourceManifest } from "./source-manifest.js"

type Agent = { name: string }
type Session = { id: string }

export type AcquisitionProfile = {
  schemaVersion: 1
  language: string
  specificationVersion: string
  publisher: string
  documentTitle: string
  allowedUrlPrefixes: string[]
  requiredKinds: Array<"html" | "pdf">
  maxArtifacts: number
}

export type SourceProposal = {
  schema_version: 1
  language: string
  specification_version: string
  publisher: string
  document_title: string
  sources: Array<{
    kind: "html" | "pdf"
    url: string
    authority_reason: string
  }>
}

function safeSegment(value: string, label: string): string {
  const normalized = value.trim().toLowerCase()
  if (!/^[a-z][a-z0-9_-]*$/.test(normalized)) throw new Error(`unsafe ${label}: ${value}`)
  return normalized
}

function safeVersion(value: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(value)) throw new Error(`unsafe specification version: ${value}`)
  return value
}

function sha256(data: Uint8Array): string {
  return createHash("sha256").update(data).digest("hex")
}

function profilePath(language: string, version: string): string {
  return `language_packs/${language}/${version}/acquisition-profile.json`
}

export function conventionalSourceManifestPath(language: string, version: string): string {
  return `documents/sources/${safeSegment(language, "language")}/${safeVersion(version)}/source-manifest.json`
}

async function readProfile(language: string, version: string): Promise<AcquisitionProfile> {
  const path = profilePath(language, version)
  let profile: AcquisitionProfile
  try {
    profile = JSON.parse(await readFile(resolve(REPO_ROOT, path), "utf8")) as AcquisitionProfile
  } catch {
    throw new Error(
      `No source manifest was supplied and no acquisition profile exists at ${path}`,
    )
  }
  if (
    profile.schemaVersion !== 1 ||
    profile.language.toLowerCase() !== language ||
    profile.specificationVersion !== version ||
    profile.publisher.trim().length === 0 ||
    profile.documentTitle.trim().length === 0 ||
    !Array.isArray(profile.allowedUrlPrefixes) ||
    profile.allowedUrlPrefixes.length === 0 ||
    profile.allowedUrlPrefixes.some((prefix) => {
      try {
        return new URL(prefix).protocol !== "https:"
      } catch {
        return true
      }
    }) ||
    !Array.isArray(profile.requiredKinds) ||
    profile.requiredKinds.length === 0 ||
    !Number.isInteger(profile.maxArtifacts) ||
    profile.maxArtifacts < profile.requiredKinds.length ||
    profile.maxArtifacts > 4
  ) throw new Error(`Invalid acquisition profile: ${path}`)
  return profile
}

function proposalPath(language: string, version: string, revision: number): string {
  return `candidates/source-discovery/${language}/${version}/source-proposal-v${revision}.json`
}

export function validateSourceProposal(
  proposal: SourceProposal,
  profile: AcquisitionProfile,
): void {
  if (
    proposal.schema_version !== 1 ||
    proposal.language.toLowerCase() !== profile.language.toLowerCase() ||
    proposal.specification_version !== profile.specificationVersion ||
    proposal.publisher !== profile.publisher ||
    proposal.document_title !== profile.documentTitle ||
    !Array.isArray(proposal.sources) ||
    proposal.sources.length === 0 ||
    proposal.sources.length > profile.maxArtifacts
  ) throw new Error("OpenCode source proposal does not match the acquisition profile")

  const kinds = new Set<string>()
  for (const source of proposal.sources) {
    if (
      !["html", "pdf"].includes(source.kind) ||
      kinds.has(source.kind) ||
      typeof source.authority_reason !== "string" ||
      source.authority_reason.trim().length < 12
    ) throw new Error("OpenCode source proposal contains an invalid or duplicate artifact")
    kinds.add(source.kind)
    let url: URL
    try {
      url = new URL(source.url)
    } catch {
      throw new Error(`OpenCode proposed an invalid source URL: ${source.url}`)
    }
    if (
      url.protocol !== "https:" ||
      url.username.length > 0 ||
      url.password.length > 0 ||
      !profile.allowedUrlPrefixes.some((prefix) => source.url.startsWith(prefix))
    ) throw new Error(`OpenCode proposed a source outside the approved official URL scope: ${source.url}`)
  }
  for (const kind of profile.requiredKinds) {
    if (!kinds.has(kind)) throw new Error(`OpenCode source proposal is missing required ${kind} evidence`)
  }
}

async function discoverProposal(
  language: string,
  version: string,
  unit: string,
  profile: AcquisitionProfile,
  outputPath: string,
  priorDiagnostic?: string,
): Promise<{ sessionId: string; model: string }> {
  const runtime = await startOpenCode()
  const model = await loadAgentModel("source-acquirer")
  try {
    const agents = unwrap<Agent[]>(await runtime.runtime.client.app.agents())
    if (!agents.some((agent) => agent.name === "source-acquirer")) {
      throw new Error("Required OpenCode agent not found: source-acquirer")
    }
    const session = unwrap<Session>(await runtime.runtime.client.session.create({
      body: { title: `Spec2Lean source discovery: ${language} ${version}` },
    }))
    if (!session.id) throw new Error("OpenCode did not return a source-discovery session ID")
    const prompt = [
      "# Spec2Lean Official Source Discovery",
      "",
      `Language: ${language}`,
      `Specification version: ${version}`,
      `Initial bounded unit: ${unit}`,
      `Required publisher spelling: ${profile.publisher}`,
      `Required document title spelling: ${profile.documentTitle}`,
      `Allowed official URL prefixes: ${profile.allowedUrlPrefixes.join(", ")}`,
      `Required artifact kinds: ${profile.requiredKinds.join(", ")}`,
      `Maximum artifacts: ${profile.maxArtifacts}`,
      `Create exactly: ${outputPath}`,
      ...(priorDiagnostic === undefined
        ? []
        : [
            "",
            "The previous immutable proposal was rejected by deterministic validation:",
            priorDiagnostic,
            "Correct exactly that problem in this new proposal revision.",
          ]),
      "",
      "Use web search and web fetch to independently locate the official, version-matched specification.",
      "Do not use mirrors, tutorials, search-result URLs, GitHub forks, or model memory as source authority.",
      "Write the proposal with candidate_write using exactly this JSON shape:",
      JSON.stringify({
        schema_version: 1,
        language,
        specification_version: version,
        publisher: profile.publisher,
        document_title: profile.documentTitle,
        sources: [{ kind: profile.requiredKinds[0], url: "https://official.example/spec", authority_reason: "Concrete reason this is the publisher's official versioned source." }],
      }, null, 2),
      "The URL must be a direct downloadable HTML document/page or PDF, not an index or search page.",
      "Do not interpret the requested unit and do not write any semantic or Lean artifact.",
      "After writing, read the exact proposal back and verify every field.",
      "",
      "Your last non-empty line must be exactly:",
      'SPEC2LEAN_RESULT {"outcome":"SUCCESS","nextStage":"CREATED","summary":"official source proposal written"}',
    ].join("\n")
    await sendPromptAsync(runtime.runtime.server.url, session.id, {
      agent: "source-acquirer",
      model: { providerID: model.providerID, modelID: model.modelID },
      parts: [{ type: "text", text: prompt }],
    })
    const response = await waitForAgentResult(runtime.runtime.server.url, session.id, {
      maxWaitMs: 4 * 60 * 1000,
    })
    const result = parseAgentResult(response)
    if (result.outcome !== "SUCCESS" || result.nextStage !== "CREATED") {
      throw new Error(`OpenCode source discovery did not succeed: ${result.summary}`)
    }
    return { sessionId: session.id, model: model.full }
  } finally {
    runtime.runtime.server.close()
  }
}

async function download(url: string, allowedPrefixes: string[]): Promise<Buffer> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 120_000)
  try {
    const response = await fetch(url, {
      redirect: "follow",
      signal: controller.signal,
      headers: { "user-agent": "Spec2Lean/0.1 official-source acquisition" },
    })
    if (!response.ok) throw new Error(`Official source download failed: HTTP ${response.status}`)
    if (!allowedPrefixes.some((prefix) => response.url.startsWith(prefix))) {
      throw new Error(`Official source redirected outside the approved URL scope: ${response.url}`)
    }
    const declaredLength = Number(response.headers.get("content-length") ?? "0")
    if (declaredLength > 50 * 1024 * 1024) throw new Error("Official source exceeds the 50 MiB acquisition limit")
    const data = Buffer.from(await response.arrayBuffer())
    if (data.length === 0 || data.length > 50 * 1024 * 1024) {
      throw new Error("Official source is empty or exceeds the 50 MiB acquisition limit")
    }
    return data
  } finally {
    clearTimeout(timer)
  }
}

async function acquire(
  proposal: SourceProposal,
  profile: AcquisitionProfile,
  manifestRelative: string,
  unit: string,
  selectedProposalPath: string,
): Promise<void> {
  const manifestAbsolute = resolve(REPO_ROOT, manifestRelative)
  const root = dirname(manifestAbsolute)
  await mkdir(resolve(root, "raw"), { recursive: true })
  const artifacts = []
  for (const source of proposal.sources) {
    const data = await download(source.url, profile.allowedUrlPrefixes)
    const localPath = `raw/specification.${source.kind}`
    const absolute = resolve(root, localPath)
    const existing = await readFile(absolute).catch(() => undefined)
    if (existing !== undefined && !existing.equals(data)) {
      throw new Error(`Refusing to overwrite a different previously acquired source: ${localPath}`)
    }
    if (existing === undefined) await writeFile(absolute, data, { flag: "wx" })
    artifacts.push({
      kind: source.kind,
      url: source.url,
      local_path: localPath,
      sha256: sha256(data),
      size_bytes: data.length,
    })
  }
  const manifest = {
    schema_version: 1,
    publisher: proposal.publisher,
    document_title: proposal.document_title,
    language: proposal.language,
    specification_version: proposal.specification_version,
    source_classification: "official",
    retrieved_at_utc: new Date().toISOString(),
    acquisition: {
      method: "opencode_discovery_with_deterministic_fetch",
      proposal_path: selectedProposalPath,
      allowed_url_prefixes: profile.allowedUrlPrefixes,
    },
    initial_formalization_unit: { construct: unit },
    artifacts,
    semantic_status: "not_started",
    notes: [
      "OpenCode selected the source from the configured official publisher scope.",
      "The orchestrator downloaded and hash-pinned the selected artifacts.",
      "No semantic interpretation was produced during acquisition.",
    ],
  }
  await writeFile(manifestAbsolute, `${JSON.stringify(manifest, null, 2)}\n`, { flag: "wx" })
  await verifySourceManifest(manifestAbsolute)
}

export async function ensureDiscoveredSourceManifest(input: {
  language: string
  specificationVersion: string
  unit: string
}): Promise<{
  path: string
  acquisition: {
    status: "CACHE_HIT" | "DISCOVERED"
    startedAtUtc: string
    finishedAtUtc: string
    proposalPath?: string
    agent?: string
    model?: string
    sessionId?: string
  }
}> {
  const startedAtUtc = new Date().toISOString()
  const language = safeSegment(input.language, "language")
  const version = safeVersion(input.specificationVersion)
  const manifest = conventionalSourceManifestPath(language, version)
  const manifestExists = await access(resolve(REPO_ROOT, manifest)).then(() => true, () => false)
  if (manifestExists) {
    await verifySourceManifest(resolve(REPO_ROOT, manifest))
    return {
      path: manifest,
      acquisition: {
        status: "CACHE_HIT",
        startedAtUtc,
        finishedAtUtc: new Date().toISOString(),
      },
    }
  }
  const profile = await readProfile(language, version)
  const proposalDirectory = `candidates/source-discovery/${language}/${version}`
  const existingNames = await readdir(resolve(REPO_ROOT, proposalDirectory)).catch(() => [])
  const existing = existingNames.flatMap((name) => {
    const match = name.match(/^source-proposal-v(\d+)\.json$/)
    return match === null ? [] : [{ revision: Number(match[1]), path: `${proposalDirectory}/${name}` }]
  }).sort((left, right) => right.revision - left.revision)
  let nextRevision = (existing[0]?.revision ?? 0) + 1
  let selectedProposalPath: string | undefined
  let proposal: SourceProposal | undefined
  let diagnostic: string | undefined
  let session: { sessionId: string; model: string } | undefined
  if (existing[0] !== undefined) {
    try {
      const candidate = JSON.parse(
        await readFile(resolve(REPO_ROOT, existing[0].path), "utf8"),
      ) as SourceProposal
      validateSourceProposal(candidate, profile)
      proposal = candidate
      selectedProposalPath = existing[0].path
    } catch (error) {
      diagnostic = error instanceof Error ? error.message : String(error)
    }
  }
  for (let attempt = 0; proposal === undefined && attempt < 2; attempt += 1) {
    const currentPath = proposalPath(language, version, nextRevision)
    try {
      session = await discoverProposal(
        language,
        version,
        input.unit,
        profile,
        currentPath,
        diagnostic,
      )
      const candidate = JSON.parse(await readFile(resolve(REPO_ROOT, currentPath), "utf8")) as SourceProposal
      validateSourceProposal(candidate, profile)
      proposal = candidate
      selectedProposalPath = currentPath
    } catch (error) {
      diagnostic = error instanceof Error ? error.message : String(error)
      nextRevision += 1
    }
  }
  if (proposal === undefined || selectedProposalPath === undefined) {
    throw new Error(`OpenCode did not produce a valid official-source proposal after 2 revisions: ${diagnostic ?? "unknown failure"}`)
  }
  await acquire(proposal, profile, manifest, input.unit, selectedProposalPath)
  return {
    path: manifest,
    acquisition: {
      status: "DISCOVERED",
      startedAtUtc,
      finishedAtUtc: new Date().toISOString(),
      proposalPath: selectedProposalPath,
      agent: "source-acquirer",
      model: session?.model,
      sessionId: session?.sessionId,
    },
  }
}
