import { access, lstat, readFile } from "node:fs/promises"

import {
  artifactFingerprintsForGate,
  publishImmutableReviewRecord,
  resolveReviewDestination,
  type ArtifactFingerprint,
} from "./human-decision-record.js"
import type { GateName, RunState } from "./workflow.js"

type BenchmarkDecisionRecord = {
  schemaVersion: 1
  recordType: "benchmark_gate_auto_advance"
  reviewId: string
  unitId: string
  runId: string
  gate: GateName
  decision: "auto_advanced"
  controller: "Spec2Lean benchmark controller"
  rationale: string
  submittedAtUtc: string
  artifacts: ArtifactFingerprint[]
  humanConfirmationRecorded: false
  gateApprovalPerformed: false
  promotionPerformed: false
  semanticAssumptions: BenchmarkSemanticAssumption[]
  provenance: {
    controller: "spec2lean-cli"
    command: "formalize --auto-approve"
  }
}

export type BenchmarkSemanticAssumption = {
  semanticId: string
  statement: string
  rationale: string
  policy: "CONSERVATIVE_BOUNDED_SCOPE"
  unresolved: true
  humanApproved: false
}

export type BenchmarkDecisionLocation = {
  reviewId: string
  reviewPath: string
}

function gateSlug(gate: GateName): string {
  return gate.toLowerCase().replaceAll("_", "-")
}

export function benchmarkDecisionLocation(
  run: RunState,
  gate: GateName,
  version = 1,
): BenchmarkDecisionLocation {
  if (!Number.isSafeInteger(version) || version < 1) {
    throw new Error(`Invalid benchmark decision record version: ${version}`)
  }
  const unitId = `${run.language}-${run.unitSlug}`
  const reviewId = `${run.runId}-${gateSlug(gate)}-benchmark-auto-v${version}`
  return {
    reviewId,
    reviewPath: `reviews/${unitId}/benchmark-auto/${reviewId}.json`,
  }
}

function recordIdentityIsValid(
  record: Partial<BenchmarkDecisionRecord>,
  run: RunState,
  gate: GateName,
  reviewId: string,
): boolean {
  return record.schemaVersion === 1 &&
    record.recordType === "benchmark_gate_auto_advance" &&
    record.reviewId === reviewId &&
    record.unitId === `${run.language}-${run.unitSlug}` &&
    record.runId === run.runId &&
    record.gate === gate &&
    record.decision === "auto_advanced" &&
    record.humanConfirmationRecorded === false &&
    record.gateApprovalPerformed === false &&
    record.promotionPerformed === false
}

async function readBenchmarkDecisionRecord(
  destination: string,
): Promise<Partial<BenchmarkDecisionRecord>> {
  const metadata = await lstat(destination)
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error("Benchmark decision record is not a regular file")
  }
  return JSON.parse(await readFile(destination, "utf8")) as Partial<BenchmarkDecisionRecord>
}

async function exists(path: string): Promise<boolean> {
  try {
    await access(path)
    return true
  } catch {
    return false
  }
}

function sameArtifacts(
  left: ArtifactFingerprint[] | undefined,
  right: ArtifactFingerprint[],
): boolean {
  return Array.isArray(left) &&
    left.length === right.length &&
    left.every((artifact, index) => {
      const expected = right[index]
      return expected !== undefined &&
        artifact.relativePath === expected.relativePath &&
        artifact.sha256 === expected.sha256 &&
        artifact.sizeBytes === expected.sizeBytes
    })
}

export async function recordBenchmarkAutoAdvance(
  run: RunState,
  gate: GateName,
  semanticAssumptions: BenchmarkSemanticAssumption[] = [],
): Promise<{ recovered: boolean; reviewPath: string }> {
  if (run.benchmark?.autoApprove !== true) {
    throw new Error("Benchmark auto-advance is not enabled for this run")
  }

  const artifacts = await artifactFingerprintsForGate(run, gate)
  let selected: {
    reviewId: string
    reviewPath: string
    destination: string
    recovered: boolean
  } | undefined

  for (let version = 1; version < 1_000; version += 1) {
    const location = benchmarkDecisionLocation(run, gate, version)
    const destination = await resolveReviewDestination(location.reviewPath)
    if (!(await exists(destination))) {
      selected = { ...location, destination, recovered: false }
      break
    }
    const record = await readBenchmarkDecisionRecord(destination)
    if (!recordIdentityIsValid(record, run, gate, location.reviewId)) {
      throw new Error(`Benchmark decision record verification failed: ${location.reviewPath}`)
    }
    if (
      JSON.stringify(record.semanticAssumptions ?? []) === JSON.stringify(semanticAssumptions) &&
      sameArtifacts(record.artifacts, artifacts)
    ) {
      selected = { ...location, destination, recovered: true }
      break
    }
  }
  if (selected === undefined) {
    throw new Error(`Too many benchmark decision records for ${run.runId} ${gate}`)
  }
  const { reviewId, reviewPath, destination, recovered } = selected

  if (!recovered) {
    const record: BenchmarkDecisionRecord = {
      schemaVersion: 1,
      recordType: "benchmark_gate_auto_advance",
      reviewId,
      unitId: `${run.language}-${run.unitSlug}`,
      runId: run.runId,
      gate,
      decision: "auto_advanced",
      controller: "Spec2Lean benchmark controller",
      rationale:
        "Benchmark-only unattended execution advanced this review boundary. " +
        "This is not a human semantic approval and cannot authorize promotion.",
      submittedAtUtc: new Date().toISOString(),
      artifacts,
      humanConfirmationRecorded: false,
      gateApprovalPerformed: false,
      promotionPerformed: false,
      semanticAssumptions,
      provenance: {
        controller: "spec2lean-cli",
        command: "formalize --auto-approve",
      },
    }
    await publishImmutableReviewRecord(
      reviewPath,
      Buffer.from(`${JSON.stringify(record, null, 2)}\n`, "utf8"),
      "benchmark-decision",
    )
  }

  const record = await readBenchmarkDecisionRecord(destination)
  if (
    !recordIdentityIsValid(record, run, gate, reviewId) ||
    JSON.stringify(record.semanticAssumptions ?? []) !== JSON.stringify(semanticAssumptions) ||
    !sameArtifacts(record.artifacts, artifacts)
  ) {
    throw new Error(`Benchmark decision record verification failed: ${reviewPath}`)
  }

  return { recovered, reviewPath }
}
