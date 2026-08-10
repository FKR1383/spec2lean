import { createHash } from "node:crypto"
import { readFile, stat } from "node:fs/promises"
import { dirname, isAbsolute, relative, resolve, sep } from "node:path"

type SourceArtifact = {
  local_path?: unknown
  sha256?: unknown
  size_bytes?: unknown
}

type SourceManifest = {
  artifacts?: unknown
}

export async function verifySourceManifest(
  manifestPath: string,
): Promise<void> {
  const manifestData = await readFile(manifestPath)
  const manifest = JSON.parse(manifestData.toString("utf8")) as SourceManifest
  if (!Array.isArray(manifest.artifacts) || manifest.artifacts.length === 0) {
    throw new Error("source manifest has no artifacts")
  }

  const manifestDirectory = dirname(manifestPath)
  for (const rawArtifact of manifest.artifacts) {
    const artifact = rawArtifact as SourceArtifact
    if (
      typeof artifact.local_path !== "string" ||
      typeof artifact.sha256 !== "string" ||
      !/^[a-f0-9]{64}$/.test(artifact.sha256)
    ) {
      throw new Error("source manifest contains an invalid artifact entry")
    }

    const artifactPath = resolve(manifestDirectory, artifact.local_path)
    const relation = relative(manifestDirectory, artifactPath)
    if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
      throw new Error(`source artifact escapes manifest directory: ${artifact.local_path}`)
    }

    let data: Buffer
    try {
      data = await readFile(artifactPath)
    } catch {
      throw new Error(
        `source artifact is missing: ${artifact.local_path}; restore the pinned raw sources before starting a run`,
      )
    }

    const actualHash = createHash("sha256").update(data).digest("hex")
    if (actualHash !== artifact.sha256) {
      throw new Error(
        `source artifact hash mismatch: ${artifact.local_path}; expected ${artifact.sha256}, got ${actualHash}`,
      )
    }

    if (typeof artifact.size_bytes === "number") {
      const metadata = await stat(artifactPath)
      if (metadata.size !== artifact.size_bytes) {
        throw new Error(
          `source artifact size mismatch: ${artifact.local_path}; expected ${artifact.size_bytes}, got ${metadata.size}`,
        )
      }
    }
  }
}
