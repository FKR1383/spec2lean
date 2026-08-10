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
  provenance: {
    controller: "spec2lean-cli"
    command: "formalize --auto-approve"
  }
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
): BenchmarkDecisionLocation {
  const unitId = `${run.language}-${run.unitSlug}`
  const reviewId = `${run.runId}-${gateSlug(gate)}-benchmark-auto-v1`
  return {
    reviewId,
    reviewPath: `reviews/${unitId}/benchmark-auto/${reviewId}.json`,
  }
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
): Promise<{ recovered: boolean; reviewPath: string }> {
  if (run.benchmark?.autoApprove !== true) {
    throw new Error("Benchmark auto-advance is not enabled for this run")
  }

  const { reviewId, reviewPath } = benchmarkDecisionLocation(run, gate)
  const artifacts = await artifactFingerprintsForGate(run, gate)
  const destination = await resolveReviewDestination(reviewPath)
  const recovered = await exists(destination)

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

  const metadata = await lstat(destination)
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error("Benchmark decision record is not a regular file")
  }
  const record = JSON.parse(
    await readFile(destination, "utf8"),
  ) as Partial<BenchmarkDecisionRecord>
  if (
    record.schemaVersion !== 1 ||
    record.recordType !== "benchmark_gate_auto_advance" ||
    record.reviewId !== reviewId ||
    record.unitId !== `${run.language}-${run.unitSlug}` ||
    record.runId !== run.runId ||
    record.gate !== gate ||
    record.decision !== "auto_advanced" ||
    record.humanConfirmationRecorded !== false ||
    record.gateApprovalPerformed !== false ||
    record.promotionPerformed !== false ||
    !sameArtifacts(record.artifacts, artifacts)
  ) {
    throw new Error(`Benchmark decision record verification failed: ${reviewPath}`)
  }

  return { recovered, reviewPath }
}
