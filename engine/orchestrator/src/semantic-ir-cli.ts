import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import { canonicalJson } from "./semantic-ir/canonical.js"
import {
  semanticDeltaSha256,
  sharedEnvironmentSha256,
} from "./semantic-ir/document.js"
import { materializeSemanticView } from "./semantic-ir/materialize.js"
import { createDeltaCriticPacket } from "./semantic-ir/review-packet.js"
import type {
  InstructionSemanticDelta,
  SharedSemanticEnvironment,
} from "./semantic-ir/types.js"
import {
  validateInstructionSemanticDelta,
  validateSharedSemanticEnvironment,
} from "./semantic-ir/validate.js"
import { REPO_ROOT } from "./repo.js"

async function readJson(path: string): Promise<unknown> {
  return JSON.parse(await readFile(resolve(REPO_ROOT, path), "utf8"))
}

function usage(): never {
  throw new Error(
    "Usage: semantic-ir validate-shared <environment.json> | validate-delta <environment.json> <delta.json> | hash-shared <environment.json> | hash-delta <delta.json> | materialize <environment.json> <delta.json> | review-packet <environment.json> <delta.json>",
  )
}

const [command, ...paths] = process.argv.slice(2)
function pathAt(index: number): string {
  return paths[index] ?? usage()
}

switch (command) {
  case "validate-shared": {
    if (paths.length !== 1) usage()
    const result = validateSharedSemanticEnvironment(await readJson(pathAt(0)))
    console.log(canonicalJson(result))
    if (!result.ok || result.unresolvedStateAffectingSemanticIds.length > 0) {
      process.exitCode = 1
    }
    break
  }
  case "validate-delta": {
    if (paths.length !== 2) usage()
    const shared = await readJson(pathAt(0))
    const delta = await readJson(pathAt(1))
    const result = validateInstructionSemanticDelta(delta, shared)
    console.log(canonicalJson(result))
    if (!result.ok || result.unresolvedStateAffectingSemanticIds.length > 0) {
      process.exitCode = 1
    }
    break
  }
  case "hash-shared": {
    if (paths.length !== 1) usage()
    const input = await readJson(pathAt(0))
    const result = validateSharedSemanticEnvironment(input)
    if (!result.ok || result.value === undefined) {
      console.error(canonicalJson(result))
      process.exitCode = 1
      break
    }
    console.log(sharedEnvironmentSha256(result.value))
    break
  }
  case "hash-delta": {
    if (paths.length !== 1) usage()
    const input = await readJson(pathAt(0)) as InstructionSemanticDelta
    console.log(semanticDeltaSha256(input))
    break
  }
  case "materialize": {
    if (paths.length !== 2) usage()
    const shared = await readJson(pathAt(0))
    const delta = await readJson(pathAt(1))
    console.log(canonicalJson(materializeSemanticView(shared, delta)))
    break
  }
  case "review-packet": {
    if (paths.length !== 2) usage()
    const shared = await readJson(pathAt(0)) as SharedSemanticEnvironment
    const delta = await readJson(pathAt(1)) as InstructionSemanticDelta
    console.log(canonicalJson(createDeltaCriticPacket(shared, delta)))
    break
  }
  default:
    usage()
}
