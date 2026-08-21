import type { AgentExecution } from "./workflow.js"

export const OUTPUT_LENGTH_RETRY_LIMIT = 2
export const NO_PROGRESS_RETRY_LIMIT = 2

export function isProviderAvailabilityFailure(
  execution: AgentExecution | undefined,
): boolean {
  return execution?.failureClass === "PROVIDER_RETRY_BUDGET_EXCEEDED"
}

/**
 * Reconstruct the semantic retry budget from durable execution history.
 * Provider availability failures are transport observations, not failed
 * semantic attempts, and proof-producing continuations reset the stall count.
 */
export function semanticRetryState(
  executions: readonly AgentExecution[],
  stage: AgentExecution["stage"],
): { consecutiveRetries: number; retryStage?: AgentExecution["stage"] } {
  let consecutiveRetries = 0

  for (let index = executions.length - 1; index >= 0; index -= 1) {
    const execution = executions[index]!
    if (isProviderAvailabilityFailure(execution)) continue
    if (execution.stage !== stage || execution.outcome !== "RETRY") break
    if (execution.progress?.kind === "PROOF_BATCH_CONTINUATION") break
    consecutiveRetries += 1
  }

  return consecutiveRetries === 0
    ? { consecutiveRetries: 0 }
    : { consecutiveRetries, retryStage: stage }
}

export function consecutiveOutputLengthFailureCount(
  executions: readonly AgentExecution[],
  consecutiveRetries: number,
): number {
  if (consecutiveRetries <= 0) return 0
  return executions
    .slice(-consecutiveRetries)
    .filter((execution) => execution.failureClass === "OUTPUT_LENGTH_EXCEEDED")
    .length
}

export function outputLengthRetryLimitReached(
  executions: readonly AgentExecution[],
  consecutiveRetries: number,
): boolean {
  return consecutiveOutputLengthFailureCount(executions, consecutiveRetries) >=
    OUTPUT_LENGTH_RETRY_LIMIT
}

function executionMadeArtifactProgress(execution: AgentExecution): boolean {
  if (execution.progress?.kind === "PROOF_BATCH_CONTINUATION") return true
  // New executions carry a diagnostic fingerprint. A changed file that still
  // produces the identical diagnostic is not useful progress. Artifact hashes
  // remain the compatibility fallback for older execution records.
  if (execution.failureFingerprint !== undefined) return false
  if (execution.artifactProduced === true) return true
  return execution.artifactBeforeSha256 !== undefined &&
    execution.artifactAfterSha256 !== undefined &&
    execution.artifactBeforeSha256 !== execution.artifactAfterSha256
}

/**
 * Count the latest same-stage retries that repeat the same deterministic
 * failure without artifact/declaration progress. Two attempts mean the
 * original failed attempt plus one bounded repair attempt.
 */
export function noProgressRetryCount(
  executions: readonly AgentExecution[],
  stage: AgentExecution["stage"],
): number {
  const latest = [...executions].reverse().find((execution) =>
    !isProviderAvailabilityFailure(execution)
  )
  if (
    latest === undefined ||
    latest.stage !== stage ||
    latest.outcome !== "RETRY" ||
    executionMadeArtifactProgress(latest)
  ) return 0

  let count = 0
  for (let index = executions.length - 1; index >= 0; index -= 1) {
    const execution = executions[index]!
    if (isProviderAvailabilityFailure(execution)) continue
    if (execution.stage !== stage || execution.outcome !== "RETRY") break
    if (executionMadeArtifactProgress(execution)) break
    if (
      latest.failureFingerprint !== undefined &&
      execution.failureFingerprint !== latest.failureFingerprint
    ) break
    count += 1
  }
  return count
}

export function noProgressRetryLimitReached(
  executions: readonly AgentExecution[],
  stage: AgentExecution["stage"],
): boolean {
  return noProgressRetryCount(executions, stage) >= NO_PROGRESS_RETRY_LIMIT
}
