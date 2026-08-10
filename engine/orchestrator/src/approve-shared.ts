import { readFile } from "node:fs/promises"
import { resolve } from "node:path"

import { REPO_ROOT } from "./repo.js"
import { approveSharedEnvironment } from "./shared-environment-approval.js"
import { validProfile } from "./semantic-v2.js"

function arg(name: string): string {
  const index = process.argv.indexOf(name)
  const value = index < 0 ? undefined : process.argv[index + 1]
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`missing ${name}`)
  }
  return value
}

const language = arg("--language").toLowerCase()
const version = arg("--version")
const reviewer = arg("--reviewer")
const rationale = arg("--rationale")
const profilePath = `language_packs/${language}/${version}/semantic-profile.json`
const profileInput = JSON.parse(await readFile(resolve(REPO_ROOT, profilePath), "utf8")) as unknown
if (!validProfile(profileInput)) throw new Error(`invalid semantic profile: ${profilePath}`)
if (profileInput.language.toLowerCase() !== language || profileInput.specificationVersion !== version) {
  throw new Error("semantic profile identity mismatch")
}

const result = await approveSharedEnvironment({
  profilePath,
  profile: profileInput,
  reviewer,
  rationale,
})
console.log(`Approved shared environment: ${result.approvedEnvironmentPath}`)
console.log(`Approval record: ${result.approvalRecordPath}`)
