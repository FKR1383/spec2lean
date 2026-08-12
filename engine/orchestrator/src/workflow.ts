export const FORMALIZATION_STAGES = [
  "CREATED",

  "ARCHITECTURE",
  "ARCHITECTURE_CRITIQUE",
  "WAITING_GATE_A",

  "SOURCE_CURATION",
  "SEMANTIC_EXTRACTION",
  "SEMANTIC_CRITIQUE",
  "WAITING_GATE_B",

  "LEAN_FORMALIZATION",
  "LEAN_MAPPING_CRITIQUE",
  "WAITING_GATE_C",

  "THEOREM_GENERATION",
  "THEOREM_STRENGTH_CRITIQUE",
  "WAITING_THEOREM_STRENGTH_APPROVAL",

  "PROOF_GENERATION",

  "FINAL_CRITIQUE",
  "WAITING_FINAL_APPROVAL",

  "BENCHMARK_COMPLETE",
  "ACCEPTED",
  "BLOCKED",
  "FAILED",
] as const

export type FormalizationStage =
  (typeof FORMALIZATION_STAGES)[number]

export type WorkflowMode =
  | "formalization"
  | "translation"

export type GateName =
  | "A"
  | "B"
  | "C"
  | "THEOREM_STRENGTH"
  | "FINAL"

export type GateStatus =
  | "pending"
  | "approved"
  | "benchmark_auto_advanced"
  | "rejected"

export type RunEvent = {
  at: string
  from: FormalizationStage | null
  to: FormalizationStage
  reason: string
}

export type AgentExecution = {
  startedAt?: string
  at: string
  stage: FormalizationStage
  agent: string
  model?: string
  sessionId: string
  outcome: string
  nextStage: FormalizationStage
  response: string
  artifactProduced?: boolean
  failureClass?: "PROVIDER_RETRY_BUDGET_EXCEEDED"
  traceability?: {
    documentRole: "SEMANTICS" | "PROOFS"
    manifestPath: string
    generationMs: number
    entries: number
    unresolvedReferences: number
  }
}

export type ActiveExecution = {
  startedAt: string
  stage: FormalizationStage
  agent: string
  model?: string
  sessionId: string
  expectedArtifact: string
}

export type SemanticV2Mode =
  | "UNASSESSED"
  | "DELTA_FAST_PATH"
  | "LEGACY_FALLBACK"

export type SemanticV2ArtifactSet = {
  attempt: number
  deltaPath: string
  materializedPath: string
  criticPacketPath: string
  deltaBytes?: number
  materializedBytes?: number
  criticPacketBytes?: number
  deltaSha256?: string
  materializedSha256?: string
  criticPacketSha256?: string
}

export type SemanticV2Event = {
  at: string
  kind: "ELIGIBILITY" | "FALLBACK" | "MATERIALIZED" | "CRITIC_FALLBACK"
  code: string
  detail: string
}

export type SemanticV2State = {
  profilePath: string
  sharedEnvironmentPath: string
  mode: SemanticV2Mode
  environment?: {
    environmentId: string
    revision: number
    sha256: string
    reviewStatus: string
  }
  missingRequiredSemanticIds: string[]
  fallbackReason?: string
  current?: SemanticV2ArtifactSet
  events: SemanticV2Event[]
}

export type RunState = {
  schemaVersion: 1

  runId: string
  mode: WorkflowMode

  language: string
  specVersion: string
  unit: string

  unitSlug: string
  leanModuleName: string
  sourceManifest: string
  sourceAcquisition?: {
    status: "CACHE_HIT" | "DISCOVERED"
    startedAtUtc: string
    finishedAtUtc: string
    proposalPath?: string
    agent?: string
    model?: string
    sessionId?: string
  }
  artifactRoot: string

  stage: FormalizationStage

  createdAt: string
  updatedAt: string

  revision: number

  gates: Record<GateName, GateStatus>

  history: RunEvent[]

  executions?: AgentExecution[]
  activeExecution?: ActiveExecution
  semanticV2?: SemanticV2State
  benchmark?: {
    autoApprove: true
    startedAtUtc: string
  }
}

