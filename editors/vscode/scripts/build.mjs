import { copyFile, mkdir, rm } from "node:fs/promises"
import { dirname, resolve } from "node:path"
import { fileURLToPath } from "node:url"

import { build } from "esbuild"

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const dist = resolve(root, "dist")
const vendor = resolve(dist, "vendor")

await rm(dist, { recursive: true, force: true })
await mkdir(vendor, { recursive: true })
await build({
  entryPoints: [resolve(root, "src/extension.ts")],
  outfile: resolve(dist, "extension.js"),
  bundle: true,
  platform: "node",
  format: "cjs",
  target: "node20",
  external: ["vscode"],
  sourcemap: true,
})
await copyFile(
  resolve(root, "node_modules/pdfjs-dist/build/pdf.mjs"),
  resolve(vendor, "pdf.mjs"),
)
await copyFile(
  resolve(root, "node_modules/pdfjs-dist/build/pdf.worker.mjs"),
  resolve(vendor, "pdf.worker.mjs"),
)
