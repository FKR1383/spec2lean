import { buildPerfReport } from "./performance.js"

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index === -1 ? undefined : process.argv[index + 1]
}

const runId = argument("--run")
if (!runId) throw new Error("Missing required argument: --run")
console.log(JSON.stringify(await buildPerfReport(runId), null, 2))
