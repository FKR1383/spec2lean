import { ensureSourceIndex } from "./source-index.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

const version = argument("--version")
if (!version) throw new Error("Missing required argument: --version")

const result = await ensureSourceIndex({
  language: "ptx",
  specificationVersion: version,
  sourceManifest: `documents/sources/nvidia/ptx/${version}/source-manifest.json`,
})

console.log(JSON.stringify({ ok: true, version, ...result }, null, 2))