const transitions:
  Record<FormalizationStage, readonly FormalizationStage[]> = {

  CREATED: [
    "ARCHITECTURE",
    "BLOCKED",
    "FAILED",
  ],

  ARCHITECTURE: [
    "ARCHITECTURE_CRITIQUE",
    "BLOCKED",
    "FAILED",
  ],

  ARCHITECTURE_CRITIQUE: [
    "ARCHITECTURE",
    "WAITING_GATE_A",
    "BLOCKED",
    "FAILED",
  ],

  WAITING_GATE_A: [
    "SOURCE_CURATION",
    "ARCHITECTURE",
    "BLOCKED",
    "FAILED",
  ],

  SOURCE_CURATION: [
    "SEMANTIC_EXTRACTION",
    "BLOCKED",
    "FAILED",
  ],

  SEMANTIC_EXTRACTION: [
    "SEMANTIC_CRITIQUE",
    "SOURCE_CURATION",
    "BLOCKED",
    "FAILED",
  ],

  SEMANTIC_CRITIQUE: [
    "SEMANTIC_EXTRACTION",
    "SOURCE_CURATION",
    "WAITING_GATE_B",
    "BLOCKED",
    "FAILED",
  ],

  WAITING_GATE_B: [
    "LEAN_FORMALIZATION",
    "SEMANTIC_EXTRACTION",
    "SOURCE_CURATION",
    "BLOCKED",
    "FAILED",
  ],

  LEAN_FORMALIZATION: [
    "LEAN_MAPPING_CRITIQUE",
    "BLOCKED",
    "FAILED",
  ],

  LEAN_MAPPING_CRITIQUE: [
    "LEAN_FORMALIZATION",
    "WAITING_GATE_C",
    "BLOCKED",
    "FAILED",
  ],

  WAITING_GATE_C: [
    "THEOREM_GENERATION",
    "LEAN_FORMALIZATION",
    "BLOCKED",
    "FAILED",
  ],

  THEOREM_GENERATION: [
    "THEOREM_STRENGTH_CRITIQUE",
    "BLOCKED",
    "FAILED",
  ],

  THEOREM_STRENGTH_CRITIQUE: [
    "THEOREM_GENERATION",
    "WAITING_THEOREM_STRENGTH_APPROVAL",
    "BLOCKED",
    "FAILED",
  ],

  WAITING_THEOREM_STRENGTH_APPROVAL: [
    "PROOF_GENERATION",
    "THEOREM_GENERATION",
    "BLOCKED",
    "FAILED",
  ],

  PROOF_GENERATION: [
    "PROOF_GENERATION",
    "FINAL_CRITIQUE",
    "BLOCKED",
    "FAILED",
  ],

  FINAL_CRITIQUE: [
    "FINAL_CRITIQUE",
    "WAITING_FINAL_APPROVAL",
    "BLOCKED",
    "FAILED",
  ],

  WAITING_FINAL_APPROVAL: [
    "BENCHMARK_COMPLETE",
    "ACCEPTED",
    "BLOCKED",
    "FAILED",
  ],

  BENCHMARK_COMPLETE: [],

  ACCEPTED: [],

  BLOCKED: [
    "ARCHITECTURE",
    "SOURCE_CURATION",
    "SEMANTIC_EXTRACTION",
    "LEAN_FORMALIZATION",
    "THEOREM_GENERATION",
    "PROOF_GENERATION",
    "FINAL_CRITIQUE",
    "FAILED",
  ],

  FAILED: [],
}

export function canTransition(
  from: FormalizationStage,
  to: FormalizationStage,
): boolean {
  return transitions[from].includes(to)
}

export function transitionRun(
  run: RunState,
  to: FormalizationStage,
  reason: string,
): RunState {
  if (!canTransition(run.stage, to)) {
    throw new Error(
      `Illegal workflow transition: ${run.stage} -> ${to}`,
    )
  }

  const now = new Date().toISOString()

  return {
    ...run,
    stage: to,
    updatedAt: now,
    revision: run.revision + 1,
    history: [
      ...run.history,
      {
        at: now,
        from: run.stage,
        to,
        reason,
      },
    ],
  }
}

export function retryRun(
  run: RunState,
  reason: string,
): RunState {
  const now = new Date().toISOString()

  return {
    ...run,
    updatedAt: now,
    revision: run.revision + 1,
    history: [
      ...run.history,
      {
        at: now,
        from: run.stage,
        to: run.stage,
        reason,
      },
    ],
  }
}
