import { ensureSourceIndex } from "./source-index.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

function required(name: string): string {
  const value = argument(name)
  if (!value) throw new Error(`Missing required argument: ${name}`)
  return value
}

const result = await ensureSourceIndex({
  language: required("--language"),
  specificationVersion: required("--version"),
  sourceManifest: required("--source-manifest"),
})

console.log(JSON.stringify({ ok: true, ...result }, null, 2))
